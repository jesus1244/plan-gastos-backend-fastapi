from app.infrastructure.database.config import settings


def test_database_settings_are_loaded() -> None:
    assert settings.postgres_db
    assert settings.postgres_user
    assert settings.postgres_host
    assert settings.postgres_port > 0
    assert 'postgresql' in settings.database_url
