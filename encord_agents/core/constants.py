ENCORD_DOMAIN_REGEX = (
    r"^https:\/\/(?:(?:cord-ai-development--[\w\d]+-[\w\d]+\.web.app)|(?:(?:dev|staging|app)\.(us\.)?encord\.com))$"
)

EDITOR_URL_PARTS_REGEX = r"(?P<domain>https://app\.(us\.)?encord\.com)/label_editor/(?P<projectHash>[\w\d-]{36})/(?P<dataHash>[\w\d-]{36})(/(?P<frame>\d+))?(/(?P<additional_path>[^?]*))?(\?(?P<query>.*))?"
EDITOR_TEST_REQUEST_HEADER = "X-Encord-Editor-Agent"
HEADER_CLOUD_TRACE_CONTEXT = "X-Cloud-Trace-Context"
# Encord signs every request it makes to a configured URL -- both the task-ready
# notifications from an agent stage and its calls to a custom agent endpoint.
WEBHOOK_SIGNATURE_HEADER = "X-Encord-Signature"
WEBHOOK_TIMESTAMP_HEADER = "X-Encord-Timestamp"
# Cap on `decision`, the pathway name a custom agent returns to route its task.
# Encord silently drops a longer one and takes the default pathway; fail loudly here.
MAX_DECISION_LENGTH = 256
