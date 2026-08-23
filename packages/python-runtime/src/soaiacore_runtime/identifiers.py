from __future__ import annotations

from .hashing import sha256_text


def deterministic_id(prefix: str, *parts: str, length: int = 24) -> str:
    material = "\x1f".join(parts)
    return f"{prefix}_{sha256_text(material)[:length]}"


def validate_identifier(value: str, prefix: str) -> str:
    expected = f"{prefix}_"
    if not value.startswith(expected) or len(value) <= len(expected):
        raise ValueError(f"identifier must start with {expected}")
    if not all(character.isalnum() or character in "_-" for character in value):
        raise ValueError("identifier contains unsupported characters")
    return value

