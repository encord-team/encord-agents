from uuid import UUID


def try_coerce_UUID(candidate_uuid: str | UUID) -> UUID | None:
    """Try to coerce to UUID. Return UUID if possible otherwise None"""
    if isinstance(candidate_uuid, UUID):
        return candidate_uuid
    try:
        return UUID(candidate_uuid)
    except ValueError:
        return None
