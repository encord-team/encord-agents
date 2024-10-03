from pathlib import Path

from pydantic import AfterValidator, Field
from pydantic_settings import BaseSettings
from typing_extensions import Annotated


def check_exists(key_file: Path) -> Path:
    assert key_file.is_file()
    return key_file


class Settings(BaseSettings):
    ssh_key_file: Annotated[Path, AfterValidator(check_exists)] = Field()
