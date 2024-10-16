"""
Main file for the command line interface.

Collects all the sub commands of the CLI.

Example usage:

    encord-agents --help

"""

import typer

from .gcp import app as gcp_app
from .test import app as test_app

app = typer.Typer(rich_markup_mode="rich")
app.add_typer(gcp_app, name="gcp")
app.add_typer(test_app, name="test")
