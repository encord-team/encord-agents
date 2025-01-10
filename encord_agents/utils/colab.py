import html
import os
import subprocess
import sys
from pathlib import Path


def is_running_on_colab() -> bool:
    pre_conditions: bool = all(
        [
            "google.colab" in sys.modules,
            os.getenv("COLAB_BACKEND_VERSION") is not None,
        ]
    )
    if not pre_conditions:
        return False
    try:
        from google.colab import runtime

        return True
    except ModuleNotFoundError:
        return False


IS_COLAB = is_running_on_colab()

DARK_LOGO = "https://storage.googleapis.com/docs-media.encord.com/Primary%20logo%20Dark%20mode%20-%20Horizontal.png"
LIGHT_LOGO = "https://storage.googleapis.com/docs-media.encord.com/Primary%20logo%20Light%20mode%20-%20Horizontal.png"


def generate_public_private_keypair(public_key_path: Path = Path.cwd() / "temporary_key.pub") -> tuple[Path, Path]:
    """
    Will look for the key. If it doesn't exist, it will create it along with a private key.
    returns: public and private key paths, respectively.

    Args:
        public_key_path: the path to where the public key should be stored.
            Note that it must have the suffix ".pub".

    Returns: (public_key_path, private_key_path) The private key path will be
        the same as the public but without the ".pub" suffix.

    """
    assert public_key_path.suffix == ".pub"
    private_key_path = public_key_path.with_suffix("")
    if not (public_key_path.is_file() and private_key_path.is_file()):
        if public_key_path.is_file():
            public_key_path.unlink()
        if private_key_path.is_file():
            private_key_path.unlink()
        devnull = subprocess.DEVNULL
        subprocess.run(
            f'ssh-keygen -t ed25519 -f {private_key_path} -N "" -q',
            shell=True,
            stdout=devnull,
        )
        print("We have created a public/private ssh key pair for you.")
    return public_key_path, private_key_path


def generate_public_private_key_pair_with_instructions() -> tuple[Path, Path]:
    """
    A utility function to create an ssh key and print instructions for how
    to associate it with the Encord platform.

    Args:
        domain: Api endpoint. Should not have to be set.

    Returns:
        A tuple of a private and a public key path.

    """
    try:
        from IPython.display import HTML, display
    except ModuleNotFoundError:
        import typer
        from rich.console import Console
        from rich.panel import Panel

        console = Console(stderr=True)
        console.print(
            Panel(
                "You have imported `encord_agents.utils.colab.generate_public_private_key_pair_with_instructions` outside a notebook. Consider using the `generate_public_private_keypair` function instead..",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        raise typer.Abort()

    public_key_path, private_key_path = generate_public_private_keypair()
    public_key_content = html.escape(public_key_path.read_text())
    private_key_content = html.escape(private_key_path.read_text())
    colab_tip = (
        """
        <p>
            <strong>Hint:</strong> Consider 
            <button onclick="copyPrivateKey()">
                <svg stroke="purple" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" height="1em" width="1em" xmlns="http://www.w3.org/2000/svg"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                Copying <i>private key</i> to clipboard
            </button>
            and adding it to the <span style="color: #8082e6;"><span><svg viewBox="0 0 24 24" style="height: 30px; width: 30px;"><path fill="currentColor" d="M21 18H15V15H13.3C12.2 17.4 9.7 19 7 19C3.1 19 0 15.9 0 12S3.1 5 7 5C9.7 5 12.2 6.6 13.3 9H24V15H21V18M17 16H19V13H22V11H11.9L11.7 10.3C11 8.3 9.1 7 7 7C4.2 7 2 9.2 2 12S4.2 17 7 17C9.1 17 11 15.7 11.7 13.7L11.9 13H17V16M7 15C5.3 15 4 13.7 4 12S5.3 9 7 9 10 10.3 10 12 8.7 15 7 15M7 11C6.4 11 6 11.4 6 12S6.4 13 7 13 8 12.6 8 12 7.6 11 7 11Z"></path></svg></span> Secrets</span> in the left sidebar with the name: <pre style="display: inline-block;">ENCORD_SSH_KEY</pre>. Then, you won't have to add the public key to the Encord platform next time.
        </p>
    """
        if IS_COLAB
        else ""
    )

    display(
        HTML(
            f"""
    <script>
        function copyToClipboard() {{ 
            console.log({{tmp: "{public_key_content.strip()}"}}); 
            navigator.clipboard.writeText(`{public_key_content.strip()}`); 
        }};
        function copyPrivateKey() {{ 
            navigator.clipboard.writeText(`{private_key_content.strip()}`); 
        }};
    </script>
    <style>
        .encord-logo {{
            display: inline-block;
            width: 60px;
            height: 16px;
            background-size: contain;
            background-repeat: no-repeat;
            background-position: bottom;
        }}
        html .encord-logo {{
            background-image: url('{LIGHT_LOGO}');
        }}
        html[theme="light"] .encord-logo {{
            background-image: url('{LIGHT_LOGO}');
        }}
        html[theme="dark"] .encord-logo {{
            background-image: url('{DARK_LOGO}');
        }}
    </style>
    <div style="border-radius: 5px; border: dashed 1px yellow; padding: 1rem;">
        <p>
            <strong>NB</strong> Please follow these steps to link this notebook to your <span class="encord-logo"></span> Accont.
        </p>
        <ol style="line-height: 2em;">
            <li>Click the button to copy your public
                <button onclick="copyToClipboard()">
                    <svg stroke="purple" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" height="1em" width="1em" xmlns="http://www.w3.org/2000/svg"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    Copy public key to clipboard
                </button>
                <small>OR manually copy this key content: 
                    <p style="color: #8082e6;">
                        <pre>{public_key_content.strip()}</pre>
                    </p>
                </small>
            </li>
            <li>Go to the <a style="color: #8082e6;" href="https://app.encord.com/settings/public-keys" target="_blank">settings panel</a></li>
            <li>Click the <span style="color: #8082e6; border: solid 0.5px #8082e6; border-radius: 2px; padding: 1px 3px;">+ New Key</span> button</li>
            <li>Give the key a title</li>
            <li>Paste the copied public key to the second text field.</li>
            <li>Click the <span style="color: #8082e6; border: solid 0.5px #8082e6; border-radius: 2px; padding: 1px 3px;">Create</span> button</li>
        </ol>
        {colab_tip}
    </div>
    """
        )  # type: ignore [no-untyped-call]
    )
    return private_key_path, public_key_path
