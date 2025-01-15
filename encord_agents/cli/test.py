"""
CLI utilities for testing agents.
"""

import os
import re
import sys

import requests
import rich
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from typer import Argument, Option, Typer
from typing_extensions import Annotated

from encord_agents import FrameData
from encord_agents.core.constants import EDITOR_URL_PARTS_REGEX

app = Typer(
    name="test",
    help="Utility for testing agents",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


def parse_editor_url(editor_url: str) -> tuple[FrameData, str]:
    """
    Reads project_hash, data_hash, frame and domain from the editor url.

    Args:
        - editor_url: The url obtained from the Label Editor.

    Returns:
        The FrameData object and the domain of the url.
    """
    try:
        match = re.match(EDITOR_URL_PARTS_REGEX, editor_url)
        if match is None:
            raise typer.Abort()
        payload = match.groupdict()
        domain = payload.pop("domain")
        payload["frame"] = payload["frame"] or 0
        return FrameData.model_validate(payload), domain
    except Exception:
        rich.print(
            """Could not match url to the expected format.
Format is expected to be [blue]https://app.(us.)?encord.com/label_editor/[magenta]{project_hash}[/magenta]/[magenta]{data_hash}[/magenta](/[magenta]{frame}[/magenta])[/blue]
""",
            file=sys.stderr,
        )
        raise typer.Abort()


def hit_endpoint(endpoint: str, payload: FrameData, domain: str) -> None:
    with requests.Session() as sess:
        request = requests.Request(
            "POST",
            endpoint,
            json=payload.model_dump(mode="json", by_alias=True),
            headers={"Content-type": "application/json"},
        )
        prepped = request.prepare()

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), TimeElapsedColumn()) as progress:
            task = progress.add_task(f"Hitting agent endpoint `[blue]{prepped.url}[/blue]`")
            response = sess.send(prepped)
            progress.update(task, advance=1)
            time_elapsed = progress.get_time()

        table = Table()

        table.add_column("Property", style="bold")
        table.add_column("Value")

        table.add_section()
        table.add_row("[green]Request[/green]")
        table.add_row("url", prepped.url)
        body_json_str = prepped.body.decode("utf-8")  # type: ignore
        table.add_row("data", body_json_str)
        table_headers = ", ".join([f"'{k}': '{v}'" for k, v in prepped.headers.items()])
        table.add_row("headers", f"{{{table_headers}}}")

        table.add_section()
        table.add_row("[green]Response[/green]")
        table.add_row("status code", str(response.status_code))
        table.add_row("response", response.text)
        table.add_row("elapsed time", f"{time_elapsed / 1000 / 1000:.4f}s")

        table.add_section()
        table.add_row("[green]Utilities[/green]")
        editor_url = f"{domain}/label_editor/{payload.project_hash}/{payload.data_hash}/{payload.frame}"
        table.add_row("label editor", editor_url)

        headers = ["'{0}: {1}'".format(k, v) for k, v in prepped.headers.items()]
        str_headers = " -H ".join(headers)
        curl_command = f"curl -X {prepped.method} \\{os.linesep}  -H {str_headers} \\{os.linesep}  -d '{body_json_str}' \\{os.linesep}  '{prepped.url}'"
        table.add_row("curl", curl_command)

        rich.print(table)


@app.command("custom", short_help="Hit a custom endpoint for testing purposes")
def custom(
    endpoint: Annotated[str, Argument(help="Endpoint to hit with json payload")],
    editor_url: Annotated[str, Argument(help="Url copy/pasted from label editor")],
) -> None:
    """
    Hit a custom agents endpoint for testing an editor agent by copying the url from the Encord Label Editor.

    Given

        - The endpoint you wish to test
        - An editor url of the form [blue]`https://app.encord.com/label_editor/[green]{project_hash}[/green]/[green]{data_hash}[/green]/[green]{frame}[/green]`[/blue]
        - A [green]port[/green] (optional)

    The url [blue]http://localhost:[green]{port}[/green]/[green]{target}[/green][/blue] will be hit with a post request containing:
    {
        "projectHash": "[green]{project_hash}[/green]",
        "dataHash": "[green]{data_hash}[/green]",
        "frame": [green]frame[/green] or 0
    }
    """
    payload, domain = parse_editor_url(editor_url)
    hit_endpoint(endpoint, payload, domain)


@app.command(
    "local",
    short_help="Hit a localhost agents endpoint for testing",
)
def local(
    target: Annotated[
        str,
        Argument(help="Name of the localhost endpoint to hit ('http://localhost/{target}')"),
    ],
    editor_url: Annotated[str, Argument(help="Url copy/pasted from label editor")],
    port: Annotated[int, Option(help="Local host port to hit")] = 8080,
) -> None:
    """Hit a localhost agents endpoint for testing an agent by copying the url from the Encord Label Editor over.

    Given

        - An editor url of the form [blue]`https://app.encord.com/label_editor/[green]{project_hash}[/green]/[green]{data_hash}[/green]/[green]{frame}[/green]`[/blue]
        - A [green]port[/green] (optional)

    The url [blue]http://localhost:[green]{port}[/green]/[green]{target}[/green][/blue] will be hit with a post request containing:
    {
        "projectHash": "[green]{project_hash}[/green]",
        "dataHash": "[green]{data_hash}[/green]",
        "frame": [green]frame[/green] or 0
    }
    """
    payload, domain = parse_editor_url(editor_url)

    if target and not target[0] == "/":
        target = f"/{target}"
    endpoint = f"http://localhost:{port}{target}"

    hit_endpoint(endpoint, payload, domain)
