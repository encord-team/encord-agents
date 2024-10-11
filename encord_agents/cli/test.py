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
    import re
    from pprint import pprint

    import requests

    parts_regex = r"https:\/\/app.encord.com\/label_editor\/(?P<projectHash>.*?)\/(?P<dataHash>[\w\d]{8}-[\w\d]{4}-[\w\d]{4}-[\w\d]{4}-[\w\d]{12})(/(?P<frame>\d+))?\??"
    editor_url = "https://app.encord.com/label_editor/a1240d34-e4e7-4f9c-b62c-d09b3dfd010e/5f68f13e-3931-4585-ad80-e15dd2c501b5/0"  # @param { type : "string" }

    # @markdown Upon a 200 response, refresh the label editor to see the result.

    try:
        payload = re.match(parts_regex, editor_url).groupdict()
        payload["frame"] = payload["frame"] or 0
    except:
        import sys

        import typer

        print(
            "Was not able to parse the url. Please make sure that it follows the format 'label_editor/project_hash/data_hash/frame'",
            file=sys.stderr,
        )
        raise typer.Abort()

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
