#!/usr/bin/env python3
"""Validate newly added Studio Agent skill packages.

Required files:
  - SKILL.md with YAML frontmatter
  - GRAPH_MODEL.json (parseable JSON)

Required SKILL.md frontmatter:
  name: <kebab-case skill id matching the directory>
  description: <non-empty>
  metadata:
    neo4j-card-title: <non-empty>
    neo4j-card-category: one of the allowed categories
    neo4j-card-description: <non-empty>

Usage:
  python3 scripts/validate-new-packages.py --base <sha-or-ref>
  python3 scripts/validate-new-packages.py --all
  python3 scripts/validate-new-packages.py <skill-id> [<skill-id> ...]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOWED_CATEGORIES = (
    "Financial Services",
    "Insurance",
    "Healthcare & Life Sciences",
    "Manufacturing",
    "Cybersecurity",
    "Industry Agnostic",
)

IGNORE_TOP_LEVEL_DIRS = {".github", "scripts", "node_modules", "skills", "tests"}
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*(?:\n(.*))?\Z", re.DOTALL)


class FrontmatterError(ValueError):
    """Raised when SKILL.md frontmatter is not a simple YAML mapping."""


def _unquote_yaml_scalar(value: str) -> str | None:
    if value == "" or value in {"null", "~", "Null", "NULL"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_frontmatter_mapping(text: str) -> dict:
    """Parse the constrained YAML mapping used in SKILL.md frontmatter.

    Supports nested mappings and quoted or plain scalars. Lists, tabs, and
    unclosed flow collections are rejected so this stays stdlib-only.
    """
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if "\t" in raw[:indent] or raw.startswith("\t"):
            raise FrontmatterError("tabs are not allowed")

        stripped = raw.strip()
        if stripped.startswith("-"):
            raise FrontmatterError("frontmatter must be a YAML mapping, not a list")
        if ":" not in stripped:
            raise FrontmatterError("expected 'key: value'")

        key, _, remainder = stripped.partition(":")
        key = key.strip()
        value = remainder.strip()
        if not key:
            raise FrontmatterError("invalid key")

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if value == "":
            nested: dict = {}
            parent[key] = nested
            stack.append((indent, nested))
            continue

        if (value.startswith("[") and not value.endswith("]")) or (
            value.startswith("{") and not value.endswith("}")
        ):
            raise FrontmatterError("not valid YAML")

        parent[key] = _unquote_yaml_scalar(value)

    return root


class Issue:
    def __init__(self, message: str, path: Path | None = None, line: int | None = None):
        self.message = message
        self.path = path
        self.line = line

    def annotation(self) -> str:
        parts = ["::error"]
        extras: list[str] = []
        if self.path is not None:
            extras.append(f"file={self.path.as_posix()}")
        if self.line is not None:
            extras.append(f"line={self.line}")
        if extras:
            parts.append(" " + ",".join(extras))
        parts.append(f"::{self.message}")
        return "".join(parts)


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def git_show(ref: str, relpath: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{relpath}"],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def top_level_dirs(ref: str) -> set[str]:
    return {
        line
        for line in git_output("ls-tree", "-d", "--name-only", ref).splitlines()
        if line
    }


def working_tree_top_level_dirs() -> set[str]:
    return {
        path.name
        for path in REPO_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }


def catalog_skill_ids_from_text(text: str, source: str) -> set[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {source}: {exc}") from exc

    skills = data.get("skills")
    if not isinstance(skills, list):
        return set()

    ids: set[str] = set()
    for entry in skills:
        if isinstance(entry, dict) and isinstance(entry.get("skillId"), str):
            ids.add(entry["skillId"])
    return ids


def catalog_skill_ids_at(ref: str | None) -> set[str]:
    if ref is None:
        catalog = REPO_ROOT / "catalog.json"
        if not catalog.is_file():
            return set()
        return catalog_skill_ids_from_text(
            catalog.read_text(encoding="utf-8"), "catalog.json"
        )

    text = git_show(ref, "catalog.json")
    if text is None:
        return set()
    return catalog_skill_ids_from_text(text, f"{ref}:catalog.json")


def is_package_dir(name: str) -> bool:
    return name not in IGNORE_TOP_LEVEL_DIRS and not name.startswith(".")


def discover_new_packages(base: str) -> list[str]:
    base_dirs = {name for name in top_level_dirs(base) if is_package_dir(name)}
    head_dirs = {name for name in working_tree_top_level_dirs() if is_package_dir(name)}
    new_dirs = head_dirs - base_dirs

    new_catalog_ids = catalog_skill_ids_at(None) - catalog_skill_ids_at(base)
    return sorted(new_dirs | new_catalog_ids)


def non_empty_string(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def load_catalog_entry(skill_id: str) -> dict | None:
    catalog = REPO_ROOT / "catalog.json"
    if not catalog.is_file():
        return None
    try:
        data = json.loads(catalog.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    skills = data.get("skills")
    if not isinstance(skills, list):
        return None
    for entry in skills:
        if isinstance(entry, dict) and entry.get("skillId") == skill_id:
            return entry
    return None


def validate_skill_md(skill_id: str, skill_dir: Path, issues: list[Issue]) -> None:
    skill_md = skill_dir / "SKILL.md"
    rel = Path(skill_id) / "SKILL.md"

    if not skill_md.is_file():
        issues.append(Issue(f"{skill_id}: missing required file SKILL.md", rel))
        return

    text = skill_md.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.strip():
        issues.append(Issue(f"{skill_id}: SKILL.md is empty", rel, 1))
        return

    match = FRONTMATTER_RE.match(text)
    if not match:
        issues.append(
            Issue(
                f"{skill_id}: SKILL.md must start with YAML frontmatter "
                "delimited by --- lines",
                rel,
                1,
            )
        )
        return

    try:
        frontmatter = parse_frontmatter_mapping(match.group(1))
    except FrontmatterError as exc:
        issues.append(
            Issue(f"{skill_id}: SKILL.md frontmatter is not valid YAML: {exc}", rel, 1)
        )
        return

    if not isinstance(frontmatter, dict):
        issues.append(
            Issue(f"{skill_id}: SKILL.md frontmatter must be a YAML mapping", rel, 1)
        )
        return

    name = non_empty_string(frontmatter.get("name"))
    if name is None:
        issues.append(
            Issue(
                f"{skill_id}: SKILL.md frontmatter is missing a non-empty 'name'",
                rel,
                1,
            )
        )
    else:
        if name != skill_id:
            issues.append(
                Issue(
                    f"{skill_id}: SKILL.md 'name' must match the directory name "
                    f"({skill_id!r}), got {name!r}",
                    rel,
                    1,
                )
            )

    if non_empty_string(frontmatter.get("description")) is None:
        issues.append(
            Issue(
                f"{skill_id}: SKILL.md frontmatter is missing a non-empty "
                "'description'",
                rel,
                1,
            )
        )

    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        issues.append(
            Issue(
                f"{skill_id}: SKILL.md frontmatter is missing a 'metadata' mapping "
                "with Neo4j card fields",
                rel,
                1,
            )
        )
        return

    title = non_empty_string(metadata.get("neo4j-card-title"))
    if title is None:
        issues.append(
            Issue(
                f"{skill_id}: metadata.neo4j-card-title is required and must be "
                "a non-empty string",
                rel,
                1,
            )
        )

    category = non_empty_string(metadata.get("neo4j-card-category"))
    if category is None:
        issues.append(
            Issue(
                f"{skill_id}: metadata.neo4j-card-category is required and must be "
                "a non-empty string",
                rel,
                1,
            )
        )
    elif category not in ALLOWED_CATEGORIES:
        allowed = ", ".join(repr(item) for item in ALLOWED_CATEGORIES)
        issues.append(
            Issue(
                f"{skill_id}: metadata.neo4j-card-category must be one of: "
                f"{allowed}. Got {category!r}",
                rel,
                1,
            )
        )

    card_description = non_empty_string(metadata.get("neo4j-card-description"))
    if card_description is None:
        issues.append(
            Issue(
                f"{skill_id}: metadata.neo4j-card-description is required and "
                "must be a non-empty string",
                rel,
                1,
            )
        )

    body = match.group(2) or ""
    if not body.strip():
        issues.append(
            Issue(
                f"{skill_id}: SKILL.md body after frontmatter must be non-empty", rel, 1
            )
        )


def validate_graph_model(skill_id: str, skill_dir: Path, issues: list[Issue]) -> None:
    graph_model = skill_dir / "GRAPH_MODEL.json"
    rel = Path(skill_id) / "GRAPH_MODEL.json"

    if not graph_model.is_file():
        issues.append(Issue(f"{skill_id}: missing required file GRAPH_MODEL.json", rel))
        return

    text = graph_model.read_text(encoding="utf-8")
    if not text.strip():
        issues.append(Issue(f"{skill_id}: GRAPH_MODEL.json is empty", rel, 1))
        return

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        line = exc.lineno if exc.lineno else 1
        issues.append(
            Issue(
                f"{skill_id}: GRAPH_MODEL.json is not valid JSON: {exc.msg}",
                rel,
                line,
            )
        )
        return

    if not isinstance(data, dict):
        issues.append(
            Issue(f"{skill_id}: GRAPH_MODEL.json must contain a JSON object", rel, 1)
        )


def validate_catalog_entry(skill_id: str, issues: list[Issue]) -> None:
    entry = load_catalog_entry(skill_id)
    catalog = Path("catalog.json")
    if entry is None:
        issues.append(
            Issue(
                f"{skill_id}: new package must be listed in catalog.json "
                f"with skillId {skill_id!r}",
                catalog,
            )
        )
        return

    files = entry.get("files")
    if not isinstance(files, dict):
        issues.append(
            Issue(
                f"{skill_id}: catalog.json entry is missing a 'files' object",
                catalog,
            )
        )
        return

    graph = files.get("graph")
    if graph != "GRAPH_MODEL.json":
        issues.append(
            Issue(
                f"{skill_id}: catalog.json files.graph must be 'GRAPH_MODEL.json', "
                f"got {graph!r}",
                catalog,
            )
        )

    markdown = files.get("markdown")
    if markdown != "SKILL.md":
        issues.append(
            Issue(
                f"{skill_id}: catalog.json files.markdown must be 'SKILL.md', "
                f"got {markdown!r}",
                catalog,
            )
        )


def validate_package(skill_id: str) -> list[Issue]:
    issues: list[Issue] = []
    skill_dir = REPO_ROOT / skill_id

    if not skill_dir.is_dir():
        issues.append(Issue(f"{skill_id}: package directory does not exist"))
        return issues

    validate_skill_md(skill_id, skill_dir, issues)
    validate_graph_model(skill_id, skill_dir, issues)
    validate_catalog_entry(skill_id, issues)
    return issues


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "base",
        help="Git SHA or ref to compare against when detecting newly added packages",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    packages = discover_new_packages(args.base)
    if not packages:
        print("No new skill packages to validate.")
        return 0
    print("New skill packages: " + ", ".join(packages))

    all_issues: list[Issue] = []
    for skill_id in packages:
        print(f"Validating {skill_id}", flush=True)
        all_issues.extend(validate_package(skill_id))

    if not all_issues:
        print(f"Validated {len(packages)} package(s).")
        return 0

    for issue in all_issues:
        print(issue.annotation())
        print(issue.message, file=sys.stderr)

    print(
        f"{len(all_issues)} validation error(s) across {len(packages)} package(s).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
