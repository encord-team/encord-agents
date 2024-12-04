"""
Main file for the command line interface.

Collects all the sub commands of the CLI.

Example usage:

    encord-agents --help

"""

import typer

from .print import app as print_app
from .test import app as test_app

app = typer.Typer(rich_markup_mode="rich")
app.add_typer(test_app, name="test")
app.add_typer(print_app, name="print")


@app.callback(invoke_without_command=True)
def version(
    version_: bool = typer.Option(False, "--version", "-v", "-V", help="Print the current version of Encord Agents"),
) -> None:
    if version_:
        import rich

        from encord_agents import __version__ as ea_version

        rich.print(f"[purple]encord-agents[/purple] version: [green]{ea_version}[/green]")
        exit()
