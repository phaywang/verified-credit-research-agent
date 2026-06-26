"""Text helpers shared by retrieval components."""

from __future__ import annotations

import re
from typing import List


TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9\-']*")


def tokenize(text: str) -> List[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def searchable_text(section_name: str, section_type: str, text: str) -> str:
    return f"{section_name} {section_type} {text}"

