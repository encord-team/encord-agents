import sys
import threading
import time
from typing import Any
from uuid import UUID

from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from .runner import Runner


class RunnerBundle:
    def __init__(self, runners: dict[str, Runner] | None = None, max_progress_cols: int = 2):
        self.max_progress_cols = max_progress_cols
        self.runners = runners or {}
        self.threads: list[threading.Thread] = []
        self.stop_event = threading.Event()

    def add_runner(self, key: str, runner: Runner, override: bool = False) -> None:
        if key in self.runners and not override:
            raise ValueError(f"Runner with key {key} already exists")
        self.runners[key] = runner

    def _run_thread(self, key: str, runner: Runner, **kwargs: Any) -> None:
        try:
            runner(**kwargs)
        except KeyboardInterrupt:
            # Individual threads shouldn't handle KeyboardInterrupt
            pass
        except Exception as e:
            print(f"Runner '{key}' failed with error: {e}")
        finally:
            # Check if we should signal other threads to stop
            if not self.stop_event.is_set():
                print(f"Runner '{key}' completed")

    def __call__(self, project_hash: str | UUID | None = None, **kwargs: Any) -> None:
        """
        Execute all runners in separate threads with the same arguments.
        Listen for keyboard interrupts to stop all threads.

        Args:
            project_hash: The project hash to pass to all runners
            **kwargs: Additional arguments to pass to all runners
        """
        # Reset state for new run
        self.threads = []
        self.stop_event.clear()

        # Create a grid layout for the panels
        num_cols = min(len(self.runners), self.max_progress_cols)
        if num_cols == 0:
            # No runners to display
            return

        # Create a grid table to organize the panels
        grid = Table.grid(padding=(0, 2))

        # Add the appropriate number of columns to the grid
        for _ in range(num_cols):
            grid.add_column()

        # Create panels for each runner and add them to the grid
        tables = []
        panels = []
        for key, runner in self.runners.items():
            table = Table.grid()
            tables.append(table)

            panel = Panel(table, title=f"[bold]{key}[/bold]", border_style="blue", padding=(2, 2))
            panels.append(panel)

        # Arrange panels in rows based on the number of columns
        row = []
        for i, panel in enumerate(panels):
            row.append(panel)
            if (i + 1) % num_cols == 0 or i == len(tables) - 1:
                # Add the current row to the grid and start a new one
                grid.add_row(*row)
                row = []

        with Live(grid, refresh_per_second=1) as live:
            for i, (key, runner) in enumerate(self.runners.items()):
                thread_kwargs = kwargs.copy()
                if project_hash is not None:
                    thread_kwargs["project_hash"] = project_hash
                    thread_kwargs["live"] = live
                    thread_kwargs["table"] = tables[i]

                thread = threading.Thread(
                    target=self._run_thread, args=(key, runner), kwargs=thread_kwargs, name=f"Runner-{key}"
                )
                self.threads.append(thread)
                thread.start()

            # Wait for all threads to complete or for keyboard interrupt
            try:
                # Keep the main thread alive until all worker threads are done
                while any(thread.is_alive() for thread in self.threads):
                    time.sleep(0.5)
            except KeyboardInterrupt:
                print("\nKeyboard interrupt received. Stopping all runners...")
                self.stop_event.set()

                # Give threads a chance to clean up
                for thread in self.threads:
                    if thread.is_alive():
                        thread.join(timeout=5.0)

                print("All runners stopped")
