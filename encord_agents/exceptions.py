import io
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

from rich.console import Console
from rich.text import Text


class PrintableError(ValueError): ...


Params = ParamSpec("Params")
RetType = TypeVar("RetType")


def format_printable_error(fn: Callable[Params, RetType]) -> Callable[Params, RetType]:
    @wraps(fn)
    def wrapper(*args: Params.args, **kwargs: Params.kwargs):
        try:
            return fn(*args, **kwargs)
        except PrintableError as err:
            output = io.StringIO()
            console = Console(
                force_terminal=True,
                color_system="auto",
                file=output,
                force_interactive=False,
                width=1000,
            )

            text_obj = Text.from_markup(err.args[0])
            console.print(text_obj, end="")
            err.args = (output.getvalue(),)
            raise

    return wrapper
