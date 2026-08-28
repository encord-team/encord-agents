import sys

from encord.orm.workflow import WorkflowStageType
from typer import Typer

from encord_agents.core.settings import Settings

app = Typer(
    name="print",
    help="Utility to print system info, e.g., for bug reporting.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@app.command(name="agent-nodes")
def print_agent_nodes(project_hash: str) -> None:
    """
    Prints agent nodes from project.

    Given the project hash, loads the project and prints the agent nodes.

    Args:
        project_hash: The project hash for which to print agent nodes.

    """
    import rich
    from encord.configs import ENCORD_DOMAIN
    from encord.exceptions import AuthenticationError, AuthorisationError
    from rich.markup import escape

    from encord_agents.core.utils import get_user_client

    settings = Settings()
    client = get_user_client(settings)
    # Report the domain we actually talked to, so a wrong-environment failure cannot
    # masquerade as a permissions or key problem.
    domain = settings.domain or ENCORD_DOMAIN

    try:
        project = client.get_project(project_hash)
    except AuthorisationError:
        rich.print(
            f"You do not seem to have access to project with project hash "
            f"`[purple]{project_hash}[/purple]` on domain `[blue]{domain}[/blue]`."
        )
        rich.print(
            "If the project lives in a different Encord environment, set the "
            "`[blue]ENCORD_DOMAIN[/blue]` environment variable (for example "
            "`https://api.us.encord.com`) and try again."
        )
        exit()
    except AuthenticationError as e:
        rich.print(f"Could not authenticate against domain `[blue]{domain}[/blue]`: {escape(str(e))}")
        rich.print(
            "If your ssh key belongs to a different Encord environment, set the "
            "`[blue]ENCORD_DOMAIN[/blue]` environment variable (for example "
            "`https://api.us.encord.com`) and try again."
        )
        exit()

    agent_nodes = [
        f'AgentStage(title="{n.title}", uuid="{n.uuid}")'
        for n in project.workflow.stages
        if n.stage_type == WorkflowStageType.AGENT
    ]
    if not agent_nodes:
        print("Project does not have any agent nodes.")
        return

    for node in agent_nodes:
        rich.print(node)


@app.command(name="system-info")
def print_system_info() -> None:
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
