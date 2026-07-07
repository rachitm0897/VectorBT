from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adapters.stock_strategy_profilling import load_catalogue_strategies
from schemas.strategies import CanonicalStrategy


@dataclass
class StrategyImportResult:
    imported: list[CanonicalStrategy] = field(default_factory=list)
    skipped: int = 0
    changed: int = 0
    failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "imported_count": len(self.imported),
            "skipped": self.skipped,
            "changed": self.changed,
            "failures": self.failures,
        }


class StrategyImporter:
    def import_from_stock_strategy_profilling(self, root: Path) -> StrategyImportResult:
        strategies, failures = load_catalogue_strategies(root)
        return StrategyImportResult(
            imported=strategies,
            skipped=0,
            changed=len(strategies),
            failures=failures,
        )

