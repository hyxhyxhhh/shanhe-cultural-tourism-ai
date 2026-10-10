"""Strict loader for versioned activity-planning runtime skills."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from backend.models import STEP_KEYS


SKILLS_ROOT = Path(__file__).with_name("activity_skills")
_MANIFEST_FIELDS = frozenset({"schemaVersion", "skills"})
_ENTRY_FIELDS = frozenset({"stepNo", "stepKey", "skillId", "version", "file"})
_REQUIRED_SECTIONS = (
    "## 输入契约",
    "## 输出契约",
    "## 业务判断规则",
    "## 禁止行为",
)
_VERSION_PATTERN = re.compile(r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")


class ActivitySkillError(RuntimeError):
    """Raised when the configured runtime skill contract is invalid."""


@dataclass(frozen=True, slots=True)
class ActivityStepSkill:
    step_no: int
    step_key: str
    skill_id: str
    version: str
    content: str


def _exact_object(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ActivitySkillError(f"{label} must be a JSON object")
    names = set(value)
    missing = sorted(fields - names)
    unknown = sorted(names - fields)
    if missing:
        raise ActivitySkillError(f"{label} is missing field(s): {', '.join(missing)}")
    if unknown:
        raise ActivitySkillError(f"{label} contains unknown field(s): {', '.join(unknown)}")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for name, child in pairs:
        if name in value:
            raise ValueError(f"duplicate JSON object key: {name}")
        value[name] = child
    return value


def _read_manifest(skills_root: Path) -> list[dict[str, Any]]:
    manifest_path = skills_root / "manifest.json"
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ActivitySkillError(f"activity skill manifest cannot be read: {manifest_path}") from exc
    try:
        manifest = json.loads(raw, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ActivitySkillError("activity skill manifest is not valid JSON") from exc
    record = _exact_object(manifest, _MANIFEST_FIELDS, "activity skill manifest")
    if record["schemaVersion"] != 1:
        raise ActivitySkillError("activity skill manifest schemaVersion must be 1")
    entries = record["skills"]
    if not isinstance(entries, list):
        raise ActivitySkillError("activity skill manifest skills must be an array")
    if len(entries) != len(STEP_KEYS):
        raise ActivitySkillError("activity skill manifest must contain exactly nine skills")
    return [
        _exact_object(entry, _ENTRY_FIELDS, f"activity skill manifest skills[{index}]")
        for index, entry in enumerate(entries)
    ]


def _validate_entry(entry: dict[str, Any], index: int) -> None:
    expected_step_no = index + 1
    expected_step_key = STEP_KEYS[index]
    if entry["stepNo"] != expected_step_no:
        raise ActivitySkillError(
            f"activity skill manifest entry {index} stepNo must be {expected_step_no}"
        )
    if entry["stepKey"] != expected_step_key:
        raise ActivitySkillError(
            f"activity skill manifest step {expected_step_no} stepKey must be {expected_step_key}"
        )
    expected_skill_id = f"activity-step-{expected_step_key}"
    if entry["skillId"] != expected_skill_id:
        raise ActivitySkillError(
            f"activity skill manifest step {expected_step_no} skillId must be {expected_skill_id}"
        )
    version = entry["version"]
    if not isinstance(version, str) or _VERSION_PATTERN.fullmatch(version) is None:
        raise ActivitySkillError(
            f"activity skill manifest step {expected_step_no} version must use semantic versioning"
        )
    expected_file = f"v1/{expected_step_no:02d}-{expected_step_key}.md"
    if entry["file"] != expected_file:
        raise ActivitySkillError(
            f"activity skill manifest step {expected_step_no} file must be {expected_file}"
        )


def load_activity_step_skill(
    step_no: int,
    step_key: str,
    *,
    skills_root: Path = SKILLS_ROOT,
) -> ActivityStepSkill:
    """Read and validate the exact skill configured for a workflow step."""

    if isinstance(step_no, bool) or not isinstance(step_no, int) or not 1 <= step_no <= 9:
        raise ActivitySkillError("activity skill stepNo must be an integer from 1 to 9")
    if not isinstance(step_key, str) or step_key != STEP_KEYS[step_no - 1]:
        raise ActivitySkillError(
            f"activity skill stepKey for step {step_no} must be {STEP_KEYS[step_no - 1]}"
        )

    entries = _read_manifest(skills_root)
    for index, entry in enumerate(entries):
        _validate_entry(entry, index)
    entry = entries[step_no - 1]
    skill_path = skills_root / entry["file"]
    try:
        content = skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ActivitySkillError(
            f"activity skill file cannot be read for step {step_no}: {skill_path}"
        ) from exc
    if not content.strip():
        raise ActivitySkillError(f"activity skill file for step {step_no} is empty")
    if "\x00" in content:
        raise ActivitySkillError(f"activity skill file for step {step_no} contains a NUL byte")
    missing_sections = [section for section in _REQUIRED_SECTIONS if section not in content]
    if missing_sections:
        raise ActivitySkillError(
            f"activity skill file for step {step_no} is missing section(s): "
            + ", ".join(missing_sections)
        )
    return ActivityStepSkill(
        step_no=step_no,
        step_key=step_key,
        skill_id=entry["skillId"],
        version=entry["version"],
        content=content.strip(),
    )
