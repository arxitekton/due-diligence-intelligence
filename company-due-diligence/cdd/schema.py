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
from typing import Any, cast

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


def _empty_errors() -> list[str]:
    return []


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=_empty_errors)
    degraded: bool = False


@cache
def load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMA_DIR / f"{name}.schema.json"
    if not path.exists():
        raise FileNotFoundError(f"no schema named {name!r} at {path}")
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def _structural_check(doc: object, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if schema.get("type") != "object":
        return errors
    if not isinstance(doc, dict):
        return [f"expected object, got {type(doc).__name__}"]
    data = cast("dict[str, Any]", doc)
    required = cast("list[str]", schema.get("required", []))
    for key in required:
        if key not in data:
            errors.append(f"missing required field: {key}")
    properties = cast("dict[str, Any]", schema.get("properties", {}))
    for key, subschema in properties.items():
        if not isinstance(subschema, dict) or key not in data:
            continue
        sub = cast("dict[str, Any]", subschema)
        if "enum" in sub and data[key] not in sub["enum"]:
            errors.append(f"{key}: {data[key]!r} not in enum")
        if sub.get("const") is not None and data[key] != sub["const"]:
            errors.append(f"{key}: {data[key]!r} != const {sub['const']!r}")
    return errors


def validate(doc: object, name: str) -> ValidationResult:
    schema = load_schema(name)
    try:
        import jsonschema  # type: ignore[import-untyped]
    except ImportError:
        errors = _structural_check(doc, schema)
        return ValidationResult(ok=not errors, errors=errors, degraded=True)

    validator: Any = jsonschema.Draft202012Validator(schema)
    errors = [
        f"{'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
        for err in validator.iter_errors(cast(Any, doc))
    ]
    return ValidationResult(ok=not errors, errors=errors, degraded=False)
