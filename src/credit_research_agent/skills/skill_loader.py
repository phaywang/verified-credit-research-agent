import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ResearchSkill:
    """Loaded skill that constrains research behavior."""
    name: str
    required_evidence_categories: list[str]
    required_sections: list[str]
    require_verified_numeric_conclusions: bool = False
    unsupported_numeric_policy: str = "exclude"


def load_debt_liquidity_skill(path: Path) -> ResearchSkill:
    """Load a debt/liquidity research skill from a markdown file.

    Parses:
    - required_evidence_categories
    - required_sections
    - rules (including verified_numeric_changes_must_appear_in_conclusions)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Skill file not found: {path}")

    content = path.read_text(encoding="utf-8")

    # Extract title
    title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
    name = title_match.group(1) if title_match else "Debt and Liquidity Research Skill"

    # Extract required_evidence_categories (markdown list format)
    categories = []
    categories_match = re.search(
        r"required_evidence_categories:\s*\n((?:- .+\n?)+)",
        content
    )
    if categories_match:
        category_lines = categories_match.group(1).split("\n")
        for line in category_lines:
            match = re.match(r"- (.+)", line)
            if match:
                categories.append(match.group(1).strip())

    # Extract required_sections (markdown list format)
    sections = []
    sections_match = re.search(
        r"required_sections:\s*\n((?:- .+\n?)+)",
        content
    )
    if sections_match:
        section_lines = sections_match.group(1).split("\n")
        for line in section_lines:
            match = re.match(r"- (.+)", line)
            if match:
                sections.append(match.group(1).strip())

    # Extract verified_numeric_changes_must_appear_in_conclusions rule
    require_verified = False
    if "verified_numeric_changes_must_appear_in_conclusions: true" in content:
        require_verified = True

    return ResearchSkill(
        name=name,
        required_evidence_categories=categories,
        required_sections=sections,
        require_verified_numeric_conclusions=require_verified,
        unsupported_numeric_policy="exclude",
    )
