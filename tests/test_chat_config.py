import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_ai_defaults_do_not_require_a_key():
    settings = get_settings()
    assert settings.openrouter_api_key is None
    assert settings.ai_model == "qwen/qwen3-30b-a3b-instruct-2507"
    assert settings.ai_timeout_seconds == 30
    assert settings.ai_max_output_tokens == 1024
    assert settings.chat_context_pairs == 5
    assert settings.chat_max_question_length == 5000


@pytest.mark.parametrize(
    "name",
    [
        "ai_timeout_seconds",
        "ai_max_output_tokens",
        "chat_context_pairs",
        "chat_max_question_length",
    ],
)
def test_limits_must_be_positive(name):
    with pytest.raises(ValidationError):
        Settings(**{name: 0})


def test_key_is_read_from_environment_but_hidden_in_repr(configure):
    configure(openrouter_api_key="private-test-secret")
    settings = get_settings()
    assert settings.openrouter_api_key.get_secret_value() == "private-test-secret"
    assert "private-test-secret" not in repr(settings)
