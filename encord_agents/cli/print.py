import sys
from typer import Typer

app = Typer(
    name="print",
    help="Utility to print system info, e.g., for bug reporting.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@app.command(name="system-info")
def print_system_info():
        """
            [bold]Prints[/bold] the information of the system for the purpose of bug reporting.
            """
        import platform
        print("System Information:")
        uname = platform.uname()
        print(f"\tSystem: {uname.system}")
        print(f"\tRelease: {uname.release}")
        print(f"\tMachine: {uname.machine}")
        print(f"\tProcessor: {uname.processor}")
        print(f"\tPython: {sys.version}")

        import encord_agents
        print(f"encord-agents version: {encord_agents.__version__}")


