"""
CLI utilities for testing agents.
"""

import os

from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from typer import Argument, Option, Typer
from typing_extensions import Annotated

app = Typer(
    name="test",
    help="Utility for testing agents",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@app.command(
    "local",
    short_help="Hit a localhost agents endpoint for testing",
)
def local(
    target: Annotated[
        str,
        Argument(help="Name of the localhost endpoint to hit ('http://localhost/{target}')"),
    ],
    url: Annotated[str, Argument(help="Url copy/pasted from label editor")],
    port: Annotated[int, Option(help="Local host port to hit")] = 8080,
) -> None:
    """Hit a localhost agents endpoint for testing an agent by copying the url from the Encord Label Editor over.

    Given

        - A url of the form [blue]`https://app.encord.com/label_editor/[green]{project_hash}[/green]/[green]{data_hash}[/green]/[green]{frame}[/green]`[/blue]
        - A [green]target[/green] endpoint
        - A [green]port[/green] (optional)

    The url [blue]http://localhost:[green]{port}[/green]/[green]{target}[/green][/blue] will be hit with a post request containing:
    {
        "projectHash": "[green]{project_hash}[/green]",
        "dataHash": "[green]{data_hash}[/green]",
        "frame": [green]frame[/green] or 0
    }
    """
    import re
    import sys
    from pprint import pprint

    import requests
    import rich
    import typer

    parts_regex = r"https:\/\/app.encord.com\/label_editor\/(?P<projectHash>.*?)\/(?P<dataHash>[\w\d]{8}-[\w\d]{4}-[\w\d]{4}-[\w\d]{4}-[\w\d]{12})(/(?P<frame>\d+))?\??"

    try:
        match = re.match(parts_regex, url)
        if match is None:
            raise typer.Abort()

        payload = match.groupdict()
        payload["frame"] = payload["frame"] or 0
    except Exception:
        rich.print(
            """Could not match url to the expected format.
Format is expected to be [blue]https://app.encord.com/label_editor/[magenta]{project_hash}[/magenta]/[magenta]{data_hash}[/magenta](/[magenta]{frame}[/magenta])[/blue]
""",
            file=sys.stderr,
        )
        raise typer.Abort()

    if target and not target[0] == "/":
        target = f"/{target}"

    with requests.Session() as sess:
        request = requests.Request(
            "POST",
            f"http://localhost:{port}{target}",
            json=payload,
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
        editor_url = (
            f"https://app.encord.com/label_editor/{payload['projectHash']}/{payload['dataHash']}/{payload['frame']}"
        )
        table.add_row("label editor", editor_url)

        headers = ["'{0}: {1}'".format(k, v) for k, v in prepped.headers.items()]
        str_headers = " -H ".join(headers)
        curl_command = f"curl -X {prepped.method} \\{os.linesep}  -H {str_headers} \\{os.linesep}  -d '{body_json_str}' \\{os.linesep}  '{prepped.url}'"
        table.add_row("curl", curl_command)

        rich.print(table)
