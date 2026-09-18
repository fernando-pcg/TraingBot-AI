"""Environment and file-based configuration.

Secrets (API keys) come ONLY from environment variables. Risk rules, the allowed
universe and the macro calendar live in JSON files under ``config/`` so they can be
audited and versioned without ever touching credentials.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

DEFAULT_HOME = Path(__file__).resolve().parent.parent


def home_dir() -> Path:
    return Path(os.environ.get("ETORO_MCP_HOME", DEFAULT_HOME)).resolve()


def config_dir() -> Path:
    return home_dir() / "config"


def journal_dir() -> Path:
    return home_dir() / "journal"


@dataclass(frozen=True)
class Credentials:
    api_key: str
    user_key: str
    mode: str  # "demo" | "real"
    allow_real_trading: bool

    @property
    def is_demo(self) -> bool:
        return self.mode == "demo"

    def missing(self) -> list[str]:
        out = []
        if not self.api_key:
            out.append("ETORO_API_KEY")
        if not self.user_key:
            out.append("ETORO_USER_KEY")
        return out


def load_credentials(env: dict[str, str] | None = None) -> Credentials:
    env = os.environ if env is None else env
    mode = (env.get("ETORO_MODE") or "demo").strip().lower()
    if mode not in ("demo", "real"):
        raise ValueError(f"ETORO_MODE debe ser 'demo' o 'real', no {mode!r}")
    return Credentials(
        api_key=(env.get("ETORO_API_KEY") or "").strip(),
        user_key=(env.get("ETORO_USER_KEY") or "").strip(),
        mode=mode,
        allow_real_trading=(env.get("ETORO_ALLOW_REAL_TRADING") or "").strip().lower() == "true",
    )


@dataclass
class RiskConfig:
    capital_usd: float = 200.0
    max_risk_per_trade_pct: float = 2.0
    hard_max_risk_per_trade_pct: float = 3.0
    daily_loss_cap_pct: float = 3.0
    weekly_loss_cap_pct: float = 5.0
    max_open_positions: int = 5
    max_position_pct_of_capital: float = 40.0
    min_position_usd: float = 10.0
    max_leverage: int = 1
    min_reward_to_risk: float = 1.5
    min_stop_distance_pct: float = 0.3
    max_stop_distance_pct: float = 10.0
    max_trades_per_day: int = 2
    event_blackout_hours_before: float = 2.0
    event_blackout_hours_after: float = 1.0
    asset_event_blackout_hours_before: float = 24.0
    proposal_ttl_minutes: int = 30
    max_entry_slippage_pct: float = 0.5
    trading_paused: bool = False
    trading_paused_reason: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RiskConfig":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        cfg = cls(**clean)
        cfg.validate()
        return cfg

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def validate(self) -> None:
        if self.capital_usd <= 0:
            raise ValueError("capital_usd debe ser > 0")
        if not (0 < self.max_risk_per_trade_pct <= self.hard_max_risk_per_trade_pct):
            raise ValueError("max_risk_per_trade_pct debe estar entre 0 y hard_max_risk_per_trade_pct")
        if self.max_leverage != 1:
            raise ValueError("max_leverage debe ser 1: esta skill no opera con apalancamiento")
        if self.min_stop_distance_pct <= 0 or self.max_stop_distance_pct <= self.min_stop_distance_pct:
            raise ValueError("min_stop_distance_pct/max_stop_distance_pct inconsistentes")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions debe ser >= 1")


@dataclass
class Universe:
    etfs: list[str] = field(default_factory=list)
    large_caps: list[str] = field(default_factory=list)
    crypto: list[str] = field(default_factory=list)

    @property
    def symbols(self) -> set[str]:
        return {s.upper() for s in (*self.etfs, *self.large_caps, *self.crypto)}

    def category(self, symbol: str) -> str | None:
        s = symbol.upper()
        for name in ("etfs", "large_caps", "crypto"):
            if s in {x.upper() for x in getattr(self, name)}:
                return name
        return None


@dataclass(frozen=True)
class MacroEvent:
    name: str
    datetime_utc: str
    source: str = ""


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_risk_config(path: Path | None = None) -> RiskConfig:
    path = path or config_dir() / "risk.json"
    return RiskConfig.from_dict(_read_json(path))


def save_risk_config(cfg: RiskConfig, path: Path | None = None) -> None:
    path = path or config_dir() / "risk.json"
    existing: dict[str, Any] = {}
    if path.exists():
        existing = _read_json(path)
    existing.update(cfg.to_dict())
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_universe(path: Path | None = None) -> Universe:
    path = path or config_dir() / "universe.json"
    data = _read_json(path)
    return Universe(
        etfs=list(data.get("etfs", [])),
        large_caps=list(data.get("large_caps", [])),
        crypto=list(data.get("crypto", [])),
    )


def load_macro_calendar(path: Path | None = None) -> list[MacroEvent]:
    path = path or config_dir() / "macro_calendar.json"
    if not path.exists():
        return []
    data = _read_json(path)
    return [
        MacroEvent(name=e["name"], datetime_utc=e["datetime_utc"], source=e.get("source", ""))
        for e in data.get("events", [])
    ]
