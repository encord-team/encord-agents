import typer

from .gcp import app as gcp_app

app = typer.Typer()
app.add_typer(gcp_app, name="gcp")
