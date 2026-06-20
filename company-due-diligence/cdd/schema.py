"""Schema loading + validation with optional jsonschema backend.

If jsonschema is installed, full validation runs. Otherwise a structural
fallback checks required keys and enum membership only, and `degraded` is
set so callers (and validate_outputs in Plan 2) can refuse to pass when
full validation is mandatory.
"""

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    degraded: bool = False


@cache
def load_schema(name: str) -> dict:
    path = _SCHEMA_DIR / f"{name}.schema.json"
    if not path.exists():
        raise FileNotFoundError(f"no schema named {name!r} at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _structural_check(doc: object, schema: dict) -> list[str]:
    errors: list[str] = []
    if schema.get("type") == "object":
        if not isinstance(doc, dict):
            return [f"expected object, got {type(doc).__name__}"]
        for key in schema.get("required", []):
            if key not in doc:
                errors.append(f"missing required field: {key}")
        for key, subschema in schema.get("properties", {}).items():
            if key in doc and isinstance(subschema, dict) and "enum" in subschema:
                if doc[key] not in subschema["enum"]:
                    errors.append(f"{key}: {doc[key]!r} not in enum")
            if key in doc and isinstance(subschema, dict) and subschema.get("const") is not None:
                if doc[key] != subschema["const"]:
                    errors.append(f"{key}: {doc[key]!r} != const {subschema['const']!r}")
    return errors


def validate(doc: object, name: str) -> ValidationResult:
    schema = load_schema(name)
    try:
        import jsonschema  # type: ignore
    except ImportError:
        errors = _structural_check(doc, schema)
        return ValidationResult(ok=not errors, errors=errors, degraded=True)

    validator = jsonschema.Draft202012Validator(schema)
    errors = [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
              for e in validator.iter_errors(doc)]
    return ValidationResult(ok=not errors, errors=errors, degraded=False)
