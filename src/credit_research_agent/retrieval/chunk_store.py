"""Chunk loading utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from credit_research_agent.schemas import FilingChunk


def load_chunks_jsonl(path: Path) -> List[FilingChunk]:
    chunks: List[FilingChunk] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                chunks.append(FilingChunk.model_validate(json.loads(line)))
    return chunks

