import os

from pydantic import ValidationError

from encord_agents.core.settings import Settings
from encord_agents.core.utils import get_user_client
from encord_agents.exceptions import PrintableError


def verify_auth():
    """
    FastAPI lifecycle start hook to fail early if ssh key is missing.

    **Example:**

    ```python
    from fastapi import FastAPI

    app = FastAPI(
        on_startup=[verify_auth]
    ```

    This will make the server fail early if auth is not setup.
    """
    from datetime import datetime, timedelta

    Settings()

    try:
        client = get_user_client()
        client.get_projects(created_after=datetime.now() - timedelta(days=1))
    except Exception:
        import traceback

        stack = traceback.format_exc()
        raise PrintableError(
            f"[red]Was able to read the SSH key, but couldn't list projects with Encord.[/red]. Original error was:{os.linesep}{stack}"
        )
