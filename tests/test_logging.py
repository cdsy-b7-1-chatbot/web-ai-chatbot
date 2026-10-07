import logging

import pytest

from app.core.logging import format_value, log_event, request_id_var, user_id_var


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "-"),
        (1240, "1240"),
        ("/api/health", "/api/health"),
        ("안녕", "안녕"),
    ],
)
def test_plain_values_are_left_as_is(value, expected):
    assert format_value(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("read timed out", '"read timed out"'),
        ("", '""'),
        ("a=b", '"a=b"'),
        ('say "hi"', r'"say \"hi\""'),
        ("C:\\temp", r'"C:\\temp"'),
        ("안녕 하세요", '"안녕 하세요"'),
    ],
)
def test_ambiguous_values_are_quoted_and_escaped(value, expected):
    assert format_value(value) == expected


def test_newline_is_escaped_so_injection_stays_on_one_line():
    attack = "/api/x\n2026-10-07T06:40:02Z INFO login_success user_id=1"

    formatted = format_value(attack)

    assert "\n" not in formatted
    assert formatted == r'"/api/x\n2026-10-07T06:40:02Z INFO login_success user_id=1"'


def test_carriage_return_is_escaped():
    assert format_value("a\rb") == r'"a\rb"'


@pytest.fixture
def request_context():
    """요청 미들웨어가 하는 일을 흉내 내 request_id·user_id 를 넣었다가 되돌린다."""
    tokens = (request_id_var.set("a1b2c3"), user_id_var.set(12))
    yield
    request_id_var.reset(tokens[0])
    user_id_var.reset(tokens[1])


def test_log_event_adds_request_context_first(caplog, request_context):
    caplog.set_level(logging.INFO)

    log_event(logging.getLogger("test"), "ai_call_success", latency_ms=1240)

    assert caplog.messages == ["ai_call_success request_id=a1b2c3 user_id=12 latency_ms=1240"]


def test_log_event_outside_request_uses_dash(caplog):
    caplog.set_level(logging.INFO)

    log_event(logging.getLogger("test"), "startup")

    assert caplog.messages == ["startup request_id=- user_id=-"]


def test_log_event_passes_level(caplog):
    caplog.set_level(logging.INFO)

    log_event(logging.getLogger("test"), "ai_call_failed", logging.WARNING, error="read timed out")

    assert caplog.records[0].levelno == logging.WARNING
    assert caplog.messages == ['ai_call_failed request_id=- user_id=- error="read timed out"']
