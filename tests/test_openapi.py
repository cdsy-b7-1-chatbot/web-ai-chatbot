import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import ERROR_CODE_DOCS, ErrorCode, error_responses
from app.main import create_app

ERROR_REF = {"$ref": "#/components/schemas/ErrorResponse"}


class _Body(BaseModel):
    name: str


@pytest.fixture
def spec():
    app = create_app()

    @app.post("/test/items", status_code=201, responses=error_responses(401, 409))
    def create_item(body: _Body):
        return {}

    return TestClient(app).get("/openapi.json").json()


def _schema(spec, path, method, status):
    return spec["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]


def test_validation_error_is_documented_as_error_response(spec):
    assert _schema(spec, "/test/items", "post", "422") == ERROR_REF
    assert "HTTPValidationError" not in spec["components"]["schemas"]
    assert "ValidationError" not in spec["components"]["schemas"]


def test_declared_error_responses_use_error_response(spec):
    assert _schema(spec, "/test/items", "post", "401") == ERROR_REF
    assert _schema(spec, "/test/items", "post", "409") == ERROR_REF


def test_every_endpoint_documents_500(spec):
    assert _schema(spec, "/api/health", "get", "500") == ERROR_REF


def test_route_without_input_has_no_422(spec):
    assert "422" not in spec["paths"]["/api/health"]["get"]["responses"]


def test_error_code_enum_is_listed_in_schema(spec):
    assert set(spec["components"]["schemas"]["ErrorCode"]["enum"]) == set(ErrorCode)


def test_every_error_code_is_documented_in_description(spec):
    assert set(ERROR_CODE_DOCS) == set(ErrorCode)
    for code in ErrorCode:
        assert f"| `{code}` |" in spec["info"]["description"]


def test_swagger_ui_is_served():
    assert TestClient(create_app()).get("/docs").status_code == 200


def test_health_response_is_documented_with_example(spec):
    schema = _schema(spec, "/api/health", "get", "200")
    assert schema == {"$ref": "#/components/schemas/HealthResponse"}
    assert spec["components"]["schemas"]["HealthResponse"]["examples"] == [{"status": "ok"}]
