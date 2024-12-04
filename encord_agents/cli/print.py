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
    from encord.exceptions import AuthorisationError
    from encord.user_client import EncordUserClient

    _ = Settings()
    client = EncordUserClient.create_with_ssh_private_key()
    try:
        project = client.get_project(project_hash)
    except AuthorisationError:
        rich.print(f"You do not seem to have access to project with project hash `[purple]{project_hash}[/purple]`")
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
