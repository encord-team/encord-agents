ENCORD_DOMAIN_REGEX = (
    r"^https:\/\/(?:(?:cord-ai-development--[\w\d]+-[\w\d]+\.web.app)|(?:(?:dev|staging|app)\.(us\.)?encord\.com))$"
)

EDITOR_URL_PARTS_REGEX = r"(?P<domain>https:\/\/app\.(us\.)?encord\.com)\/label_editor\/(?P<projectHash>[\w\d-]+)\/(?P<dataHash>[\w\d]{8}-[\w\d]{4}-[\w\d]{4}-[\w\d]{4}-[\w\d]{12})(\/(?P<frame>\d+))?(\/(?P<mode>[01]))?(\/(?P<reviewId>\d+))?\/?(\?|$)"
