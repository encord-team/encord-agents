ENCORD_DOMAIN_REGEX = (
    r"^https:\/\/(?:(?:cord-ai-development--[\w\d]+-[\w\d]+\.web.app)|(?:(?:dev|staging|app)\.(us\.)?encord\.com))$"
)

EDITOR_URL_PARTS_REGEX = r"(?P<domain>https:\/\/app.(us\.)?encord.com)\/label_editor\/(?P<projectHash>.*?)\/(?P<dataHash>[\w\d]{8}-[\w\d]{4}-[\w\d]{4}-[\w\d]{4}-[\w\d]{12})(\/(?P<frame>\d+))?\??"

TEST_REQUEST_PAYLOAD: dict[str, str | int] = {
    "projectHash": "027e0c65-c53f-426d-9f02-04fafe8bd80e",
    "dataHash": "038ed92d-dbe8-4991-a3aa-6ede35d6e62d",
    "frame": 10,
}
