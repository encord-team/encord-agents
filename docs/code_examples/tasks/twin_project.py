from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.options import Option
from encord.workflow.stages.agent import AgentTask
from encord_agents.tasks import Depends, Runner
from encord_agents.tasks.dependencies import Twin, dep_twin_label_row
from typing_extensions import Annotated

# 1. Setup the runner
runner = Runner(project_hash="<project_hash_a>")

# 2. Get the classification attribute used to query answers
checklist_classification = (
    runner.project.ontology_structure.classifications[0]  # type: ignore
)
checklist_attribute = checklist_classification.attributes[0]

# 3. Define the agent
from uuid import UUID


@runner.stage(stage=UUID("<transfer_agent_stage_uuid>"))
def copy_labels(
    manually_annotated_lr: LabelRowV2,
    twin: Annotated[
        Twin, Depends(dep_twin_label_row(twin_project_hash="<project_hash_b>"))
    ],
) -> str | None:
    # 4. Reading the checkboxes that have been set
    instance = manually_annotated_lr.get_classification_instances()[0]
    answers = instance.get_answer(attribute=checklist_attribute)
    if answers is None or isinstance(answers, (str, Option)):
        return None

    set_options = {o.title for o in answers}  # Use title to match

    # 5. Set answer on the sink labels
    for radio_clf in twin.label_row.ontology_structure.classifications:
        ins = radio_clf.create_instance()

        attr = radio_clf.attributes[0]
        if radio_clf.title in set_options:
            ins.set_answer(attr.options[0])
        else:
            ins.set_answer(attr.options[1])

        ins.set_for_frames(frames=0)
        twin.label_row.add_classification_instance(ins)

    # 6. Save labels and proceed tasks
    twin.label_row.save()
    if twin.task and isinstance(twin.task, AgentTask):
        twin.task.proceed(pathway_uuid="<twin_completion_pathway_uuid>")

    return "<labeling_completion_pathway_uuid>"


if __name__ == "__main__":
    runner.run()
