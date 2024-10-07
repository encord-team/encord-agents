import subprocess
from pathlib import Path
from shutil import copy, copytree
from typing import Optional

import rich
from rich.panel import Panel
from typer import Abort, Argument, Option, Typer
from typing_extensions import Annotated

app = Typer(
    name="encord-gcp-agent",
    help="Utility to setup and run GCP agents locally",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

_SOURCE_CODE_PATH = Path(__file__).parent.parent

_TEMPLATE_CONTENT_W_ASSET = """
from encord.objects.ontology_labels_impl import LabelRowV2

from encord_agents.gcp_functions import FrameData, editor_agent


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

from encord_agents.gcp_functions import FrameData, editor_agent


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


def make_clean_build_dir(destination: Path):
    destination.mkdir()
    lib_path = destination / "encord_agtents"
    lib_path.mkdir()

    copytree(_SOURCE_CODE_PATH / "core", lib_path / "core")
    copytree(_SOURCE_CODE_PATH / "gcp_functions", lib_path / "gcp_functions")


def write_dependencies(destination: Path):
    content = subprocess.run(
        "poetry export --without-hashes --format=requirements.txt --no-cache",
        capture_output=True,
        shell=True,
    )
    with (destination / "requirements.txt").open("w") as f:
        f.write(content.stdout.decode("utf-8"))


def move_src(src_file: Path, destination: Path):
    dest_file = destination / "main.py"
    copy(src_file, dest_file)


def write_template_file(destination: Path, with_asset: bool):
    (destination / "main.py").write_text(
        _TEMPLATE_CONTENT_W_ASSET if with_asset else _TEMPLATE_CONTENT_WO_ASSET
    )


@app.command(
    "build",
    help="Build a fresh directory with the necessary files for publishing on GCP.",
)
def build(
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
    destination = Path.cwd() / project_name
    if destination.exists():
        raise Abort("Cannot create project with that name. It already exists.")

    make_clean_build_dir(destination)
    write_dependencies(destination)
    if src_file is not None:
        move_src(src_file, destination)
    else:
        write_template_file(destination, with_asset)


@app.command("run", help="Run the agent function on localhost for testing purposes.")
def run(
    target: Annotated[
        str,
        Argument(
            help="The name of the function within the [blue]`main.py`[/blue] file to use as cloud function."
        ),
    ]
):
    subprocess.run(
        f"functions-framework --target '{target}' --debug",
        cwd=Path.cwd(),
        shell=True,
    )


@app.command("deploy", help="Print example deploy command")
def deploy(
    target: Annotated[
        str,
        Argument(
            help="The name of the function within the [blue]`main.py`[/blue] file to use as cloud function."
        ),
    ]
):
    panel = Panel(
        f"""
This is an example of how you can deploy the function to the cloud.
Make sure to authenticate `gcloud` and select the appropriate project first.
[blue]https://cloud.google.com/functions/docs/create-deploy-gcloud[/blue]

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
[blue]https://cloud.google.com/functions/docs/configuring/secrets[/blue]
""",
        title="Example deployment script",
        expand=False,
    )
    rich.print(panel)


@app.command(
    "test",
    help="Test a running cloud function against the frame you are currently looking at in the Label Editor",
)
def test_frame(
    target: Annotated[
        str,
        Argument(
            help="The name of the function within the [blue]`main.py`[/blue] file to use as cloud function."
        ),
    ],
    url: Annotated[
        str,
        Argument(
            help="Paste the url that you're currently looking at in the Label Editor."
        ),
    ],
):
    import requests

    splits = url.split("/")
    idx = splits.index("label_editor")
    project_hash, data_hash, *rest = splits[idx + 1 :]
    frame = int(rest[0]) if rest else 0
    payload = {"projectHash": project_hash, "dataHash": data_hash, "frame": frame}
    response = requests.post(
        f"http://localhost:8080/{target}",
        json=payload,
        headers={"Content-type": "application/json"},
    )
    print(response.status_code)
    print(response.content.decode("utf-8"))
