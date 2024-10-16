from typing import Annotated, Iterator

from encord.objects.ontology_labels_impl import LabelRowV2
from encord_agents.tasks import Runner, Depends
from encord_agents.tasks.dependencies import dep_video_iterator
from encord_agents.core.data_model import Frame


# TODO remove me
project_hash = "a918b378-1041-489b-b228-ab684c3fb026"
runner = Runner(project_hash=project_hash)


@runner.stage(stage="pre-label")
def run_something(
    lr: LabelRowV2, 
    frames: Annotated[Iterator[Frame], Depends(dep_video_iterator)],
):
    # Do actions to label rows here

    print(lr.data_title)
    print([f.content.shape[0] for f in frames])

    return "annotate"  # Tell where the task should go


if __name__ == "__main__":
    from typer import Typer
    app = Typer(add_completion=False, rich_markup_mode="rich")
    app.command()(runner.__call__)
    app()

