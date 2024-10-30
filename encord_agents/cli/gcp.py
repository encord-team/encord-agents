"""
GCP related CLI actions.

This file assists in initializing, running, and deploying Google cloud run
functions.
"""

import subprocess
from pathlib import Path
from shutil import copy
from typing import Optional

import rich
from rich.console import Group
from rich.panel import Panel
from rich.tree import Tree
from typer import Abort, Argument, Option, Typer
from typing_extensions import Annotated

app = Typer(
    name="gcp",
    help="Utility to setup and run GCP agents locally",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# TODO update encord-agents dependency
_DEPENDENCIES = """
functions-framework
git+https://github.com/encord-team/encord_agents
"""

_TEMPLATE_CONTENT_W_ASSET = """
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.coordinates import BoundingBoxCoordinates
from encord_agents import FrameData
from encord_agents.gcp import editor_agent


@editor_agent(asset=True)
def my_editor_agent(frame_data: FrameData, label_row: LabelRowV2, asset: Path) -> None:
    ins = label_row.ontology_structure.objects[0].create_instance()
    ins.set_for_frames(
        frames=frame_data.frame,
        coordinates=BoundingBoxCoordinates(
            top_left_x=0.2, top_left_y=0.2, width=0.6, height=0.6
        ),
    )
    label_row.add_object_instance(ins)
    label_row.save()
"""

_TEMPLATE_CONTENT_WO_ASSET = """
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.coordinates import BoundingBoxCoordinates
from encord_agents import FrameData
from encord_agents.gcp import editor_agent


@editor_agent(asset=False)
def my_editor_agent(frame_data: FrameData, label_row: LabelRowV2) -> None:
    ins = label_row.ontology_structure.objects[0].create_instance()
    ins.set_for_frames(
        frames=frame_data.frame,
        coordinates=BoundingBoxCoordinates(
            top_left_x=0.2, top_left_y=0.2, width=0.6, height=0.6
        ),
    )
    label_row.add_object_instance(ins)
    label_row.save()
"""


def write_requirements_file(destination: Path):
    with (destination / "requirements.txt").open("w") as f:
        f.write(_DEPENDENCIES)


def move_src(src_file: Path, destination: Path):
    dest_file = destination / "main.py"
    copy(src_file, dest_file)


def write_template_file(destination: Path, with_asset: bool):
    (destination / "main.py").write_text(_TEMPLATE_CONTENT_W_ASSET if with_asset else _TEMPLATE_CONTENT_WO_ASSET)


def print_instructions(destination: Path):
    """
    Print instructions to run the project created by the `init` command.

    Args:
        destination: The directory where the project was initialized.
    """
    cwd = Path.cwd()
    rel_path = destination.relative_to(cwd) if destination.is_relative_to(cwd) else destination

    tree = Tree(f":open_file_folder: {rel_path}")
    tree.add(":page_facing_up: requirements.txt")
    tree.add("🐍 main.py")
    panel = Panel(
        Group(
            f"""
A project [blue]`{rel_path}`[/blue] was created with the following files:
    """,
            tree,
            f"""
To start using the project, follow these steps

[magenta]
cd {rel_path}
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
[/magenta]

Now you can edit the [blue]`main.py`[/blue] to your needs.

To test your function, please see [link=https://google.com]the docs :open_book:[/link]
to learn how to use [cyan]`encord-agents gcp run`[/cyan] and [cyan]`encord-agents test local`[/cyan].
""",
        ),
        title=":star2: Project successfully created :star2:",
    )
    rich.print(panel)


@app.command(
    "init",
)
def init(
    project_name: Annotated[str, Argument(help="Name of new project directory")],
    src_file: Annotated[
        Optional[Path],
        Option(
            help="File to convert into the main file if you have one already. Can, e.g., be used with examples from the examples directory of the repo."
        ),
    ] = None,
    with_asset: Annotated[
        bool,
        Option(
            help="If your application needs the asset (image/frame of video, then set this to true for a more complete file template. Note, this only has an effect when you don't specify a `src_file`."
        ),
    ] = False,
):
    """
    Initialize a project with the required files for running an agent with GCP.
    """
    destination = Path.cwd() / project_name
    if destination.exists():
        raise Abort("Cannot create project with that name. It already exists.")

    destination.mkdir()
    write_requirements_file(destination)
    if src_file is not None:
        move_src(src_file, destination)
    else:
        write_template_file(destination, with_asset)

    print_instructions(destination)


@app.command("run", help="Run the agent function on localhost for testing purposes.")
def run(
    target: Annotated[
        str,
        Argument(help="The name of the function within the [blue]`main.py`[/blue] file to use as cloud function."),
    ],
):
    from pydantic import ValidationError

    try:
        from encord_agents.core.settings import Settings

        Settings()
    except ValidationError as e:
        import sys

        import typer

        print(e, file=sys.stderr)
        raise typer.Abort()

    subprocess.run(
        f"functions-framework --target '{target}' --debug",
        cwd=Path.cwd(),
        shell=True,
    )


@app.command("deploy", help="Print example deploy command")
def deploy(
    target: Annotated[
        str,
        Argument(help="The name of the function within the [blue]`main.py`[/blue] file to use as cloud function."),
    ],
):
    panel = Panel(
        f"""
This is an example of how you can deploy the function to the cloud.
Make sure to authenticate `gcloud` and select the appropriate project first.

[blue][link=https://cloud.google.com/functions/docs/create-deploy-gcloud]https://cloud.google.com/functions/docs/create-deploy-gcloud[/link][/blue]

[magenta]```
cloud functions deploy {target} \\
    --entry-point {target} \\
    --runtime python311 \\
    --trigger-http \\
    --allow-unauthenticated \\
    --gen2 \\
    --region europe-west2 \\
    --set-secrets="ENCORD_SSH_KEY=SERVICE_ACCOUNT_KEY:latest"
```[/magenta]

Notice how we set secrets (the ssh key that the agent should use).
Please see the google docs for more details.
[blue][link=https://cloud.google.com/functions/docs/configuring/secrets]https://cloud.google.com/functions/docs/configuring/secrets[/link][/blue]
""",
        title="Example deployment script",
        expand=False,
    )
    rich.print(panel)
