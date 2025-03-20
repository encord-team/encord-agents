ENCORD_DOMAIN_REGEX = (
    r"^https:\/\/(?:(?:cord-ai-development--[\w\d]+-[\w\d]+\.web.app)|(?:(?:dev|staging|app)\.(us\.)?encord\.com))$"
)

EDITOR_URL_PARTS_REGEX = r"(?P<domain>https://app\.(us\.)?encord\.com)/label_editor/(?P<projectHash>[\w\d-]{36})/(?P<dataHash>[\w\d-]{36})(/(?P<frame>\d+))?(/(?P<additional_path>[^?]*))?(\?(?P<query>.*))?"
EDITOR_TEST_REQUEST_HEADER = "X-Encord-Editor-Agent"
