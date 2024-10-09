from pydantic import ValidationError

from encord_agents.core.settings import Settings


def verify_auth():
    try:
        Settings()
    except ValidationError as e:
        import sys

        import typer

        print(e, file=sys.stderr)
        raise typer.Abort()
