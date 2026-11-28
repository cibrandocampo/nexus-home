"""Production behaviour: secret guard, unhandled errors, security headers, the built frontend."""

import logging

import pytest
from httpx import ASGITransport, AsyncClient

from app import preflight
from app.core.config import Settings, ensure_production_ready, production_problems
from app.core.headers import CONTENT_SECURITY_POLICY
from app.main import create_app

STRONG = "x" * 32
GOOD_KEY = "tvvrxZOGUWmbvodmRntVIw1lQGK5i34S3nmOK2zrv6U="


@pytest.mark.parametrize(
    ("secret", "problem"),
    [("change-me", "default placeholder"), ("short-but-not-default", "shorter than 32 bytes")],
)
def test_production_refuses_a_weak_secret(secret, problem):
    settings = Settings(env="production", secret_key=secret)

    assert problem in production_problems(settings)[0]
    with pytest.raises(RuntimeError, match=r"Refusing to start in production.*openssl rand"):
        ensure_production_ready(settings)


def test_secret_length_is_counted_in_bytes():
    # 11 characters of 3 bytes each: 33 bytes.
    settings = Settings(env="production", secret_key="€" * 11, device_token_key=GOOD_KEY)
    assert production_problems(settings) == []


def test_other_environments_accept_the_default_secret():
    assert production_problems(Settings(env="development")) == []


def test_create_app_refuses_production_with_the_default_secret(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "change-me")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="SECRET_KEY is the default placeholder"):
            create_app()
    finally:
        get_settings.cache_clear()


def test_preflight_exits_with_a_clear_message(monkeypatch, capsys):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "change-me")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert preflight.main() == 1
    finally:
        get_settings.cache_clear()
    err = capsys.readouterr().err
    assert "Configuration error: SECRET_KEY is the default placeholder." in err
    assert "openssl rand -hex 32" in err


def test_preflight_passes_outside_production():
    assert preflight.main() == 0


def test_production_hides_the_interactive_docs(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", STRONG)
    monkeypatch.setenv("DEVICE_TOKEN_KEY", GOOD_KEY)
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        app = create_app()
    finally:
        get_settings.cache_clear()
    assert app.docs_url is None
    assert app.openapi_url is None


async def test_unhandled_errors_answer_500_envelope_and_are_logged(app, caplog):
    @app.get("/api/explode")
    async def explode():
        raise ValueError("secret detail ana@example.com")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="app.core.errors"):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/explode")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error"}
    }
    assert "secret detail" not in response.text
    assert "Unhandled error on GET /api/explode" in caplog.text
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert caplog.text.count("Unhandled error") == 1


async def test_an_error_after_the_answer_started_is_left_to_the_server(app):
    from fastapi.responses import StreamingResponse

    async def body():
        yield b"partial"
        raise ValueError("mid-stream")

    @app.get("/api/stream")
    async def stream():
        return StreamingResponse(body())

    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.raises(ValueError, match="mid-stream"):
            await client.get("/api/stream")


async def test_api_paths_are_exact_without_a_slash_redirect(client):
    response = await client.get("/api/health/")

    assert response.status_code == 404


async def test_health_reports_the_version(client):
    response = await client.get("/api/health")

    assert response.json() == {"status": "ok", "version": "dev"}


async def test_security_headers_are_on_every_response(client):
    for path in ("/api/health", "/api/nope"):
        response = await client.get(path)
        assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in CONTENT_SECURITY_POLICY
    assert "script-src 'self'" in CONTENT_SECURITY_POLICY


async def test_a_header_set_by_a_route_is_not_duplicated(app, client):
    from fastapi.responses import PlainTextResponse

    @app.get("/api/framed")
    async def framed():
        return PlainTextResponse("ok", headers={"X-Frame-Options": "SAMEORIGIN"})

    response = await client.get("/api/framed")

    assert response.headers.get_list("x-frame-options") == ["SAMEORIGIN"]


# --- Built frontend ---------------------------------------------------------------------------


