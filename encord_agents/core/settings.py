"""
Settings used throughout the module.

Note that central settings will be read via environment variables.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from encord_agents.exceptions import PrintableError


class Settings(BaseSettings):
    ssh_key_file: Optional[Path] = Field(validation_alias="ENCORD_SSH_KEY_FILE", default=None)
    """
    The path to the private ssh key file to authenticate with Encord.

    Either this or the `ENCORD_SSH_KEY` needs to be set for most use-cases.
    To setup a key with Encord, please see
    [the platform docs](https://docs.encord.com/platform-documentation/Annotate/annotate-api-keys).
    """
    ssh_key_content: Optional[str] = Field(validation_alias="ENCORD_SSH_KEY", default=None)
    """
    The content of the private ssh key file to authenticate with Encord.

    Either this or the `ENCORD_SSH_KEY` needs to be set for most use-cases.
    To setup a key with Encord, please see
    [the platform docs](https://docs.encord.com/platform-documentation/Annotate/annotate-api-keys).
    """
    domain: Optional[str] = Field(validation_alias="ENCORD_DOMAIN", default=None)

    @field_validator("ssh_key_content")
    @classmethod
    def check_key_content(cls, content: str | None) -> str | None:
        if content is None:
            return content

        if os.path.exists(content):
            raise PrintableError(
                f"The env variable `[blue]ENCORD_SSH_KEY[/blue]` (={content}) is set with a value that looks like a path and not ssh key content. Did you mean to set the `[blue]ENCORD_SSH_KEY_FILE[/blue]` environment variable with the private key file content directly?"
            )

        return content

    @field_validator("ssh_key_file")
    @classmethod
    def check_path_expand_and_exists(cls, path: Path | None) -> Path | None:
        if path is None:
            return path

        path = path.expanduser()

        if not path.is_file():
            raise PrintableError(
                "The env variable `[blue]ENCORD_SSH_KEY_FILE[/blue]` is set with a value that could not be found in the file system. Did you mean to set the `[blue]ENCORD_SSH_KEY[/blue]` environment variable with the private key file content directly?"
            )

        return path

    @model_validator(mode="after")
    def check_key(self: "Settings") -> "Settings":
        if not any(map(bool, [self.ssh_key_content, self.ssh_key_file])):
            raise PrintableError(
                f"Must specify either `[blue]ENCORD_SSH_KEY_FILE[/blue]` or `[blue]ENCORD_SSH_KEY[/blue]` env variables. If you don't have an ssh key, please refere to our docs:{os.linesep}[magenta]https://docs.encord.com/platform-documentation/Annotate/annotate-api-keys#creating-keys-using-terminal-powershell[/magenta]"
            )

        if all(map(bool, [self.ssh_key_file, self.ssh_key_content])):
            import warnings

            warnings.warn(
                "You have configured both the `ENCORD_SSH_KEY` and `ENCORD_SSH_KEY_FILE`. The `ENCORD_SSH_KEY` will take precedence."
            )

        return self

    @property
    def ssh_key(self) -> str:
        if self.ssh_key_content is None:
            if self.ssh_key_file is None:
                raise ValueError("Both ssh key content and ssh key file is None")
            self.ssh_key_content = self.ssh_key_file.read_text()
        return self.ssh_key_content
