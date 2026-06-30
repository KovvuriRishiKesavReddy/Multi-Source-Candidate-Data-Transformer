"""
CLI entry point for the multi-source candidate data transformer.

Usage:
    python -m cli.main \
        --ats sample_inputs/ats_export.json \
        --notes sample_inputs/recruiter_notes.txt \
        --config sample_inputs/config_default.json \
        --output output.json

Any of --ats / --notes can be omitted entirely (per "any source may be
missing" in the brief) — the pipeline runs on whatever sources are provided.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from ..extractors.ats_json import extract_ats_json
from ..extractors.recruiter_notes import extract_recruiter_notes
from ..merge.build_profile import build_canonical_profile
from ..merge.matcher import group_records
from ..schema.canonical import PartialRecord
from ..schema.projector import ProjectionError, project
from ..schema.validator import validate_against_config

logger = logging.getLogger("eightfold")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Multi-source candidate data transformer — merges ATS JSON and/or "
        "recruiter notes into canonical candidate profiles, then projects them through "
        "a runtime config."
    )
    parser.add_argument("--ats", help="Path to ATS JSON export file")
    parser.add_argument("--notes", help="Path to recruiter notes .txt file")
    parser.add_argument("--config", required=True, help="Path to the output-shaping config JSON")
    parser.add_argument(
        "--config2",
        help="Optional second config — if given, ALSO projects every candidate through this "
        "config and writes to <output>.alt.json, without re-running extraction/merge.",
    )
    parser.add_argument("--output", help="Path to write output JSON (default: stdout)")
    parser.add_argument(
        "--log-level", default="WARNING", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def load_records(ats_path: str | None, notes_path: str | None) -> list[PartialRecord]:
    records: list[PartialRecord] = []
    sources_used = []

    if ats_path:
        ats_records = extract_ats_json(ats_path)
        records.extend(ats_records)
        if ats_records:
            sources_used.append(("ats_json", len(ats_records)))
    else:
        logger.warning("No --ats path provided — running without the structured source.")

    if notes_path:
        notes_records = extract_recruiter_notes(notes_path)
        records.extend(notes_records)
        if notes_records:
            sources_used.append(("recruiter_notes", len(notes_records)))
    else:
        logger.warning("No --notes path provided — running without the unstructured source.")

    if not sources_used:
        logger.warning("No sources produced any records at all — output will be empty.")

    for source_name, count in sources_used:
        print(f"  - {source_name}: {count} record(s) extracted", file=sys.stderr)

    return records


def build_all_profiles(records: list[PartialRecord]):
    groups = group_records(records)
    profiles = []
    for g in groups:
        try:
            profiles.append(build_canonical_profile(g))
        except Exception as e:  # noqa: BLE001 - one bad group must not kill the run
            names = [r.full_name for r in g.records]
            logger.warning("Failed to build profile for group %s (%s) — skipping.", names, e)
    return profiles


def project_all(profiles, config: dict):
    results = []
    skipped = 0
    for profile in profiles:
        try:
            out = project(profile, config)
        except ProjectionError as e:
            logger.warning(
                "Skipping candidate %s (%s) — projection failed: %s",
                profile.candidate_id,
                profile.full_name,
                e,
            )
            skipped += 1
            continue

        errors = validate_against_config(out, config)
        if errors:
            logger.warning(
                "Skipping candidate %s (%s) — output failed validation: %s",
                profile.candidate_id,
                profile.full_name,
                errors,
            )
            skipped += 1
            continue

        results.append(out)
    return results, skipped


def write_output(data, path: str | None):
    text = json.dumps(data, indent=2)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(levelname)s: %(message)s")

    print("Extracting from sources:", file=sys.stderr)
    records = load_records(args.ats, args.notes)

    profiles = build_all_profiles(records)
    print(f"Built {len(profiles)} canonical candidate profile(s).", file=sys.stderr)

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)

    results, skipped = project_all(profiles, config)
    print(
        f"Projected {len(results)} candidate(s) through config "
        f"({skipped} skipped due to projection/validation failure).",
        file=sys.stderr,
    )

    write_output(results, args.output)

    if args.config2:
        with open(args.config2, encoding="utf-8") as f:
            config2 = json.load(f)
        results2, skipped2 = project_all(profiles, config2)
        print(
            f"Projected {len(results2)} candidate(s) through second config "
            f"({skipped2} skipped).",
            file=sys.stderr,
        )
        alt_path = f"{args.output}.alt.json" if args.output else None
        write_output(results2, alt_path)
        if alt_path is None:
            pass  # already printed to stdout via write_output above


if __name__ == "__main__":
    main()