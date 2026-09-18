import json
from pathlib import Path

import pytest

from etoro_mcp.config import RiskConfig, Universe


@pytest.fixture
def cfg() -> RiskConfig:
    return RiskConfig()


@pytest.fixture
def universe() -> Universe:
    return Universe(etfs=["SPY", "QQQ"], large_caps=["AAPL", "MSFT"], crypto=["BTC", "ETH"])


@pytest.fixture
def repo_config_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "config"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
