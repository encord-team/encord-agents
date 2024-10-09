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
        Argument(
            help="Name of the localhost endpoint to hit ('http://localhost/{target}')"
        ),
    ],
    url: Annotated[str, Argument(help="Url copy/pasted from label editor")],
    port: Annotated[int, Option(help="Local host port to hit")] = 8080,
):
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
    from pprint import pprint

    import requests

    splits = url.split("/")
    idx = splits.index("label_editor")
    project_hash, data_hash, *rest = splits[idx + 1 :]
    frame = int(rest[0]) if rest else 0
    payload = {"projectHash": project_hash, "dataHash": data_hash, "frame": frame}
    response = requests.post(
        f"http://localhost:{port}/{target}",
        json=payload,
        headers={"Content-type": "application/json"},
    )
    print(response.status_code)
    try:
        pprint(response.json())
    except:
        print(response.content.decode("utf-8"))
