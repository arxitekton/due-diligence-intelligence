import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"


def _frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md must start with YAML frontmatter"
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def test_skill_has_name_and_description():
    fm = _frontmatter(SKILL.read_text())
    assert fm.get("name") == "company-due-diligence"
    assert 20 <= len(fm.get("description", "")) <= 1024


def test_skill_links_resolve():
    text = SKILL.read_text()
    for rel in re.findall(r"\]\((prompts/[^)]+|references/[^)]+)\)", text):
        assert (ROOT / rel).exists(), f"SKILL.md links missing file: {rel}"


def test_skill_is_concise():
    assert len(SKILL.read_text().splitlines()) <= 200, "SKILL.md should stay concise"
