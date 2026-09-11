import logging
from typing import Callable, NamedTuple
from uuid import UUID

from encord.exceptions import InvalidArgumentsError
from encord.http.bundle import Bundle
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.orm.project import ProjectType
from encord.orm.workflow import WorkflowStageType
from encord.project import Project
from encord.user_client import EncordUserClient
from encord.workflow.stages.agent import AgentStage, AgentTask
from encord.workflow.workflow import WorkflowStage
from typer import Abort

from encord_agents.core.data_model import LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.core.dependencies.models import (
    Context,
    Dependant,
)
from encord_agents.core.dependencies.utils import get_dependant
from encord_agents.core.utils import get_user_client
from encord_agents.exceptions import PrintableError
from encord_agents.tasks.models import TaskAgentReturnType
from encord_agents.utils.generic_utils import try_coerce_UUID

logger = logging.getLogger(__name__)


class StagePathways(NamedTuple):
    """The pathways of one agent stage, indexed both ways for lookup.

    Built once per stage rather than per task: validating an agent's answer needs
    membership by uuid and resolution by name, and rebuilding either from
    `stage.pathways` inside the task loop is wasted work.
    """

    uuid_by_name: dict[str, UUID]
    name_by_uuid: dict[UUID, str]

    @classmethod
    def from_stage(cls, stage: AgentStage) -> "StagePathways":
        return cls(
            uuid_by_name={pathway.name: pathway.uuid for pathway in stage.pathways},
            name_by_uuid={pathway.uuid: pathway.name for pathway in stage.pathways},
        )


class PendingPathway(NamedTuple):
    """A pathway action resolved for a task but not yet applied to it.

    A pathway an agent named is resolved to its uuid before it gets here, so there is no
    state in which neither field is set -- which `AgentTask.proceed` rejects at runtime.
    """

    task: AgentTask
    pathway_uuid: UUID


class RunnerAgent:
    def __init__(
        self,
        identity: str | UUID,
        callable: Callable[..., TaskAgentReturnType],
        printable_name: str | None = None,
        label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None = None,
        label_row_initialise_labels_args: LabelRowInitialiseLabelsArgs | None = None,
        will_set_priority: bool = False,
    ):
        self.identity = identity
        self.printable_name = printable_name or identity
        self.callable = callable
        self.dependant: Dependant = get_dependant(func=callable)
        self.label_row_metadata_include_args = label_row_metadata_include_args
        self.label_row_initialise_labels_args = label_row_initialise_labels_args
        self.will_set_priority = will_set_priority

    def __repr__(self) -> str:
        return f'RunnerAgent("{self.printable_name}")'


