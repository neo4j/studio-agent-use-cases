#!/usr/bin/env python3
"""Unit tests for scripts/validate-new-packages.py."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-new-packages.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_new_packages", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


vnp = load_validator()

SKILL_ID = "example-skill"
VALID_GRAPH_MODEL = json.dumps({"version": "4.0.0", "nodes": {}})


def skill_md(
    *,
    name: str = SKILL_ID,
    description: str = "A test skill.",
    title: str = "Example Skill",
    category: str = "Industry Agnostic",
    card_description: str = "Short summary.",
    body: str = "# Example Skill\n\nBody text.\n",
) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "metadata:\n"
        f"  neo4j-card-title: {title}\n"
        f"  neo4j-card-category: {category}\n"
        f"  neo4j-card-description: {card_description}\n"
        "---\n\n"
        f"{body}"
    )


def catalog_for(skill_id: str, **files) -> dict:
    entry_files = {
        "graph": "GRAPH_MODEL.json",
        "markdown": "SKILL.md",
        "skill": [],
    }
    entry_files.update(files)
    return {
        "schemaVersion": 1,
        "skills": [{"skillId": skill_id, "files": entry_files}],
    }


class ValidatorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.skill_dir = self.root / SKILL_ID
        self.skill_dir.mkdir()
        self.addCleanup(self.tmp.cleanup)
        self._orig_root = vnp.REPO_ROOT
        vnp.REPO_ROOT = self.root
        self.addCleanup(self._restore_repo_root)

    def _restore_repo_root(self) -> None:
        vnp.REPO_ROOT = self._orig_root

    def write_skill_md(self, content: str) -> None:
        (self.skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def write_graph_model(self, content: str = VALID_GRAPH_MODEL) -> None:
        (self.skill_dir / "GRAPH_MODEL.json").write_text(content, encoding="utf-8")

    def write_catalog(self, data: dict | None = None, **files) -> None:
        payload = catalog_for(SKILL_ID, **files) if data is None else data
        (self.root / "catalog.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    def skill_md_issues(
        self, content: str | None = None, *, missing: bool = False
    ) -> list[str]:
        if not missing and content is not None:
            self.write_skill_md(content)
        issues: list[vnp.Issue] = []
        vnp.validate_skill_md(SKILL_ID, self.skill_dir, issues)
        return [issue.message for issue in issues]

    def graph_model_issues(
        self, content: str | None = None, *, missing: bool = False
    ) -> list[str]:
        if not missing and content is not None:
            self.write_graph_model(content)
        issues: list[vnp.Issue] = []
        vnp.validate_graph_model(SKILL_ID, self.skill_dir, issues)
        return [issue.message for issue in issues]


class TestIssue(unittest.TestCase):
    def test_annotation_includes_file_and_line(self) -> None:
        issue = vnp.Issue("missing title", Path("example-skill/SKILL.md"), 1)
        self.assertEqual(
            issue.annotation(),
            "::error file=example-skill/SKILL.md,line=1::missing title",
        )

    def test_annotation_without_location(self) -> None:
        issue = vnp.Issue("package directory does not exist")
        self.assertEqual(
            issue.annotation(), "::error::package directory does not exist"
        )


class TestHelpers(unittest.TestCase):
    def test_is_package_dir(self) -> None:
        self.assertTrue(vnp.is_package_dir("retail-banking"))
        self.assertFalse(vnp.is_package_dir(".github"))
        self.assertFalse(vnp.is_package_dir("scripts"))
        self.assertFalse(vnp.is_package_dir("node_modules"))
        self.assertFalse(vnp.is_package_dir(".hidden"))

    def test_non_empty_string(self) -> None:
        self.assertEqual(vnp.non_empty_string("  title  "), "title")
        self.assertIsNone(vnp.non_empty_string("   "))
        self.assertIsNone(vnp.non_empty_string(""))
        self.assertIsNone(vnp.non_empty_string(None))
        self.assertIsNone(vnp.non_empty_string(1))

    def test_catalog_skill_ids_from_text(self) -> None:
        text = json.dumps(catalog_for("retail-banking"))
        self.assertEqual(
            vnp.catalog_skill_ids_from_text(text, "catalog.json"),
            {"retail-banking"},
        )

    def test_catalog_skill_ids_from_text_skips_invalid_entries(self) -> None:
        text = json.dumps(
            {
                "skills": [
                    {"skillId": "ok"},
                    {"skillId": 1},
                    "skip",
                    {"name": "no-id"},
                ]
            }
        )
        self.assertEqual(
            vnp.catalog_skill_ids_from_text(text, "catalog.json"),
            {"ok"},
        )

    def test_catalog_skill_ids_from_text_invalid_json(self) -> None:
        with self.assertRaises(SystemExit):
            vnp.catalog_skill_ids_from_text("{", "catalog.json")


class TestParseFrontmatter(unittest.TestCase):
    def test_parses_nested_metadata_and_colons_in_values(self) -> None:
        parsed = vnp.parse_frontmatter_mapping(
            "name: example-skill\n"
            "description: Detect foo: bar with https://example.com\n"
            "metadata:\n"
            "  neo4j-card-title: Example Skill\n"
            "  neo4j-card-category: Industry Agnostic\n"
            "  neo4j-card-description: 'Short summary.'\n"
        )
        self.assertEqual(parsed["name"], "example-skill")
        self.assertEqual(
            parsed["description"],
            "Detect foo: bar with https://example.com",
        )
        self.assertEqual(
            parsed["metadata"]["neo4j-card-title"],
            "Example Skill",
        )
        self.assertEqual(
            parsed["metadata"]["neo4j-card-description"],
            "Short summary.",
        )

    def test_rejects_lists_and_unclosed_flow_values(self) -> None:
        with self.assertRaises(vnp.FrontmatterError):
            vnp.parse_frontmatter_mapping("- just a list\n")
        with self.assertRaises(vnp.FrontmatterError):
            vnp.parse_frontmatter_mapping("name: [unclosed\n")


class TestExistingSkills(unittest.TestCase):
    def test_checked_in_skill_md_files_parse(self) -> None:
        skill_files = sorted(vnp.REPO_ROOT.glob("*/SKILL.md"))
        self.assertGreater(len(skill_files), 0)
        for skill_md in skill_files:
            with self.subTest(skill=skill_md.parent.name):
                text = skill_md.read_text(encoding="utf-8").replace("\r\n", "\n")
                match = vnp.FRONTMATTER_RE.match(text)
                self.assertIsNotNone(match)
                parsed = vnp.parse_frontmatter_mapping(match.group(1))
                self.assertIsInstance(parsed, dict)
                self.assertEqual(parsed.get("name"), skill_md.parent.name)


class TestValidateSkillMd(ValidatorTestCase):
    def test_valid_skill_md(self) -> None:
        self.assertEqual(self.skill_md_issues(skill_md()), [])

    def test_accepts_crlf_and_each_allowed_category(self) -> None:
        for category in vnp.ALLOWED_CATEGORIES:
            with self.subTest(category=category):
                content = skill_md(category=category).replace("\n", "\r\n")
                self.assertEqual(self.skill_md_issues(content), [])

    def test_missing_file(self) -> None:
        messages = self.skill_md_issues(missing=True)
        self.assertTrue(
            any("missing required file SKILL.md" in msg for msg in messages)
        )

    def test_empty_file(self) -> None:
        messages = self.skill_md_issues("   \n")
        self.assertTrue(any("SKILL.md is empty" in msg for msg in messages))

    def test_missing_frontmatter(self) -> None:
        messages = self.skill_md_issues("# No frontmatter\n")
        self.assertTrue(any("YAML frontmatter" in msg for msg in messages))

    def test_invalid_yaml_frontmatter(self) -> None:
        messages = self.skill_md_issues("---\nname: [unclosed\n---\n\nBody\n")
        self.assertTrue(any("not valid YAML" in msg for msg in messages))

    def test_frontmatter_must_be_mapping(self) -> None:
        messages = self.skill_md_issues("---\n- just a list\n---\n\nBody\n")
        self.assertTrue(any("must be a YAML mapping" in msg for msg in messages))

    def test_name_must_match_directory(self) -> None:
        messages = self.skill_md_issues(skill_md(name="other-skill"))
        self.assertTrue(any("must match the directory name" in msg for msg in messages))

    def test_missing_description_and_metadata_fields(self) -> None:
        content = (
            "---\n"
            f"name: {SKILL_ID}\n"
            "description: ''\n"
            "metadata:\n"
            "  neo4j-card-title: ' '\n"
            "  neo4j-card-category: ''\n"
            "  neo4j-card-description: ''\n"
            "---\n\n"
            "Body\n"
        )
        messages = self.skill_md_issues(content)
        self.assertTrue(any("non-empty 'description'" in msg for msg in messages))
        self.assertTrue(any("neo4j-card-title" in msg for msg in messages))
        self.assertTrue(
            any("neo4j-card-category is required" in msg for msg in messages)
        )
        self.assertTrue(any("neo4j-card-description" in msg for msg in messages))

    def test_missing_metadata_mapping(self) -> None:
        content = f"---\nname: {SKILL_ID}\ndescription: A test skill.\n---\n\nBody\n"
        messages = self.skill_md_issues(content)
        self.assertTrue(any("'metadata' mapping" in msg for msg in messages))

    def test_rejects_unknown_category(self) -> None:
        messages = self.skill_md_issues(skill_md(category="General"))
        self.assertTrue(
            any("must be one of" in msg and "General" in msg for msg in messages)
        )

    def test_empty_body(self) -> None:
        messages = self.skill_md_issues(skill_md(body="   \n"))
        self.assertTrue(
            any("body after frontmatter must be non-empty" in msg for msg in messages)
        )


class TestValidateGraphModel(ValidatorTestCase):
    def test_valid_graph_model(self) -> None:
        self.assertEqual(self.graph_model_issues(VALID_GRAPH_MODEL), [])

    def test_missing_file(self) -> None:
        messages = self.graph_model_issues(missing=True)
        self.assertTrue(
            any("missing required file GRAPH_MODEL.json" in msg for msg in messages)
        )

    def test_empty_file(self) -> None:
        messages = self.graph_model_issues("   \n")
        self.assertTrue(any("GRAPH_MODEL.json is empty" in msg for msg in messages))

    def test_invalid_json(self) -> None:
        messages = self.graph_model_issues("{not json")
        self.assertTrue(any("not valid JSON" in msg for msg in messages))

    def test_json_must_be_object(self) -> None:
        messages = self.graph_model_issues("[1, 2]")
        self.assertTrue(any("must contain a JSON object" in msg for msg in messages))


class TestValidateCatalogEntry(ValidatorTestCase):
    def test_valid_catalog_entry(self) -> None:
        self.write_catalog()
        issues: list[vnp.Issue] = []
        vnp.validate_catalog_entry(SKILL_ID, issues)
        self.assertEqual(issues, [])

    def test_missing_catalog_entry(self) -> None:
        issues: list[vnp.Issue] = []
        vnp.validate_catalog_entry(SKILL_ID, issues)
        self.assertTrue(
            any("must be listed in catalog.json" in i.message for i in issues)
        )

    def test_missing_files_object(self) -> None:
        self.write_catalog({"schemaVersion": 1, "skills": [{"skillId": SKILL_ID}]})
        issues: list[vnp.Issue] = []
        vnp.validate_catalog_entry(SKILL_ID, issues)
        self.assertTrue(any("missing a 'files' object" in i.message for i in issues))

    def test_wrong_graph_and_markdown_paths(self) -> None:
        self.write_catalog(graph="model.json", markdown="README.md")
        issues: list[vnp.Issue] = []
        vnp.validate_catalog_entry(SKILL_ID, issues)
        messages = [issue.message for issue in issues]
        self.assertTrue(
            any("files.graph must be 'GRAPH_MODEL.json'" in msg for msg in messages)
        )
        self.assertTrue(
            any("files.markdown must be 'SKILL.md'" in msg for msg in messages)
        )


class TestValidatePackage(ValidatorTestCase):
    def test_missing_directory(self) -> None:
        issues = vnp.validate_package("missing-skill")
        self.assertEqual(len(issues), 1)
        self.assertIn("package directory does not exist", issues[0].message)

    def test_valid_package(self) -> None:
        self.write_skill_md(skill_md())
        self.write_graph_model()
        self.write_catalog()
        self.assertEqual(vnp.validate_package(SKILL_ID), [])

    def test_collects_issues_from_all_checks(self) -> None:
        issues = vnp.validate_package(SKILL_ID)
        messages = [issue.message for issue in issues]
        self.assertTrue(
            any("missing required file SKILL.md" in msg for msg in messages)
        )
        self.assertTrue(
            any("missing required file GRAPH_MODEL.json" in msg for msg in messages)
        )
        self.assertTrue(
            any("must be listed in catalog.json" in msg for msg in messages)
        )


class TestDiscoverNewPackages(ValidatorTestCase):
    def test_unions_new_directories_and_catalog_ids(self) -> None:
        def catalog_ids(ref: str | None) -> set[str]:
            if ref is None:
                return {"retail-banking", "new-skill"}
            return {"retail-banking"}

        with (
            patch.object(
                vnp, "top_level_dirs", return_value={".github", "retail-banking"}
            ),
            patch.object(
                vnp,
                "working_tree_top_level_dirs",
                return_value={"retail-banking", "scripts", "new-skill"},
            ),
            patch.object(vnp, "catalog_skill_ids_at", side_effect=catalog_ids),
        ):
            self.assertEqual(vnp.discover_new_packages("abc123"), ["new-skill"])

    def test_returns_empty_when_nothing_is_new(self) -> None:
        with (
            patch.object(vnp, "top_level_dirs", return_value={"retail-banking"}),
            patch.object(
                vnp, "working_tree_top_level_dirs", return_value={"retail-banking"}
            ),
            patch.object(vnp, "catalog_skill_ids_at", return_value={"retail-banking"}),
        ):
            self.assertEqual(vnp.discover_new_packages("abc123"), [])


class TestMain(ValidatorTestCase):
    def test_parse_args_reads_positional_base(self) -> None:
        args = vnp.parse_args(["abc123"])
        self.assertEqual(args.base, "abc123")

    def test_main_succeeds_when_there_are_no_new_packages(self) -> None:
        stdout = io.StringIO()
        with patch.object(vnp, "discover_new_packages", return_value=[]):
            with redirect_stdout(stdout):
                status = vnp.main(["abc123"])
        self.assertEqual(status, 0)
        self.assertIn("No new skill packages to validate.", stdout.getvalue())

    def test_main_succeeds_for_a_valid_new_package(self) -> None:
        self.write_skill_md(skill_md())
        self.write_graph_model()
        self.write_catalog()
        stdout = io.StringIO()
        with patch.object(vnp, "discover_new_packages", return_value=[SKILL_ID]):
            with redirect_stdout(stdout):
                status = vnp.main(["abc123"])
        self.assertEqual(status, 0)
        self.assertIn("Validated 1 package(s).", stdout.getvalue())

    def test_main_fails_when_a_new_package_is_invalid(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(vnp, "discover_new_packages", return_value=[SKILL_ID]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = vnp.main(["abc123"])
        self.assertEqual(status, 1)
        self.assertIn("::error", stdout.getvalue())
        self.assertIn("validation error(s)", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
