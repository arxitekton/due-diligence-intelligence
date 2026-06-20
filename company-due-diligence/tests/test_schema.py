
from cdd.schema import ValidationResult, load_schema, validate


def _valid_run_manifest() -> dict:
    return {
        "run_id": "20260620T183000Z-a1b2c3",
        "company_id": "acme-corp",
        "company_name": "Acme Corp.",
        "started_at": "2026-06-20T18:30:00Z",
        "completed_at": None,
        "mode": "full_refresh",
        "input_parameters": {"company_name": "Acme Corp."},
        "reproducibility": {
            "prompt_set_hash": "0" * 16,
            "schema_set_hash": "1" * 16,
            "model_id": "claude-opus-4-8",
            "tool_versions": {},
            "normalizer_profile_versions": {"html": "1"},
            "locale": "en-US",
        },
        "sources_discovered": 0,
        "sources_retrieved": 0,
        "sources_new": 0,
        "sources_changed": 0,
        "sources_unavailable": 0,
        "artifacts_extracted": 0,
        "schemas_validated": False,
        "output_paths": [],
        "warnings": [],
        "errors": [],
    }


def test_load_known_schema():
    schema = load_schema("run_manifest")
    assert schema["$id"].endswith("run_manifest.schema.json")


def test_valid_run_manifest_passes():
    result = validate(_valid_run_manifest(), "run_manifest")
    assert isinstance(result, ValidationResult)
    assert result.ok, result.errors


def test_bad_mode_fails():
    doc = _valid_run_manifest()
    doc["mode"] = "not_a_mode"
    result = validate(doc, "run_manifest")
    assert not result.ok
    assert any("mode" in e for e in result.errors)


def test_missing_required_field_fails():
    doc = _valid_run_manifest()
    del doc["run_id"]
    result = validate(doc, "run_manifest")
    assert not result.ok


def test_source_event_schema_roundtrip():
    event = {
        "event_id": "evt_0001",
        "event_time": "2026-06-20T18:30:00Z",
        "run_id": "20260620T183000Z-a1b2c3",
        "entity_type": "source",
        "entity_id": "src_0123456789abcdef",
        "event_type": "discovered",
        "payload": {"url": "https://example.com", "source_class": "ir"},
    }
    assert validate(event, "source_registry").ok