@pytest.fixture
def built(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>SPA</title>")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    (tmp_path.parent / "outside.txt").write_text("private")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
async def spa_client(built):
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.parametrize("path", ["/", "/profile", "/admin/users", "/some/deep/route?x=1"])
async def test_pages_get_the_spa_without_caching(spa_client, path):
    response = await spa_client.get(path)

    assert response.status_code == 200
    assert "<title>SPA</title>" in response.text
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


async def test_hashed_assets_are_cached_forever(spa_client):
    response = await spa_client.get("/assets/index-abc123.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


async def test_a_revalidated_asset_keeps_its_cache_policy(spa_client):
    first = await spa_client.get("/assets/index-abc123.js")

    response = await spa_client.get(
        "/assets/index-abc123.js", headers={"If-None-Match": first.headers["etag"]}
    )

    assert response.status_code == 304
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


async def test_public_files_are_served(spa_client):
    response = await spa_client.get("/favicon.svg")

    assert response.text == "<svg/>"
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize(
    "path", ["/api/nope", "/api", "/assets/missing.js", "/%00", "/foo%00bar", "/assets/%00"]
)
async def test_api_and_asset_misses_keep_the_json_404(spa_client, path):
    response = await spa_client.get(path)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_other_methods_do_not_get_the_spa(spa_client):
    response = await spa_client.post("/profile")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("path", ["/..%2Foutside.txt", "/%2E%2E/outside.txt", "/../outside.txt"])
async def test_files_outside_the_build_are_never_served(spa_client, path):
    response = await spa_client.get(path)

    assert "private" not in response.text


async def test_without_a_build_pages_are_json_404(client):
    response = await client.get("/profile")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_security_middleware_passes_other_scopes_through():
    from app.core.headers import SecurityHeadersMiddleware

    seen = []

    async def inner(scope, receive, send):
        seen.append(scope["type"])

    from app.core.errors import UnhandledErrorMiddleware

    await SecurityHeadersMiddleware(inner)({"type": "lifespan"}, None, None)
    await UnhandledErrorMiddleware(inner)({"type": "lifespan"}, None, None)

    assert seen == ["lifespan", "lifespan"]


def _access_record(msg, args):
    import logging

    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, msg, None, None)
    record.args = args
    return record


def test_access_log_drops_query_strings():
    from app.core.logging import DropQueryString

    record = _access_record(
        '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", "/api/users?q=ana@example.com", "1.1", 200)
    )

    assert DropQueryString().filter(record) is True
    assert record.getMessage() == '1.2.3.4:5 - "GET /api/users HTTP/1.1" 200'


def test_access_log_filter_leaves_other_records_alone():
    from app.core.logging import DropQueryString

    record = _access_record("plain %s", ("x",))
    DropQueryString().filter(record)

    assert record.getMessage() == "plain x"


def test_access_log_filter_is_installed_once():
    import logging

    from app.core.logging import DropQueryString, configure_access_log

    configure_access_log()
    configure_access_log()

    filters = logging.getLogger("uvicorn.access").filters
    assert sum(isinstance(f, DropQueryString) for f in filters) == 1


async def test_a_build_without_assets_still_serves_pages(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<!doctype html><title>SPA</title>")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        app = create_app()
    finally:
        get_settings.cache_clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/profile")

    assert "<title>SPA</title>" in response.text


def test_production_refuses_the_development_device_key():
    problems = production_problems(Settings(env="production", secret_key=STRONG))

    assert problems == ["DEVICE_TOKEN_KEY is the development key"]
    with pytest.raises(RuntimeError, match="DEVICE_TOKEN_KEY"):
        ensure_production_ready(Settings(env="production", secret_key=STRONG))


@pytest.mark.parametrize("key", ["", "not-base64!", "c2hvcnQ=", GOOD_KEY.rstrip("=")])
def test_production_refuses_a_malformed_device_key(key):
    problems = production_problems(
        Settings(env="production", secret_key=STRONG, device_token_key=key)
    )

    assert problems == ["DEVICE_TOKEN_KEY is not a Fernet key (url-safe base64 of 32 bytes)"]


def test_production_accepts_a_new_device_key():
    settings = Settings(env="production", secret_key=STRONG, device_token_key=GOOD_KEY)

    assert production_problems(settings) == []
