"""End-to-end flow through the MCP tool functions with a mocked eToro API."""

import json
from pathlib import Path

import httpx
import pytest

from etoro_mcp import server
from etoro_mcp.client import EtoroClient
from etoro_mcp.config import Credentials
from etoro_mcp.journal import Journal, ProposalStore


class FakeEtoro:
    """Minimal stateful mock of the endpoints the server uses."""

    def __init__(self):
        self.credit = 200.0
        self.positions = []
        self.mirrors = []
        self.history = []
        self.ask = 500.0
        self.bid = 499.8
        self.orders_sent = []

    def handler(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path.endswith("/market-data/search"):
            return httpx.Response(200, json={"page": 1, "pageSize": 5, "totalItems": 1, "items": [{"instrumentId": 1001, "internalSymbolFull": "SPY", "displayName": "SPDR S&P 500"}]})
        if path.endswith("/market-data/instruments"):
            return httpx.Response(200, json={"instrumentDisplayDatas": [{"instrumentID": 1001, "symbolFull": "SPY", "instrumentDisplayName": "SPDR S&P 500", "instrumentTypeID": 6}]})
        if path.endswith("/market-data/instruments/rates"):
            return httpx.Response(200, json={"rates": [{"instrumentID": 1001, "bid": self.bid, "ask": self.ask, "lastExecution": self.ask}]})
        if path.endswith("/pnl"):
            return httpx.Response(200, json={"clientPortfolio": {"credit": self.credit, "positions": self.positions, "mirrors": self.mirrors, "unrealizedPnL": 0}})
        if "/history" in path:
            return httpx.Response(200, json={"items": self.history})
        if path.endswith("/market-open-orders/by-amount") or path.endswith("/limit-orders"):
            body = json.loads(req.content)
            self.orders_sent.append((path, body))
            return httpx.Response(200, json={"orderId": 42, "token": "abc"})
        return httpx.Response(404, json={"message": f"unhandled {path}"})


@pytest.fixture
def env(tmp_path, monkeypatch, repo_config_dir):
    # aislar config y bitácora en tmp
    home = tmp_path / "home"
    (home / "config").mkdir(parents=True)
    for f in ("risk.json", "universe.json", "macro_calendar.json"):
        (home / "config" / f).write_text((repo_config_dir / f).read_text(encoding="utf-8"), encoding="utf-8")
    # calendario vacío para que la fecha del test no caiga en una ventana
    (home / "config" / "macro_calendar.json").write_text('{"events": []}', encoding="utf-8")
    monkeypatch.setenv("ETORO_MCP_HOME", str(home))
    fake = FakeEtoro()
    creds = Credentials(api_key="k" * 36, user_key="u" * 36, mode="demo", allow_real_trading=False)
    svc = server.Services(creds=creds, client=EtoroClient(creds, transport=httpx.MockTransport(fake.handler)))
    svc.journal = Journal(home / "journal")
    svc.proposals = ProposalStore(home / "journal")
    monkeypatch.setattr(server, "svc", svc)
    return fake, svc, home


def test_status_reports_demo_and_caps(env):
    fake, svc, home = env
    st = server.etoro_status()
    assert st["mode"] == "demo" and st["realTradingArmed"] is False
    assert st["portfolio"]["creditAvailableUsd"] == 200.0
    assert st["lossCaps"]["weekly_cap_usd"] == 10.0
    assert st["positionsSlotsLeft"] == 5


def test_propose_then_execute_requires_confirm(env):
    fake, svc, home = env
    r = server.propose_trade("SPY", True, stop=490.0, take_profit=520.0, thesis="Ruptura de máximos semanales con volumen creciente; invalida bajo 490")
    assert r["riskCheck"]["ok"], r["riskCheck"]
    pid = r["proposalId"]
    assert pid.startswith("P-")
    assert r["sizing"]["amount_usd"] == 80.0
    assert r["entry"] == 500.0  # ask para compra

    # sin confirm no se ejecuta
    out = server.execute_proposal(pid)
    assert out["executed"] is False and "confirm" in out["reason"]
    assert fake.orders_sent == []

    out = server.execute_proposal(pid, confirm=True)
    assert out["executed"] is True, out
    path, body = fake.orders_sent[0]
    assert path.endswith("/trading/execution/demo/market-open-orders/by-amount")
    assert body == {"InstrumentID": 1001, "IsBuy": True, "Leverage": 1, "Amount": 80.0, "StopLossRate": 490.0, "TakeProfitRate": 520.0}

    # no se puede ejecutar dos veces
    again = server.execute_proposal(pid, confirm=True)
    assert again["executed"] is False and "executed" in again["reason"]

    types = [e["type"] for e in svc.journal.recent(limit=10)]
    assert types[:3] == ["execution", "approval", "proposal"]


def test_rejected_proposal_has_no_id(env):
    fake, svc, home = env
    fake.credit = 3.09
    fake.mirrors = [{"mirrorID": 1, "parentUsername": "TradIA-NXLKTXRRA", "investedAmount": 200, "positions": []}]
    r = server.propose_trade("SPY", True, stop=490.0, take_profit=520.0, thesis="Ruptura de máximos semanales con volumen creciente; invalida bajo 490")
    assert r["riskCheck"]["ok"] is False
    assert r["proposalId"] is None
    assert any("mínimo" in v for v in r["riskCheck"]["violations"])
    assert any("mirrors" in w for w in r["riskCheck"]["warnings"])


def test_execute_blocks_on_slippage(env):
    fake, svc, home = env
    r = server.propose_trade("SPY", True, stop=490.0, take_profit=520.0, thesis="Ruptura de máximos semanales con volumen creciente; invalida bajo 490")
    fake.ask = 504.0  # +0.8 %
    out = server.execute_proposal(r["proposalId"], confirm=True)
    assert out["executed"] is False and "se movió" in out["reason"]
    assert fake.orders_sent == []


def test_real_mode_needs_double_lock(env, monkeypatch):
    fake, svc, home = env
    creds = Credentials(api_key="k" * 36, user_key="u" * 36, mode="real", allow_real_trading=False)
    svc._creds = creds
    svc._client = EtoroClient(creds, transport=httpx.MockTransport(fake.handler))
    out = server.execute_proposal("P-whatever", confirm=True)
    assert out["executed"] is False and "ETORO_ALLOW_REAL_TRADING" in out["reason"]


def test_pause_switch_blocks_proposals(env):
    fake, svc, home = env
    server.set_trading_pause(True, "semana roja")
    r = server.propose_trade("SPY", True, stop=490.0, take_profit=520.0, thesis="Ruptura de máximos semanales con volumen creciente; invalida bajo 490")
    assert r["proposalId"] is None and any("PAUSA" in v for v in r["riskCheck"]["violations"])
    server.set_trading_pause(False, "nueva semana")
    assert server.risk_rules()["risk"]["trading_paused"] is False


def test_limit_order_path(env):
    fake, svc, home = env
    r = server.propose_trade("SPY", True, stop=485.0, take_profit=515.0, entry=495.0, order_type="limit", thesis="Compra en retroceso a soporte 495 con stop bajo 485")
    assert r["riskCheck"]["ok"], r["riskCheck"]
    out = server.execute_proposal(r["proposalId"], confirm=True)
    assert out["executed"], out
    path, body = fake.orders_sent[0]
    assert path.endswith("/limit-orders") and body["Rate"] == 495.0 and body["Leverage"] == 1


def test_benchmark(env):
    fake, svc, home = env
    b = server.benchmark_start("SPY")
    assert b["alreadyStarted"] is False and b["benchmark"]["accountStartEquityUsd"] == 200.0
    fake.bid = 510.0
    fake.credit = 204.0
    s = server.benchmark_status()
    assert s["benchmark"]["returnPct"] == 2.0 and s["account"]["returnPct"] == 2.0 and s["differencePct"] == 0.0
