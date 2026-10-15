from types import SimpleNamespace

import pytest

from services.event_retry_policy import (
    DEAD_LETTER_QUEUE,
    MAIN_QUEUE,
    MAX_RETRIES,
    RETRY_DELAY_MS,
    RETRY_QUEUE,
    get_retry_count,
    next_retry_count,
    should_retry,
)


def test_default_retry_count_is_zero():
    assert get_retry_count(None) == 0


def test_retry_count_is_read_from_headers():
    properties = SimpleNamespace(headers={"x-retry-count": 2})
    assert get_retry_count(properties) == 2


def test_invalid_retry_count_is_rejected():
    properties = SimpleNamespace(headers={"x-retry-count": "invalid"})
    with pytest.raises(ValueError, match="Invalid x-retry-count header"):
        get_retry_count(properties)


def test_negative_retry_count_is_rejected():
    properties = SimpleNamespace(headers={"x-retry-count": -1})
    with pytest.raises(ValueError, match="Invalid x-retry-count header"):
        get_retry_count(properties)


def test_boolean_retry_count_is_rejected():
    properties = SimpleNamespace(headers={"x-retry-count": True})
    with pytest.raises(ValueError, match="Invalid x-retry-count header"):
        get_retry_count(properties)


def test_retry_count_increments():
    assert next_retry_count(0) == 1
    assert next_retry_count(1) == 2
    assert next_retry_count(2) == 3


def test_retry_limit_is_three():
    assert MAX_RETRIES == 3
    assert should_retry(0)
    assert should_retry(1)
    assert should_retry(2)
    assert not should_retry(3)


def test_retry_limit_prevents_an_extra_retry():
    with pytest.raises(ValueError):
        next_retry_count(3)


def test_queue_settings():
    assert MAIN_QUEUE == "claim_events"
    assert RETRY_QUEUE == "claim_events_retry"
    assert DEAD_LETTER_QUEUE == "claim_events_dead"
    assert RETRY_DELAY_MS == 30_000
