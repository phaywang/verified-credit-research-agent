"""Sentence-transformers embedding wrapper."""

from __future__ import annotations

from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from credit_research_agent.config import DEFAULT_EMBEDDING_MODEL


class DenseEmbedder:
    """Local embedding model with normalized vectors for cosine search."""

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        local_files_only: bool = True,
    ) -> None:
        self.model_name = model_name
        self.model = SentenceTransformer(model_name, local_files_only=local_files_only)

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        return np.asarray(
            self.model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )

    def embed_query(self, query: str) -> np.ndarray:
        return self.embed_texts([query])[0]

