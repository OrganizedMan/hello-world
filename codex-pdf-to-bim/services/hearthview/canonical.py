import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


class CanonicalValueError(TypeError):
    """Raised when a value cannot participate in exact model identity."""


def _normalize(value: object) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        raise CanonicalValueError("Canonical models cannot contain floating-point values.")
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalValueError("Canonical mapping keys must be strings.")
        return {key: _normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    raise CanonicalValueError(f"Unsupported canonical value type: {type(value).__name__}.")


def canonical_bytes(value: object) -> bytes:
    normalized = _normalize(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()
