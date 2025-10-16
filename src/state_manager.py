"""State manager providing persistence for bot state."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List


@dataclass
class PositionState:
    symbol: str
    quantity: float
    entry_price: float
    timestamp: float


@dataclass
class TradeRecord:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    timestamp: float


class StateManager:
    """Persist and restore state for positions and trades."""

    def __init__(self, state_file: Path, trades_file: Path) -> None:
        self._state_file = state_file
        self._trades_file = trades_file
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._trades_file.parent.mkdir(parents=True, exist_ok=True)

    def load_positions(self) -> Dict[str, PositionState]:
        if not self._state_file.exists():
            return {}
        with self._state_file.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return {
            symbol: PositionState(**position)
            for symbol, position in raw.get("positions", {}).items()
        }

    def save_positions(self, positions: Dict[str, PositionState]) -> None:
        payload = {"positions": {symbol: asdict(pos) for symbol, pos in positions.items()}}
        with self._state_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def append_trade(self, trade: TradeRecord) -> None:
        trades = self.load_trades()
        trades.append(asdict(trade))
        with self._trades_file.open("w", encoding="utf-8") as f:
            json.dump(trades, f, indent=2)

    def load_trades(self) -> List[Dict[str, float | str]]:
        if not self._trades_file.exists():
            return []
        with self._trades_file.open("r", encoding="utf-8") as f:
            return json.load(f)


