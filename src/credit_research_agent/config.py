"""Configuration defaults for the Ford debt/liquidity demo."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RUNS_DIR = PROJECT_ROOT / "runs"

DEFAULT_RUN_ID = os.getenv("RUN_ID", "ford_debt_liquidity_2023_2025")
DEFAULT_EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT", "Verified Credit Research Agent contact@example.com"
)

FORD_COMPANY = "Ford Motor Company"
FORD_TICKER = "F"
FORD_CIK = "0000037996"
SUPPORTED_RISK_THEME = "debt_liquidity"

