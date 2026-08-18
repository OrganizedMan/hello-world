"""The explicit `Unknown` sentinel (plan §11: "Unknown is a button").

A field holding UNKNOWN is a documented epistemic state, never a Python
None used ambiguously for "not set yet" vs "confirmed absent". Validation
and rendering code must treat UNKNOWN as a first-class value: e.g. a room
with an UNKNOWN ceiling height is drawn open-topped, not defaulted.
"""
from __future__ import annotations

from typing import Union


class _UnknownType:
    _instance: "_UnknownType | None" = None

    def __new__(cls) -> "_UnknownType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNKNOWN"

    def __bool__(self) -> bool:
        return False

    def __reduce__(self):
        return (_UnknownType, ())


UNKNOWN = _UnknownType()

IntOrUnknown = Union[int, _UnknownType]


def nm_or_unknown_to_json(v: IntOrUnknown):
    return None if v is UNKNOWN else v


def json_to_nm_or_unknown(v) -> IntOrUnknown:
    return UNKNOWN if v is None else int(v)
