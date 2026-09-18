import json

import httpx
import pytest

from etoro_mcp.client import EtoroApiError, EtoroClient, summarize_portfolio
from etoro_mcp.config import Credentials, load_credentials


def make_client(mode: str, handler):
    creds = Credentials(api_key="k" * 36, user_key="u" * 36, mode=mode, allow_real_trading=False)
    return EtoroClient(creds, transport=httpx.MockTransport(handler))


def test_load_credentials_defaults_to_demo():
    c = load_credentials({"ETORO_API_KEY": "a", "ETORO_USER_KEY": "b"})
    assert c.mode == "demo" and c.is_demo and not c.allow_real_trading and c.missing() == []
    c = load_credentials({})
    assert c.missing() == ["ETORO_API_KEY", "ETORO_USER_KEY"]
    with pytest.raises(ValueError):
        load_credentials({"ETORO_MODE": "live"})


def test_headers_and_demo_routing():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["headers"] = dict(req.headers)
        return httpx.Response(200, json={"clientPortfolio": {"credit": 3.09, "positions": []}})

    c = make_client("demo", handler)
    c.portfolio_with_pnl()
    assert seen["url"].endswith("/api/v1/trading/info/demo/pnl")
    assert seen["headers"]["x-api-key"] == "k" * 36
    assert seen["headers"]["x-user-key"] == "u" * 36
    assert len(seen["headers"]["x-request-id"]) == 36
    assert c.info_path("/portfolio") == "/trading/info/demo/portfolio"
    assert c.execution_path("/limit-orders") == "/trading/execution/demo/limit-orders"


def test_real_routing():
    c = make_client("real", lambda r: httpx.Response(200, json={}))
    assert c.pnl_path() == "/trading/info/real/pnl"
    assert c.info_path("/portfolio") == "/trading/info/portfolio"
    assert c.execution_path("/market-open-orders/by-amount") == "/trading/execution/market-open-orders/by-amount"


def test_open_market_body_and_path():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"orderId": 1})

    c = make_client("demo", handler)
    c.open_market_by_amount(1001, 79.999, True, 490.0, 520.0)
    assert seen["url"].endswith("/trading/execution/demo/market-open-orders/by-amount")
    assert seen["body"] == {"InstrumentID": 1001, "IsBuy": True, "Leverage": 1, "Amount": 80.0, "StopLossRate": 490.0, "TakeProfitRate": 520.0}


def test_close_and_cancel_paths():
    calls = []

    def handler(req: httpx.Request):
        calls.append((req.method, str(req.url), req.content))
        return httpx.Response(200, json={})

    c = make_client("demo", handler)
    c.close_position(555, 1001)
    c.cancel_order(777)
    assert calls[0][0] == "POST" and calls[0][1].endswith("/market-close-orders/positions/555")
    assert json.loads(calls[0][2]) == {"InstrumentID": 1001, "UnitsToDeduct": None}
    assert calls[1][0] == "DELETE" and calls[1][1].endswith("/trading/execution/demo/market-open-orders/777")


def test_error_mapping_and_no_retry_on_post():
    n = {"count": 0}

    def handler(req: httpx.Request):
        n["count"] += 1
        return httpx.Response(401, json={"message": "bad key"})

    c = make_client("demo", handler)
    with pytest.raises(EtoroApiError) as exc:
        c.post("/x", {})
    assert exc.value.status == 401 and "Autenticación" in str(exc.value)
    assert n["count"] == 1


def test_history_fallback_on_404():
    urls = []

    def handler(req: httpx.Request):
        urls.append(req.url.path)
        if req.url.path.endswith("/trade/history"):
            return httpx.Response(404, json={"message": "nope"})
        return httpx.Response(200, json={"items": []})

    c = make_client("demo", handler)
    c.trade_history("2026-09-14")
    assert urls == ["/api/v1/trading/info/trade/history", "/api/v1/trading/info/demo/history"]


def test_candles_validation():
    c = make_client("demo", lambda r: httpx.Response(200, json=[]))
    with pytest.raises(ValueError):
        c.candles(1, "Weekly")
    with pytest.raises(ValueError):
        c.candles(1, "OneDay", direction="up")


def test_summarize_portfolio_with_copy():
    raw = {
        "clientPortfolio": {
            "credit": 3.09,
            "positions": [{"positionID": 1, "instrumentID": 1001, "isBuy": True, "amount": 20, "unrealizedPnL": -0.5, "openDateTime": "2026-09-18T09:00:00Z"}],
            "mirrors": [{"mirrorID": 9, "parentUsername": "TradIA-NXLKTXRRA", "initialInvestment": 200, "investedAmount": 150, "availableAmount": 50, "netProfit": 0, "stopLossPercentage": 40, "positions": [{"positionID": 2, "instrumentID": 1002}]}],
            "orders": [{"orderID": 5}],
        }
    }
    s = summarize_portfolio(raw)
    assert s["creditAvailableUsd"] == 3.09
    assert s["directInvestedUsd"] == 20
    assert s["copyInvestedUsd"] == 200
    assert s["unrealizedPnlUsd"] == -0.5
    assert s["equityEstimateUsd"] == 222.59
    assert s["mirrors"][0]["parentUsername"] == "TradIA-NXLKTXRRA"
    assert s["mirrors"][0]["positionsCount"] == 1
    assert s["pendingOrdersCount"] == 1
