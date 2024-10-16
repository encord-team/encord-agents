"""
Settings used throughout the module.

Note that central settings will be read via environment variables.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


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

    @model_validator(mode="after")
    def check_key(self):
        assert any(
            map(bool, [self.ssh_key_content, self.ssh_key_file])
        ), "Must specify either `ENCORD_SSH_KEY_FILE` or `ENCORD_SSH_KEY` env variables. "
        # TODO help people find their way through ssh keys
        return self

    @property
    def ssh_key(self) -> str:
        return self.ssh_key_content if self.ssh_key_content else self.ssh_key_file.read_text()