class RunnerBase:
    @staticmethod
    def _resolve_pathway(
        task: AgentTask,
        pathway_to_follow: UUID | str | None,
        pathways: StagePathways,
    ) -> PendingPathway | None:
        """Validate the pathway an agent chose and return the action that applies it.

        Applying is deferred to `_apply_pathway_actions` so a batch of tasks can be moved
        in one request. A pathway the agent named is resolved to its uuid here, so every
        action carries the destination and both runners send the same field.

        Returns:
            The action to apply, or None if the agent returned no pathway.

        Raises:
            PrintableError: If the pathway is not one of the stage's.
        """
        if pathway_to_follow is None:
            # TODO: Should we log that task didn't continue?
            return None

        if next_stage_uuid := try_coerce_UUID(pathway_to_follow):
            if next_stage_uuid not in pathways.name_by_uuid:
                raise PrintableError(
                    f"No pathway with UUID: {next_stage_uuid} found. "
                    f"Accepted pathway UUIDs are: {list(pathways.name_by_uuid)}"
                )
            return PendingPathway(task, next_stage_uuid)

        if pathway_to_follow not in pathways.uuid_by_name:
            raise PrintableError(
                f"No pathway with name: {pathway_to_follow} found. "
                f"Accepted pathway names are: {list(pathways.uuid_by_name)}"
            )
        return PendingPathway(task, pathways.uuid_by_name[str(pathway_to_follow)])

    @staticmethod
    def _apply_pathway_actions(pending_pathways: list[PendingPathway]) -> tuple[set[UUID], set[UUID]]:
        """Move tasks along their chosen pathways, in a single request where possible.

        Encord rejects the entire request if any task in it has already left the stage, so
        one task advanced by someone else -- a concurrent run, or a person in the app --
        would otherwise strand every other task batched with it. On any rejection the
        actions are replayed one at a time, which costs a request per task but keeps the
        outcome per task rather than losing the batch.

        Returns:
            The uuids of the tasks that had already left the stage, and the uuids of those
            this call could not move for any other reason. Tasks in neither set were moved.
        """
        if not pending_pathways:
            return set(), set()

        try:
            with Bundle() as task_bundle:
                for pending in pending_pathways:
                    pending.task.proceed(pathway_uuid=pending.pathway_uuid, bundle=task_bundle)
            return set(), set()
        except InvalidArgumentsError:
            # The expected rejection: at least one task in the request has moved on.
            logger.warning(f"Bundled pathway update rejected; replaying {len(pending_pathways)} task(s) individually.")
        except Exception as exc:
            # Anything else is unexplained, so replay too rather than lose the whole batch
            # to it. Each task then gets its own outcome below.
            logger.warning(
                f"Bundled pathway update failed with {type(exc).__name__}; "
                f"replaying {len(pending_pathways)} task(s) individually.",
                exc_info=exc,
            )

        already_advanced: set[UUID] = set()
        could_not_move: set[UUID] = set()
        for pending in pending_pathways:
            try:
                pending.task.proceed(pathway_uuid=pending.pathway_uuid)
            except InvalidArgumentsError:
                logger.info(f"Task {pending.task.uuid} has already left this stage; leaving it where it is.")
                already_advanced.add(pending.task.uuid)
            except Exception:
                logger.exception(f"Could not move task {pending.task.uuid} along its pathway.")
                could_not_move.add(pending.task.uuid)
        return already_advanced, could_not_move

    @staticmethod
    def _verify_project_hash(ph: str | UUID) -> str:
        try:
            ph = str(UUID(str(ph)))
        except ValueError:
            logger.error("Could not read project_hash as a UUID")
            raise Abort()
        return ph

    @staticmethod
    def _get_stage_names(valid_stages: list[AgentStage], join_str: str = ", ") -> str:
        return join_str.join(
            [f'[magenta]AgentStage(title="{k.title}", uuid="{k.uuid}")[/magenta]' for k in valid_stages]
        )

    @staticmethod
    def _validate_project(project: Project | None) -> None:
        if project is None:
            return
        PROJECT_MUSTS = "Task agents only work for workflow projects that have agent nodes in the workflow."
        assert (
            project.project_type == ProjectType.WORKFLOW
        ), f"Provided project is not a workflow project. {PROJECT_MUSTS}"
        assert (
            len([s for s in project.workflow.stages if s.stage_type == WorkflowStageType.AGENT]) > 0
        ), f"Provided project does not have any agent stages in it's workflow. {PROJECT_MUSTS}"

    @staticmethod
    def _validate_max_tasks_per_stage(max_tasks_per_stage: int | None) -> int | None:
        if max_tasks_per_stage is not None:
            if max_tasks_per_stage < 1:
                raise PrintableError("We require that `max_tasks_per_stage` >= 1")
        return max_tasks_per_stage

    @classmethod
    def _assemble_context(
        cls,
        task: AgentTask,
        runner_agent: RunnerAgent,
        project: Project,
        include_args: LabelRowMetadataIncludeArgs,
        init_args: LabelRowInitialiseLabelsArgs,
        stage: AgentStage,
        client: EncordUserClient,
    ) -> Context:
        contexts = cls._assemble_contexts([task], runner_agent, project, include_args, init_args, stage, client)
        assert contexts
        return contexts[0]

    @staticmethod
    def _get_ordered_label_rows_from_tasks(
        tasks: list[AgentTask],
        include_args: LabelRowMetadataIncludeArgs | None,
        project: Project,
    ) -> list[LabelRowV2]:
        include_args = include_args or LabelRowMetadataIncludeArgs()
        label_rows = {
            UUID(lr.data_hash): lr
            for lr in project.list_label_rows_v2(data_hashes=[t.data_hash for t in tasks], **include_args.model_dump())
        }
        task_lrs: list[LabelRowV2] = []
        for task in tasks:
            if task.data_hash not in label_rows:
                raise ValueError(
                    f"We have a task: {task}, with {task.data_hash=} but there was no such label row found for this data_hash. Should be impossible"
                )
            task_lrs.append(label_rows[task.data_hash])
        return task_lrs

    @staticmethod
    def _assemble_contexts(
        task_batch: list[AgentTask],
        runner_agent: RunnerAgent,
        project: Project,
        include_args: LabelRowMetadataIncludeArgs,
        init_args: LabelRowInitialiseLabelsArgs,
        stage: AgentStage,
        client: EncordUserClient,
    ) -> list[Context]:
        contexts = [
            Context(
                project=project,
                label_row=None,
                task=task,
                agent_stage=stage,
                storage_item=None,
            )
            for task in task_batch
        ]
        batch_lrs: list[LabelRowV2] = []
        if runner_agent.dependant.needs_label_row or runner_agent.will_set_priority:
            batch_lrs = RunnerBase._get_ordered_label_rows_from_tasks(task_batch, include_args, project)
            if runner_agent.dependant.needs_label_row:
                with project.create_bundle() as lr_bundle:
                    for lr in batch_lrs:
                        lr.initialise_labels(bundle=lr_bundle, **init_args.model_dump())
            for label_row, context in zip(batch_lrs, contexts, strict=True):
                context.label_row = label_row
        if runner_agent.dependant.needs_storage_item:
            if not batch_lrs:
                # Fetch LRs as a reference to the backing_item_uuids. Note not passing args nor passing into context.
                batch_lrs = RunnerBase._get_ordered_label_rows_from_tasks(task_batch, None, project)
            storage_items = client.get_storage_items([lr.backing_item_uuid or "" for lr in batch_lrs], sign_url=True)
            if len(storage_items) != len(contexts):
                batch_lr_backing_item_uuids = set(lr.backing_item_uuid for lr in batch_lrs)
                storage_item_backing_item_uuids = set(storage_item.uuid for storage_item in storage_items)
                missing_backing_item_uuids = list(batch_lr_backing_item_uuids - storage_item_backing_item_uuids)
                raise ValueError(
                    f"Failed to get the storage items for: {missing_backing_item_uuids}. Please ensure that the account used to execute the agent has the appropriate permissions"
                )
            for storage_item, context in zip(storage_items, contexts, strict=True):
                context.storage_item = storage_item

        return contexts

    def __init__(
        self,
        project_hash: str | UUID | None = None,
        *,
        user_client: EncordUserClient | None = None,
    ):
        """
        Initialize the runner with an optional project hash.

        The `project_hash` will allow stricter stage validation.
        If left unspecified, errors will first be raised during execution of the runner.

        Args:
            project_hash: The project hash that the runner applies to.

                Can be left unspecified to be able to reuse same runner on multiple projects.
        """
        self.project_hash = self._verify_project_hash(project_hash) if project_hash else None
        self.client = user_client or get_user_client()

        self.project: Project | None = self.client.get_project(self.project_hash) if self.project_hash else None
        self._validate_project(self.project)

        self.valid_stages: list[AgentStage] | None = None
        if self.project is not None:
            self.valid_stages = [s for s in self.project.workflow.stages if s.stage_type == WorkflowStageType.AGENT]
        self.agents: list[RunnerAgent] = []

    def _validate_stage(self, stage: str | UUID) -> tuple[UUID | str, str]:
        """
        Returns stage uuid and printable name.
        """
        printable_name = str(stage)
        try:
            stage = UUID(str(stage))
        except ValueError:
            pass

        if self.valid_stages is not None:
            selected_stage: WorkflowStage | None = None
            for v_stage in self.valid_stages:
                attr = v_stage.title if isinstance(stage, str) else v_stage.uuid
                if attr == stage:
                    selected_stage = v_stage

            if selected_stage is None:
                agent_stage_names = self._get_stage_names(self.valid_stages)
                raise PrintableError(
                    rf"Stage name [blue]`{stage}`[/blue] could not be matched against a project stage. Valid stages are \[{agent_stage_names}]."
                )
            stage = selected_stage.uuid

        return stage, printable_name

    def _check_stage_already_defined(
        self, stage: UUID | str, printable_name: str, *, overwrite: bool = False
    ) -> int | None:
        if stage in [a.identity for a in self.agents]:
            if not overwrite:
                raise PrintableError(
                    f"Stage name [blue]`{printable_name}`[/blue] has already been assigned a function. You can only assign one callable to each agent stage."
                )
            previous_index = [agent.identity for agent in self.agents].index(stage)
            return previous_index
        return None

    def _add_stage_agent(
        self,
        identity: str | UUID,
        func: Callable[..., TaskAgentReturnType],
        *,
        stage_insertion: int | None,
        printable_name: str | None,
        label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None,
        label_row_initialise_labels_args: LabelRowInitialiseLabelsArgs | None,
        will_set_priority: bool = False,
    ) -> RunnerAgent:
        runner_agent = RunnerAgent(
            identity=identity,
            callable=func,
            printable_name=printable_name,
            label_row_metadata_include_args=label_row_metadata_include_args,
            label_row_initialise_labels_args=label_row_initialise_labels_args,
            will_set_priority=will_set_priority,
        )
        if stage_insertion is not None:
            if stage_insertion >= len(self.agents):
                raise ValueError("This should be impossible. Trying to update an agent at a location not defined")
            self.agents[stage_insertion] = runner_agent
        else:
            self.agents.append(runner_agent)
        return runner_agent
