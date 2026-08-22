import json

from scripts.generate_contracts import render_schema, render_typescript


def test_generated_schema_exposes_exact_project_contract() -> None:
    schema = json.loads(render_schema())

    assert schema["title"] == "ProjectModel"
    assert "Wall" in schema["$defs"]
    assert schema["properties"]["revision"]["type"] == "integer"


def test_generated_typescript_brands_tick_strings() -> None:
    generated = render_typescript()

    assert "export type TickString = string & { readonly __tickBrand: unique symbol };" in generated
    assert "export interface ProjectModel" in generated
    assert "width_ticks: TickString;" in generated


def test_generated_typescript_includes_api_boundary_models() -> None:
    generated = render_typescript()

    for interface_name in (
        "ProjectResponse",
        "SourceResponse",
        "ReviewItemResponse",
        "ValidationRunResponse",
        "GeometryResponse",
        "BlenderCapabilityResponse",
        "RenderJobResponse",
    ):
        assert f"export interface {interface_name}" in generated
