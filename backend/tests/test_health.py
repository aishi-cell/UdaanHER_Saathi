import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_unhandled_exception_returns_uniform_error_shape(caplog):
    @app.get("/__test_raise__")
    def _raise():
        raise ValueError("boom")

    with caplog.at_level(logging.INFO, logger="udaanher.request"):
        response = client.get("/__test_raise__")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong."}
    }
    assert any("/__test_raise__" in record.getMessage() for record in caplog.records)


def test_unhandled_exception_still_carries_cors_headers():
    """Starlette's ServerErrorMiddleware (which invokes handlers registered
    via add_exception_handler(Exception, ...)) sits outside CORSMiddleware,
    so a 500 would otherwise show up in the browser as a misleading
    "blocked by CORS policy" error instead of the real failure."""

    @app.get("/__test_raise_cors__")
    def _raise():
        raise ValueError("boom")

    response = client.get(
        "/__test_raise_cors__", headers={"Origin": "http://localhost:5173"}
    )

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
