import itertools
from typing import Iterable, TypeVar
from uuid import UUID


def try_coerce_UUID(candidate_uuid: str | UUID) -> UUID | None:
    """Try to coerce to UUID. Return UUID if possible otherwise None"""
    if isinstance(candidate_uuid, UUID):
        return candidate_uuid
    try:
        return UUID(candidate_uuid)
    except ValueError:
        return None


T = TypeVar("T")


def batch_iterator(iterable: Iterable[T], batch_size: int) -> Iterable[list[T]]:
    """Batch an iterable into a list of lists"""
    iterator = iter(iterable)
    while True:
        batch = list(itertools.islice(iterator, batch_size))
        if not batch:
            break
        yield batch
