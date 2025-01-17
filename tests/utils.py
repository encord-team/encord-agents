from enum import Enum


class AuthMode(Enum):
    KEY_CONTENT = "key_content"
    KEY_FILE = "key_file"
    BOTH = "both"
    NONE = "none"
