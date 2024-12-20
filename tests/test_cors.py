import re

import pytest

from encord_agents.core.constants import ENCORD_DOMAIN_REGEX


@pytest.fixture
def legal_origins() -> list[str]:
    return [
        # Example development previews
        "https://cord-ai-development--eb393d03-pccc0hqn.web.app",
        "https://cord-ai-development--40816cb1-dij7k5yt.web.app",
        "https://cord-ai-development--a3353fa9-0wf42o8h.web.app",
        # Main deployment,
        "https://app.encord.com",
        "https://dev.encord.com",
        "https://staging.encord.com",
        # US Deployments,
        "https://staging.us.encord.com",
        "https://dev.us.encord.com",
        "https://app.us.encord.com",
    ]


@pytest.fixture
def illegal_origins() -> list[str]:
    return [
        "https://google.com",
        "https://test.encord.com",
        "https://us.app.encord.com",
        "https://app.encord.com.something-else.com",
        "https://dev.encord.com.something-else.com",
        "https://staging.encord.com.something-else.com",
    ]


@pytest.fixture
def compiled_regex() -> re.Pattern[str]:
    return re.compile(ENCORD_DOMAIN_REGEX)


def test_legal_domains_against_CORS_regex(legal_origins: list[str], compiled_regex: re.Pattern[str]) -> None:
    for origin in legal_origins:
        assert compiled_regex.fullmatch(origin), f"Origin should have been allowed: `{origin}`"


def test_illegal_domains_against_CORS_regex(illegal_origins: list[str], compiled_regex: re.Pattern[str]) -> None:
    for origin in illegal_origins:
        assert not compiled_regex.fullmatch(origin), f"Origin should _not_ have been allowed: `{origin}`"
