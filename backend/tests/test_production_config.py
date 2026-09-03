from app import create_app
from app.config import Config


def test_cors_allows_configured_local_origin_and_rejects_unknown_origin():
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    allowed = client.get(
        '/api/profile/projects',
        headers={'Origin': 'http://localhost:5173'},
    )
    denied = client.get(
        '/api/profile/projects',
        headers={'Origin': 'https://untrusted.example'},
    )

    assert allowed.headers.get('Access-Control-Allow-Origin') == 'http://localhost:5173'
    assert denied.headers.get('Access-Control-Allow-Origin') is None


def test_config_has_no_shared_secret_fallback():
    assert Config.SECRET_KEY != 'prism-secret-key'
