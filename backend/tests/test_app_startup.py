from fastapi import FastAPI

from app.api.v1.health import health_check
from app.main import app


def test_application_imports_and_registers_health_endpoint():
    assert isinstance(app, FastAPI)

    assert any(
        route.endpoint is health_check
        and route.path == "/health"
        and "GET" in route.methods
        for route in app.routes
    )
