# Default CORS origins: the production Encord apps only. Editor agents act with the
# agent author's credentials, so any other frontend must be opted into explicitly
# with `custom_cors_regex` (or `allow_origin_regex` on the middleware).
ENCORD_DOMAIN_REGEX = r"^https:\/\/app\.(?:us\.)?encord\.com$"

# Slashes escaped so the link checker doesn't parse this as a URL
EDITOR_URL_PARTS_REGEX = r"(?P<domain>https:\/\/app\.(us\.)?encord\.com)/label_editor/(?P<projectHash>[\w\d-]{36})/(?P<dataHash>[\w\d-]{36})(/(?P<frame>\d+))?(/(?P<additional_path>[^?]*))?(\?(?P<query>.*))?"
EDITOR_TEST_REQUEST_HEADER = "X-Encord-Editor-Agent"
HEADER_CLOUD_TRACE_CONTEXT = "X-Cloud-Trace-Context"
# Sent by the Encord editor with editor agent calls.
AGENT_RUN_TOKEN_HEADER = "X-Encord-Agent-Run-Token"
# Encord signs every request it makes to a configured URL -- both the task-ready
# notifications from an agent stage and its calls to a custom agent endpoint.
WEBHOOK_SIGNATURE_HEADER = "X-Encord-Signature"
WEBHOOK_TIMESTAMP_HEADER = "X-Encord-Timestamp"
# Cap on `decision`, the pathway name a custom agent returns to route its task.
# Encord silently drops a longer one and takes the default pathway; fail loudly here.
MAX_DECISION_LENGTH = 256
