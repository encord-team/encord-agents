from pydantic import ValidationError

from encord_agents.core.settings import Settings


def verify_auth():
    """
    FastAPI lifecycle start hook to fail early if ssh key is missing.
    """
    try:
        Settings()
    except ValidationError as e:
        import sys

        import typer

        print(e, file=sys.stderr)
        raise typer.Abort()
