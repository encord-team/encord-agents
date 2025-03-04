from uuid import UUID


def try_coerce_UUID(candidate_uuid: str | UUID) -> bool:
    """Try to coerce to UUID. Return true if possible otherwise false"""
    if isinstance(candidate_uuid, UUID):
        return True
    try:
        UUID(candidate_uuid)
        return True
    except ValueError:
        return False
