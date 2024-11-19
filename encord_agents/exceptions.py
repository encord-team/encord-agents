import io

from rich.console import Console
from rich.text import Text


class PrintableError(ValueError):
    def __str__(self) -> str:
        output = io.StringIO()
        console = Console(
            force_terminal=True,
            color_system="auto",
            file=output,
            force_interactive=False,
            width=1000,
        )

        text_obj = Text.from_markup(self.args[0])
        console.print(text_obj, end="")
        return output.getvalue()
