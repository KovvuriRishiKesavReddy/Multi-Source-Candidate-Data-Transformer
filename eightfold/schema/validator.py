"""
Validates a projector's output against the config that produced it. This is
a sanity check on OUR OWN code, not on the input data — if the projector has
a bug, this is what catches a result that doesn't actually match what the
config asked for, before it's returned to the caller.
"""

from __future__ import annotations

_TYPE_CHECKERS = {
    "string": lambda v: v is None or isinstance(v, str),
    "string[]": lambda v: v is None or (isinstance(v, list) and all(isinstance(x, str) for x in v)),
    "number": lambda v: v is None or isinstance(v, (int, float)),
}


def validate_against_config(output: dict, config: dict) -> list[str]:
    errors: list[str] = []
    on_missing = config.get("on_missing", "null")

    for field_cfg in config.get("fields", []):
        path = field_cfg["path"]
        declared_type = field_cfg.get("type")
        required = field_cfg.get("required", False)

        present = path in output

        if not present:
            if required:
                errors.append(f"Required field '{path}' is missing from output entirely.")
            elif on_missing == "omit":
                pass  # expected: omitted fields should not be present
            elif on_missing == "null":
                errors.append(
                    f"Field '{path}' is absent from output, but on_missing policy is 'null' "
                    f"(expected the key to be present with a null value)."
                )
            continue

        value = output[path]

        if required and value is None:
            errors.append(f"Required field '{path}' is present but null.")

        if declared_type and declared_type in _TYPE_CHECKERS:
            if not _TYPE_CHECKERS[declared_type](value):
                errors.append(
                    f"Field '{path}' does not match declared type '{declared_type}' "
                    f"(got {type(value).__name__})."
                )

    expected_keys = {f["path"] for f in config.get("fields", [])} | {"confidence", "provenance"}
    unexpected = set(output.keys()) - expected_keys
    if unexpected:
        errors.append(f"Output contains unexpected keys not in config: {sorted(unexpected)}")

    return errors