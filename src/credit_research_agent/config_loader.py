"""Configuration loader for multi-company, multi-theme credit research framework.

Loads company metadata, risk themes, and metrics from YAML configs.
Enables dynamic task generation without hardcoding company/theme specifics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


CONFIG_DIR = Path(__file__).parent.parent.parent / "configs"


@dataclass
class MetricDefinition:
    """Definition of a financial metric: how to extract it, what it means."""
    name: str
    description: str
    xbrl_selectors: List[Dict[str, str]] = field(default_factory=list)
    text_patterns: List[str] = field(default_factory=list)
    unit: str = "USD"
    note: str = ""


@dataclass
class CompanyConfig:
    """Metadata for a company: ticker, name, CIK, available years."""
    ticker: str
    name: str
    cik: str
    filing_types: List[str]
    fiscal_years: List[int]
    sector: str


@dataclass
class RiskThemeConfig:
    """Configuration for a risk theme: required evidence, metrics, rules."""
    name: str
    description: str
    required_evidence_categories: List[str]
    required_sections: List[str]
    key_metrics: List[str]
    comparison_years: int
    rules: List[str]


class ConfigLoader:
    """Load and cache configuration from YAML files."""

    def __init__(self, config_dir: Path = CONFIG_DIR):
        self.config_dir = config_dir
        self._companies_cache: Optional[Dict[str, CompanyConfig]] = None
        self._risk_themes_cache: Optional[Dict[str, RiskThemeConfig]] = None
        self._metrics_cache: Optional[Dict[str, MetricDefinition]] = None

    def load_companies(self) -> Dict[str, CompanyConfig]:
        """Load company configurations from configs/companies.yaml."""
        if self._companies_cache is not None:
            return self._companies_cache

        path = self.config_dir / "companies.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Companies config not found: {path}")

        raw = self._load_yaml(path)
        companies: Dict[str, CompanyConfig] = {}

        for company_id, data in raw.get("companies", {}).items():
            companies[company_id] = CompanyConfig(
                ticker=data["ticker"],
                name=data["name"],
                cik=data["cik"],
                filing_types=data.get("filing_types", ["10-K"]),
                fiscal_years=data.get("fiscal_years", []),
                sector=data.get("sector", ""),
            )

        self._companies_cache = companies
        return companies

    def load_risk_themes(self) -> Dict[str, RiskThemeConfig]:
        """Load risk theme configurations from configs/risk_themes.yaml."""
        if self._risk_themes_cache is not None:
            return self._risk_themes_cache

        path = self.config_dir / "risk_themes.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Risk themes config not found: {path}")

        raw = self._load_yaml(path)
        themes: Dict[str, RiskThemeConfig] = {}

        for theme_id, data in raw.get("risk_themes", {}).items():
            themes[theme_id] = RiskThemeConfig(
                name=theme_id,
                description=data.get("description", ""),
                required_evidence_categories=data.get("required_evidence_categories", []),
                required_sections=data.get("required_sections", []),
                key_metrics=data.get("key_metrics", []),
                comparison_years=data.get("comparison_years", 2),
                rules=data.get("rules", []),
            )

        self._risk_themes_cache = themes
        return themes

    def load_metrics(self) -> Dict[str, MetricDefinition]:
        """Load metric definitions from configs/metrics_mapping.yaml."""
        if self._metrics_cache is not None:
            return self._metrics_cache

        path = self.config_dir / "metrics_mapping.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Metrics mapping config not found: {path}")

        raw = self._load_yaml(path)
        metrics: Dict[str, MetricDefinition] = {}

        for metric_name, data in raw.get("metrics", {}).items():
            metrics[metric_name] = MetricDefinition(
                name=metric_name,
                description=data.get("description", ""),
                xbrl_selectors=data.get("xbrl_selectors", []),
                text_patterns=data.get("text_patterns", []),
                unit=data.get("unit", "USD"),
                note=data.get("note", ""),
            )

        self._metrics_cache = metrics
        return metrics

    def load_skill(self, risk_theme: str) -> str:
        """Load skill markdown for a risk theme.

        Args:
            risk_theme: e.g., "debt_liquidity_research", "leverage_analysis"

        Returns:
            Skill markdown content (raw text).

        Raises:
            FileNotFoundError: if skill not found.
        """
        path = self.config_dir / "skills" / f"{risk_theme}.md"
        if not path.exists():
            raise FileNotFoundError(f"Skill not found: {path}")

        return path.read_text(encoding="utf-8")

    def get_company(self, company_id: str) -> CompanyConfig:
        """Get configuration for a specific company.

        Args:
            company_id: e.g., "ford", "apple"

        Raises:
            KeyError: if company not found.
        """
        companies = self.load_companies()
        if company_id not in companies:
            raise KeyError(f"Unknown company: {company_id}. Available: {list(companies.keys())}")
        return companies[company_id]

    def get_risk_theme(self, theme_id: str) -> RiskThemeConfig:
        """Get configuration for a specific risk theme.

        Args:
            theme_id: e.g., "debt_liquidity", "leverage_analysis"

        Raises:
            KeyError: if theme not found.
        """
        themes = self.load_risk_themes()
        if theme_id not in themes:
            raise KeyError(f"Unknown risk theme: {theme_id}. Available: {list(themes.keys())}")
        return themes[theme_id]

    def get_metric(self, metric_name: str) -> MetricDefinition:
        """Get definition for a specific metric.

        Args:
            metric_name: e.g., "total_debt", "shareholders_equity"

        Raises:
            KeyError: if metric not found.
        """
        metrics = self.load_metrics()
        if metric_name not in metrics:
            raise KeyError(f"Unknown metric: {metric_name}. Available: {list(metrics.keys())}")
        return metrics[metric_name]

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        """Load and parse a YAML file."""
        if yaml is None:
            raise ImportError("PyYAML not installed. Install with: pip install pyyaml")

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}


# Global loader instance
_loader: Optional[ConfigLoader] = None


def get_loader(config_dir: Path = CONFIG_DIR) -> ConfigLoader:
    """Get or create the global configuration loader."""
    global _loader
    if _loader is None:
        _loader = ConfigLoader(config_dir)
    return _loader


def reset_loader() -> None:
    """Reset the global loader (for testing)."""
    global _loader
    _loader = None
