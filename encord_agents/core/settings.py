import logging
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    ssh_key_file: Optional[Path] = Field(
        validation_alias="ENCORD_SSH_KEY_FILE", default=None
    )
    ssh_key_content: Optional[str] = Field(
        validation_alias="ENCORD_SSH_KEY", default=None
    )

    @model_validator(mode="after")
    def check_key(self):
        assert any(
            map(bool, [self.ssh_key_content, self.ssh_key_file])
        ), "Must specify either `ENCORD_SSH_KEY_FILE` or `ENCORD_SSH_KEY` env variables. "
        # TODO help people find their way through ssh keys
        return self

    @property
    def ssh_key(self) -> str:
        return (
            self.ssh_key_content
            if self.ssh_key_content
            else self.ssh_key_file.read_text()
        )
