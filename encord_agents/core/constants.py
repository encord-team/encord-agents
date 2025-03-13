ENCORD_DOMAIN_REGEX = (
    r"^https:\/\/(?:(?:cord-ai-development--[\w\d]+-[\w\d]+\.web.app)|(?:(?:dev|staging|app)\.(us\.)?encord\.com))$"
)

EDITOR_URL_PARTS_REGEX = r"(?P<domain>https:\/\/app.(us\.)?encord.com)\/label_editor\/(?P<projectHash>.*?)\/(?P<dataHash>[\w\d]{8}-[\w\d]{4}-[\w\d]{4}-[\w\d]{4}-[\w\d]{12})(\/(?P<frame>\d+))?\??"

TEST_REQUEST_PAYLOAD: dict[str, str | int] = {
    "projectHash": "12345678-1234-5678-1234-123456789012",
    "dataHash": "abcdefab-abcd-abcd-abcd-abcdefabcdef",
    "frame": 10,
}
