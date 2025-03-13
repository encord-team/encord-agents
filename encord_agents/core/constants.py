ENCORD_DOMAIN_REGEX = (
    r"^https:\/\/(?:(?:cord-ai-development--[\w\d]+-[\w\d]+\.web.app)|(?:(?:dev|staging|app)\.(us\.)?encord\.com))$"
)

EDITOR_URL_PARTS_REGEX = r"(?P<domain>https:\/\/app.(us\.)?encord.com)\/label_editor\/(?P<projectHash>.*?)\/(?P<dataHash>[\w\d]{8}-[\w\d]{4}-[\w\d]{4}-[\w\d]{4}-[\w\d]{12})(\/(?P<frame>\d+))?\??"

TEST_REQUEST_PAYLOAD: dict[str, str | int] = {
    "projectHash": "00000000-0000-0000-0000-000000000000",
    "dataHash": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "frame": 10,
}
