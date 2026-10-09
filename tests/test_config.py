import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_cors_origins_are_split_by_comma():
    settings = Settings(cors_origins=" https://a.onrender.com, ,https://b.com ")

    assert settings.cors_origin_list == ["https://a.onrender.com", "https://b.com"]


def test_empty_cors_origins_means_no_origin():
    assert Settings().cors_origin_list == []


def test_expire_minutes_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(jwt_expire_minutes=0)


def test_tests_ignore_developer_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("COOKIE_SECURE=false\nLOG_LEVEL=DEBUG\n")
    monkeypatch.chdir(tmp_path)

    settings = get_settings()

    assert settings.cookie_secure is True
    assert settings.log_level == "INFO"


def test_configure_changes_settings_for_one_test(configure):
    configure(cookie_secure="false")

    assert get_settings().cookie_secure is False
