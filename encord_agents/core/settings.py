"""
Settings used throughout the module.

Note that central settings will be read via environment variables.
"""
import os

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from encord_agents.exceptions import PrintableError, format_printable_error


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

    @field_validator("ssh_key_file")
    @classmethod
    def check_path_expand_and_exists(cls, path: Path | None):
        if path is None:
            return path

        path = path.expanduser()
        assert path.is_file(), f"Provided ssh key file (ENCORD_SSH_KEY_FILE: '{path}') does not exist"
        return path

    @model_validator(mode="after")
    @format_printable_error
    def check_key(self):
        if not any(
            map(bool, [self.ssh_key_content, self.ssh_key_file])
        ): 
            raise PrintableError(f"Must specify either `[blue]ENCORD_SSH_KEY_FILE[/blue]` or `[blue]ENCORD_SSH_KEY[/blue]` env variables. If you don't have an ssh key, please refere to our docs:{os.linesep}[magenta]https://docs.encord.com/platform-documentation/Annotate/annotate-api-keys#creating-keys-using-terminal-powershell[/magenta]")
        # TODO help people find their way through ssh keys
        return self

    @property
    def ssh_key(self) -> str:
        return self.ssh_key_content if self.ssh_key_content else self.ssh_key_file.read_text()
