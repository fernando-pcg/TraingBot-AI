"""Configuration loader and schema definitions."""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel, Field, ValidationError, field_validator


class Environment(str, Enum):
    """Supported environments for the trading bot."""

    LIVE = "live"
    TESTNET = "testnet"
    BACKTEST = "backtest"


class RiskSettings(BaseModel):
    """Risk management settings."""

    initial_capital: float = Field(..., gt=0)
    max_capital_per_trade: float = Field(..., gt=0)
    stop_loss_pct: float = Field(..., gt=0, lt=1)
    take_profit_pct: float = Field(..., gt=0, lt=1)
    min_profit_margin_pct: float = Field(default=0.01, ge=0, lt=1)
    max_profit_margin_pct: float = Field(default=0.5, gt=0, le=1)
    reinvestment_pct: float = Field(default=0.5, ge=0, le=1)
    daily_loss_limit_pct: float = Field(default=0.05, gt=0, le=1)
    max_exposure_pct: float = Field(default=0.3, gt=0, le=1)

    @field_validator("max_capital_per_trade")
    @classmethod
    def validate_max_capital(cls, value: float, info: Dict[str, Any]) -> float:
        initial_capital = info.data.get("initial_capital", 0)
        if initial_capital and value > initial_capital:
            msg = "max_capital_per_trade cannot exceed initial_capital"
            raise ValueError(msg)
        return value


class StrategySettings(BaseModel):
    """Strategy-specific configuration."""

    name: str
    risk_percent: float = Field(..., gt=0, lt=1)
    stop_loss_pct: float = Field(default=0.01, gt=0, lt=1)
    take_profit_pct: float = Field(default=0.02, gt=0, lt=1)
    indicators: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class APISettings(BaseModel):
    """API credentials and settings."""

    api_key: str = os.getenv("BINANCE_API_KEY")
    api_secret: str = os.getenv("BINANCE_API_SECRET")
    use_testnet: bool = Field(default=True)


class Config(BaseModel):
    """Root configuration for the trading bot."""

    environment: Environment
    risk: RiskSettings
    strategy: StrategySettings
    binance: APISettings
    state_file: Path = Field(default=Path("state/state.json"))
    trades_history_file: Path = Field(default=Path("state/trades.json"))
    logs_dir: Path = Field(default=Path("logs"))
    dry_run: bool = Field(default=True)
    log_level: str = Field(default="INFO")


class ConfigLoader:
    """Loader for configuration profiles stored as JSON files."""

    def __init__(self, config_dir: Path | str = Path("config")) -> None:
        self._config_dir = Path(config_dir)

    def load(self, profile: str) -> Config:
        """Load and validate configuration profile."""

        file_path = self._config_dir / f"{profile}.json"
        if not file_path.exists():
            msg = f"Configuration profile '{profile}' not found at {file_path}"
            raise FileNotFoundError(msg)

        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        try:
            return Config.model_validate(data)
        except ValidationError as exc:
            msg = f"Invalid configuration for profile '{profile}': {exc}"
            raise ValueError(msg) from exc


