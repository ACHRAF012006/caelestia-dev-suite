"""Pure, deterministic manifest decoding/migration. No installation or code loading."""
from copy import deepcopy
from dataclasses import dataclass
import json
from types import MappingProxyType

from backend.paths import SafetyError

CURRENT_SCHEMA = 2


def strict_json(text):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out: raise SafetyError(f"Duplicate manifest key: {key}")
            out[key] = value
        return out
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(SafetyError("Invalid JSON number: " + value)))
    except (ValueError, TypeError, UnicodeError) as error:
        raise SafetyError(f"Invalid manifest JSON: {error}") from error


def v1_to_v2(manifest):
    result = deepcopy(manifest)
    result['schema_version'] = 2
    return result


MIGRATIONS = MappingProxyType({1: v1_to_v2})
SCHEMAS = MappingProxyType({1: frozenset(), 2: frozenset({'resources', 'portable_data'})})


@dataclass(frozen=True)
class ManifestDocument:
    original: dict
    manifest: dict
    source_version: int
    migrations: tuple
    original_text: str


def decode(text):
    original = strict_json(text)
    if not isinstance(original, dict): raise SafetyError("Manifest must be an object")
    version = original.get('schema_version', 1)
    if type(version) is not int or version not in SCHEMAS:
        raise SafetyError(f"schema_version: unsupported schema {version!r}; this manager reads 1–{CURRENT_SCHEMA}. Update the manager for future schemas.")
    from backend.validators import _validate_manifest
    try:
        _validate_manifest(deepcopy(original), version)
        current, steps = deepcopy(original), []
        number = version
        while number < CURRENT_SCHEMA:
            current = MIGRATIONS[number](current)
            steps.append((number, number + 1)); number += 1
        _validate_manifest(current, CURRENT_SCHEMA)
    except SafetyError as error:
        raise SafetyError(f"Manifest schema {version}: {error}") from error
    return ManifestDocument(deepcopy(original), current, version, tuple(steps),
                            text.decode('utf-8') if isinstance(text, bytes) else text)


def parse(text):
    return decode(text).manifest
