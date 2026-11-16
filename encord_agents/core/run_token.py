"""
Forward the agent run token Encord sends with editor agent calls.

Encord may send an opaque token in the `X-Encord-Agent-Run-Token` header. Agents built with this
library pass it back unchanged on their Encord requests, so Encord can attribute the changes an
agent makes to the run that caused them. Agents don't need to read or verify it.

The token is forwarded by clients from `get_user_client` (which the dependencies use). A client
you create yourself, or a thread you start yourself, doesn't forward it.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

_current_token: ContextVar[Optional[str]] = ContextVar("encord_agent_run_token", default=None)


def current_agent_run_token() -> Optional[str]:
    """The run token of the call being handled, if Encord sent one."""
    return _current_token.get()


@contextmanager
def forwarding_agent_run_token(token: Optional[str]) -> Iterator[None]:
    """While inside, Encord SDK calls made through `get_user_client` send `token`."""
    reset = _current_token.set((token or "").strip() or None)
    try:
        yield
    finally:
        _current_token.reset(reset)
