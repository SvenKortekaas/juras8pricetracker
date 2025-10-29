#!/usr/bin/env python3
"""Update project changelog files following Keep a Changelog guidelines."""

from __future__ import annotations

import argparse
import re
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


SKIP_PATTERNS = [
    r"^chore: bump ",
    r"^docs: update changelog",
    r"^Merge ",
    r"^Update CHANGELOG",
]

CATEGORY_MAPPING = OrderedDict(
    [
        ("Added", ["feat", "feature", "add", "introduc", "implement", "initial"]),
        ("Changed", ["change", "chore", "refactor", "update", "improv", "sync", "bump", "upgrade"]),
        ("Fixed", ["fix", "bugfix", "resolve", "hotfix", "patch"]),
        ("Removed", ["remove", "delete", "drop"]),
        ("Documentation", ["docs", "doc", "readme"]),
        ("CI", ["ci", "build", "workflow"]),
        ("Security", ["security"]),
    ]
)

DEFAULT_CATEGORY = "Changed"


@dataclass(frozen=True)
class CommitEntry:
    subject: str
    author: str


def run_git(args: Sequence[str]) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def get_repo_slug() -> str:
    remote_url = run_git(["config", "--get", "remote.origin.url"])
    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]

    patterns = [
        r"git@github\.com:(?P<slug>.+)",
        r"https://github\.com/(?P<slug>.+)",
        r"ssh://git@github\.com/(?P<slug>.+)",
    ]

    for pattern in patterns:
        match = re.match(pattern, remote_url)
        if match:
            return match.group("slug")

    raise RuntimeError(f"Unable to determine GitHub slug from remote URL: {remote_url}")


def normalize_tag(tag: str | None) -> str | None:
    if not tag or tag == "v0.0.0":
        return None
    return tag


def skipped(subject: str) -> bool:
    return any(re.search(pattern, subject) for pattern in SKIP_PATTERNS)


def collect_commits(previous_tag: str | None) -> List[CommitEntry]:
    range_spec = ["HEAD"]
    if previous_tag:
        range_spec = [f"{previous_tag}..HEAD"]

    raw = run_git(
        ["log", "--reverse", "--pretty=format:%s%x1f%an%x1e", "--no-merges", *range_spec]
    )

    entries: list[CommitEntry] = []
    for record in raw.split("\x1e"):
        record = record.strip()
        if not record:
            continue
        try:
            subject, author = record.split("\x1f")
        except ValueError:
            subject, author = record, ""
        subject = subject.strip()
        author = author.strip()
        if skipped(subject):
            continue
        entries.append(CommitEntry(subject=subject, author=author))

    # Remove duplicates while preserving order
    seen = set()
    unique_entries: list[CommitEntry] = []
    for entry in entries:
        key = (entry.subject, entry.author)
        if key in seen:
            continue
        seen.add(key)
        unique_entries.append(entry)
    return unique_entries


def categorize_commits(commits: Iterable[CommitEntry]) -> OrderedDict[str, List[str]]:
    categories = OrderedDict((name, []) for name in CATEGORY_MAPPING.keys())
    categories.setdefault(DEFAULT_CATEGORY, [])
    categories.setdefault("Other", [])

    for entry in commits:
        subject_lower = entry.subject.lower()
        selected_category = None
        for category, prefixes in CATEGORY_MAPPING.items():
            if any(subject_lower.startswith(prefix) for prefix in prefixes):
                selected_category = category
                break
        if not selected_category:
            selected_category = DEFAULT_CATEGORY if DEFAULT_CATEGORY in categories else "Other"
        categories[selected_category].append(format_commit(entry))

    # Remove empty categories
    return OrderedDict((cat, items) for cat, items in categories.items() if items)


def format_commit(entry: CommitEntry) -> str:
    if entry.author:
        return f"{entry.subject} ({entry.author})"
    return entry.subject


def ensure_changelog_skeleton(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")

    header = "# Changelog\nAll notable changes to this project are documented in this file.\n\n"
    header += "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),\n"
    header += "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n"
    header += "## [Unreleased]\n"
    return header


def insert_new_section(content: str, new_section: str) -> str:
    if "## [Unreleased]" not in content:
        content = content.rstrip() + "\n\n## [Unreleased]\n"

    pattern = re.compile(r"(## \[Unreleased\][\s\S]*?)(?=^## \[[^\]]+\]|\Z)", flags=re.MULTILINE)
    match = pattern.search(content)
    if not match:
        # Should not happen, but fallback by appending after Unreleased header.
        return content.rstrip() + "\n\n" + new_section

    unreleased_block = match.group(1)
    if not unreleased_block.endswith("\n\n"):
        unreleased_block = unreleased_block.rstrip() + "\n\n"

    updated_block = unreleased_block + new_section + "\n"
    return content[: match.start()] + updated_block + content[match.end():]


def build_section(version: str, release_date: str, categories: OrderedDict[str, List[str]]) -> str:
    lines = [f"## [{version}] - {release_date}"]
    for category, entries in categories.items():
        if not entries:
            continue
        lines.append(f"### {category}")
        lines.extend(f"- {entry}" for entry in entries)
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def update_reference_links(content: str, tags: Sequence[str], repo_slug: str) -> str:
    tags = [tag for tag in tags if tag]
    if not tags:
        return content

    lines = []
    latest = tags[0]
    lines.append(f"[Unreleased]: https://github.com/{repo_slug}/compare/{latest}...HEAD")

    for current, previous in zip(tags, tags[1:]):
        lines.append(
            f"[{current.lstrip('v')}]: https://github.com/{repo_slug}/compare/{previous}...{current}"
        )

    last = tags[-1]
    lines.append(
        f"[{last.lstrip('v')}]: https://github.com/{repo_slug}/releases/tag/{last}"
    )

    link_block = "\n".join(lines)

    match = re.search(r"^\[Unreleased\]:.*$", content, flags=re.MULTILINE)
    if match:
        trimmed = content[: match.start()].rstrip()
        return f"{trimmed}\n\n{link_block}\n"

    return content.rstrip() + "\n\n" + link_block + "\n"


def get_sorted_tags() -> List[str]:
    raw = run_git(["tag", "--sort=-v:refname"])
    if not raw:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def render_and_write(path: Path, new_section: str, repo_slug: str, tags: Sequence[str]) -> None:
    content = ensure_changelog_skeleton(path)
    updated = insert_new_section(content, new_section)
    updated = update_reference_links(updated, tags, repo_slug)
    path.write_text(updated, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update changelog files for a new release.")
    parser.add_argument("--new-tag", required=True, help="New tag name (e.g. v1.2.3)")
    parser.add_argument(
        "--previous-tag", default="", help="Previous tag name (e.g. v1.2.2); optional."
    )
    parser.add_argument("--date", required=True, help="Release date in YYYY-MM-DD format.")
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Changelog file paths to update (each receives the new entry).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    new_tag = args.new_tag
    previous_tag = normalize_tag(args.previous_tag)

    commits = collect_commits(previous_tag)
    categories = categorize_commits(commits)
    if not categories:
        categories = OrderedDict([(DEFAULT_CATEGORY, ["No notable changes recorded."])])
    version = new_tag.lstrip("v")
    new_section = build_section(version, args.date, categories)

    repo_slug = get_repo_slug()
    tags = get_sorted_tags()

    for file_path in args.files:
        render_and_write(Path(file_path), new_section, repo_slug, tags)


if __name__ == "__main__":
    main()
