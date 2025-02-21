from rich.progress import ProgressColumn, Task
from rich.text import Text


class TaskSpeedColumn(ProgressColumn):
    """Renders human readable transfer speed."""

    def __init__(self, unit: str = "tasks") -> None:
        super().__init__()
        self.unit = unit

    def _format_speed(self, speed: float) -> str:
        resolution = "s" if speed > 1 / 60 else "m" if speed > 1 / 3600 else "h"
        if resolution == "m":
            speed /= 60
        elif resolution == "h":
            speed /= 3600
        return f"{speed:.2f} {self.unit}/{resolution}"

    def render(self, task: Task) -> Text:
        """Show data transfer speed."""
        speed = task.finished_speed or task.speed
        if speed is None:
            return Text("?", style="progress.data.speed")

        return Text(self._format_speed(speed), style="progress.data.speed")
