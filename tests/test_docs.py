"""The documentation and the samples must not drift away from the code."""
import configparser
import re
from pathlib import Path

import pytest

from conftest import load_script

ROOT = Path(__file__).resolve().parent.parent
READMES = ["README.md", "README.ja.md"]
DOCS = READMES + ["docs/reference.md", "docs/reference.ja.md", "docs/comparison.md",
                  "docs/comparison.ja.md"]
CONFIG_SAMPLES = sorted(p for p in (ROOT / "examples").iterdir() if p.is_file())
AGENT_SAMPLES = sorted((ROOT / "examples" / "agents").iterdir())


def table_keys(text, section):
    """First-column `keys` of the table that follows the first mention of `[section]`."""
    start = text.index("`[%s]`" % section)
    keys = []
    for line in text[start:].split("\n")[1:]:
        if line.startswith("|"):
            match = re.match(r"\| `([a-z_]+)` \|", line)
            if match:
                keys.append(match.group(1))
        elif keys:
            break
    return keys


@pytest.mark.parametrize("name", READMES)
def test_readme_tables_list_every_setting(name):
    module = load_script()
    text = (ROOT / name).read_text(encoding="utf-8")
    assert sorted(table_keys(text, "launch_claude")) == sorted(module.CONFIG_KEYS)
    assert sorted(table_keys(text, "agent")) == sorted(module.AGENT_KEYS)


def sample_keys(path, section, include_commented):
    text = path.read_text(encoding="utf-8")
    if include_commented:  # "# key = value" lines document keys that are off by default
        text = re.sub(r"(?m)^# ([a-z_]+ = )", r"\1", text)
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(text)
    return set(parser[section])


@pytest.mark.parametrize("path", CONFIG_SAMPLES, ids=lambda p: p.name)
def test_config_samples_use_known_keys(path):
    module = load_script()
    assert sample_keys(path, "launch_claude", True) <= set(module.CONFIG_KEYS)


@pytest.mark.parametrize("path", AGENT_SAMPLES, ids=lambda p: p.name)
def test_agent_samples_use_known_keys(path):
    module = load_script()
    assert sample_keys(path, "agent", True) <= set(module.AGENT_KEYS)


def test_reference_samples_document_every_key():
    module = load_script()
    assert sample_keys(ROOT / "examples" / "config.example", "launch_claude", True) == set(module.CONFIG_KEYS)
    assert sample_keys(ROOT / "examples" / "agents" / "example.conf", "agent", True) == set(module.AGENT_KEYS)


def test_reference_config_sample_changes_nothing_as_is():
    assert sample_keys(ROOT / "examples" / "config.example", "launch_claude", False) == set()


@pytest.mark.parametrize("name", DOCS)
def test_relative_links_point_to_existing_files(name):
    path = ROOT / name
    for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", path.read_text(encoding="utf-8")):
        if "://" in target:
            continue
        assert (path.parent / target).exists(), "%s links to missing %s" % (name, target)


@pytest.mark.parametrize("name", READMES)
def test_readme_contents_list_every_section(name):
    text = (ROOT / name).read_text(encoding="utf-8")
    text = re.sub(r"(?s)```.*?```", "", text)  # "## ..." inside code blocks is not a heading
    headings = re.findall(r"(?m)^## (.+)$", text)
    listed = re.findall(r"(?m)^- \[([^\]]+)\]\(#([^)]+)\)$", text)
    assert [title for title, _ in listed] == headings[1:]  # the first heading is the list itself
    for title, anchor in listed:
        assert anchor == title.lower().replace(" ", "-")


def test_help_lists_every_command():
    module = load_script()
    for command in module.COMMANDS:
        assert "launch_claude " + command in module.USAGE
