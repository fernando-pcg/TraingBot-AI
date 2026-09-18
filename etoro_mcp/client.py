"""Thin, auditable HTTP client for the eToro public API.

Headers per request: ``x-request-id`` (UUID), ``x-api-key``, ``x-user-key``.
Demo/Real routing follows the public API convention:

  info      demo: /trading/info/demo/...        real: /trading/info/...
  execution demo: /trading/execution/demo/...   real: /trading/execution/...

Endpoint paths were taken from the public API and cross-checked against two
open-source wrappers; verify against https://api-portal.etoro.com/ on first use.
Logging goes to stderr only (stdout is the MCP stdio transport).
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import httpx

from .config import Credentials

log = logging.getLogger("etoro_mcp.client")

BASE_URL = "https://public-api.etoro.com/api/v1"

CANDLE_PERIODS = (
    "OneMinute",
    "FiveMinutes",
    "TenMinutes",
    "FifteenMinutes",
    "ThirtyMinutes",
    "OneHour",
    "FourHours",
    "OneDay",
    "OneWeek",
)


class EtoroApiError(RuntimeError):
    def __init__(self, status: int, message: str, body: Any = None):
        super().__init__(f"eToro API {status}: {message}")
        self.status = status
        self.body = body


def friendly_message(status: int, body: Any, mode: str) -> str:
    api_msg = None
    if isinstance(body, dict):
        api_msg = body.get("message") or body.get("Message") or body.get("error")
    if status in (401, 403):
        return f"Autenticación rechazada ({status}). Revisa ETORO_API_KEY / ETORO_USER_KEY y que la key sea del entorno '{mode}'."
    if status == 404:
        return f"No encontrado (404): {api_msg or 'revisa instrumentId/positionId/ruta'}"
    if status == 429:
        return "Límite de peticiones (429). Espera unos segundos y reintenta."
    if 400 <= status < 500:
        return f"Petición rechazada ({status}): {api_msg or body}"
    if status >= 500:
        return f"eToro no disponible ({status}). Reintenta en un momento."
    return f"Error {status}"


class EtoroClient:
    def __init__(
        self,
        creds: Credentials,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 20.0,
        base_url: str = BASE_URL,
    ):
        self.creds = creds
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(timeout=timeout, transport=transport)
        self.last_request_id: str | None = None

    # ---- routing -------------------------------------------------------
    @property
    def mode(self) -> str:
        return self.creds.mode

    def info_path(self, sub: str) -> str:
        return f"/trading/info/demo{sub}" if self.creds.is_demo else f"/trading/info{sub}"

    def execution_path(self, sub: str) -> str:
        return f"/trading/execution/demo{sub}" if self.creds.is_demo else f"/trading/execution{sub}"

    def pnl_path(self) -> str:
        return "/trading/info/demo/pnl" if self.creds.is_demo else "/trading/info/real/pnl"

    # ---- transport -----------------------------------------------------
    def _headers(self) -> dict[str, str]:
        self.last_request_id = str(uuid.uuid4())
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-request-id": self.last_request_id,
        }
        if self.creds.api_key:
            h["x-api-key"] = self.creds.api_key
        if self.creds.user_key:
            h["x-user-key"] = self.creds.user_key
        return h

    def request(self, method: str, path: str, *, params: dict | None = None, json: Any = None, retries: int = 1) -> Any:
        url = f"{self.base_url}{path}"
        attempt = 0
        while True:
            attempt += 1
            log.debug("%s %s params=%s", method, url, params)
            try:
                resp = self._http.request(method, url, params=params, json=json, headers=self._headers())
            except httpx.HTTPError as exc:
                if attempt <= retries:
                    time.sleep(1.5 * attempt)
                    continue
                raise EtoroApiError(0, f"Error de red: {exc}") from exc

            if resp.status_code in (429, 500, 502, 503, 504) and attempt <= retries and method == "GET":
                time.sleep(2.0 * attempt)
                continue

            body: Any
            try:
                body = resp.json() if resp.content else None
            except ValueError:
                body = resp.text

            if resp.is_error:
                raise EtoroApiError(resp.status_code, friendly_message(resp.status_code, body, self.mode), body)
            return body

    def get(self, path: str, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        return self.request("GET", path, params=clean or None)

    def post(self, path: str, body: Any) -> Any:
        return self.request("POST", path, json=body, retries=0)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path, retries=0)

    # ---- market data ---------------------------------------------------
    def search_instruments(self, query: str, *, exact_symbol: bool = False, page: int = 1, page_size: int = 10) -> Any:
        key = "internalSymbolFull" if exact_symbol else "searchText"
        return self.get("/market-data/search", **{key: query, "pageNumber": page, "pageSize": page_size})

    def instruments(self, instrument_ids: list[int]) -> Any:
        return self.get("/market-data/instruments", instrumentIds=",".join(str(i) for i in instrument_ids))

    def rates(self, instrument_ids: list[int]) -> Any:
        return self.get("/market-data/instruments/rates", instrumentIds=",".join(str(i) for i in instrument_ids))

    def candles(self, instrument_id: int, period: str, count: int = 50, direction: str = "desc") -> Any:
        if period not in CANDLE_PERIODS:
            raise ValueError(f"period debe ser uno de {CANDLE_PERIODS}")
        if direction not in ("asc", "desc"):
            raise ValueError("direction debe ser 'asc' o 'desc'")
        count = max(1, min(int(count), 1000))
        return self.get(f"/market-data/instruments/{int(instrument_id)}/history/candles/{direction}/{period}/{count}")

    # ---- account -------------------------------------------------------
    def portfolio_with_pnl(self) -> Any:
        return self.get(self.pnl_path())

    def portfolio(self) -> Any:
        return self.get(self.info_path("/portfolio"))

    def trade_history(self, min_date: str, page: int = 1, page_size: int = 100) -> Any:
        """Closed trades since ``min_date`` (YYYY-MM-DD).

        The public API exposes history under ``/trading/info/trade/history``; older
        docs use ``/trading/info/{demo|real}/history``. Try the first, fall back on 404.
        """
        params = {"minDate": min_date, "page": page, "pageSize": page_size}
        try:
            return self.get("/trading/info/trade/history", **params)
        except EtoroApiError as exc:
            if exc.status != 404:
                raise
            alt = "/trading/info/demo/history" if self.creds.is_demo else "/trading/info/real/history"
            return self.get(alt, **params)

    # ---- execution (write) --------------------------------------------
    def open_market_by_amount(
        self,
        instrument_id: int,
        amount_usd: float,
        is_buy: bool,
        stop_loss_rate: float,
        take_profit_rate: float | None,
        leverage: int = 1,
    ) -> Any:
        body: dict[str, Any] = {
            "InstrumentID": int(instrument_id),
            "IsBuy": bool(is_buy),
            "Leverage": int(leverage),
            "Amount": round(float(amount_usd), 2),
            "StopLossRate": float(stop_loss_rate),
        }
        if take_profit_rate is not None:
            body["TakeProfitRate"] = float(take_profit_rate)
        return self.post(self.execution_path("/market-open-orders/by-amount"), body)

    def place_limit_order(
        self,
        instrument_id: int,
        amount_usd: float,
        is_buy: bool,
        rate: float,
        stop_loss_rate: float,
        take_profit_rate: float | None,
        leverage: int = 1,
    ) -> Any:
        body: dict[str, Any] = {
            "InstrumentID": int(instrument_id),
            "Amount": round(float(amount_usd), 2),
            "IsBuy": bool(is_buy),
            "Rate": float(rate),
            "Leverage": int(leverage),
            "StopLossRate": float(stop_loss_rate),
        }
        if take_profit_rate is not None:
            body["TakeProfitRate"] = float(take_profit_rate)
        return self.post(self.execution_path("/limit-orders"), body)

    def close_position(self, position_id: int, instrument_id: int, units_to_deduct: float | None = None) -> Any:
        body = {"InstrumentID": int(instrument_id), "UnitsToDeduct": units_to_deduct}
        return self.post(self.execution_path(f"/market-close-orders/positions/{int(position_id)}"), body)

    def cancel_order(self, order_id: int) -> Any:
        return self.delete(self.execution_path(f"/market-open-orders/{int(order_id)}"))


# ---- response helpers (tolerant to casing differences) -------------------

def _g(d: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def trim_position(p: dict) -> dict:
    return {
        "positionId": _g(p, "positionID", "positionId"),
        "instrumentId": _g(p, "instrumentID", "instrumentId"),
        "isBuy": _g(p, "isBuy", "IsBuy"),
        "amountUsd": _g(p, "amount", "initialAmountInDollars", "Amount"),
        "units": _g(p, "units", "Units"),
        "leverage": _g(p, "leverage", "Leverage"),
        "openRate": _g(p, "openRate", "OpenRate"),
        "currentRate": _g(p, "currentRate", "CurrentRate"),
        "stopLossRate": _g(p, "stopLossRate", "StopLossRate"),
        "takeProfitRate": _g(p, "takeProfitRate", "TakeProfitRate"),
        "unrealizedPnl": _g(p, "unrealizedPnL", "unrealizedPnl", "profit"),
        "openDateTime": _g(p, "openDateTime", "OpenDateTime"),
        "totalFees": _g(p, "totalFees", "TotalFees"),
    }


def trim_mirror(m: dict) -> dict:
    positions = _g(m, "positions", "Positions", default=[]) or []
    return {
        "mirrorId": _g(m, "mirrorID", "mirrorId"),
        "parentCid": _g(m, "parentCID", "parentCid"),
        "parentUsername": _g(m, "parentUsername", "ParentUsername"),
        "initialInvestmentUsd": _g(m, "initialInvestment", "InitialInvestment"),
        "availableAmountUsd": _g(m, "availableAmount", "AvailableAmount"),
        "investedUsd": _g(m, "investedAmount", "InvestedAmount"),
        "netProfitUsd": _g(m, "netProfit", "NetProfit", "unrealizedPnL"),
        "stopLossPercentage": _g(m, "stopLossPercentage", "StopLossPercentage"),
        "stopLossAmountUsd": _g(m, "stopLossAmount", "StopLossAmount"),
        "copyExistingPositions": _g(m, "copyExistingPositions", "CopyExistingPositions"),
        "startedAt": _g(m, "startedCopyDate", "StartedCopyDate", "openDateTime"),
        "positionsCount": len(positions),
        "positions": [trim_position(p) for p in positions],
    }


def summarize_portfolio(raw: Any) -> dict:
    cp = raw.get("clientPortfolio", raw) if isinstance(raw, dict) else {}
    positions = _g(cp, "positions", "Positions", default=[]) or []
    mirrors = _g(cp, "mirrors", "Mirrors", default=[]) or []
    orders = []
    for key in ("orders", "stockOrders", "entryOrders", "ordersForOpen"):
        orders.extend(_g(cp, key, default=[]) or [])
    invested = sum(float(_g(p, "amount", "initialAmountInDollars", "Amount", default=0) or 0) for p in positions)
    copy_invested = 0.0
    for m in mirrors:
        copy_invested += float(_g(m, "investedAmount", "InvestedAmount", default=0) or 0)
        copy_invested += float(_g(m, "availableAmount", "AvailableAmount", default=0) or 0)
    credit = float(_g(cp, "credit", "Credit", default=0) or 0)
    unrealized = _g(cp, "unrealizedPnL", "unrealizedPnl")
    if unrealized is None:
        unrealized = sum(float(_g(p, "unrealizedPnL", "unrealizedPnl", "profit", default=0) or 0) for p in positions)
    return {
        "creditAvailableUsd": round(credit, 2),
        "directInvestedUsd": round(invested, 2),
        "copyInvestedUsd": round(copy_invested, 2),
        "unrealizedPnlUsd": round(float(unrealized or 0), 2),
        "equityEstimateUsd": round(credit + invested + copy_invested + float(unrealized or 0), 2),
        "positionsCount": len(positions),
        "positions": [trim_position(p) for p in positions],
        "mirrorsCount": len(mirrors),
        "mirrors": [trim_mirror(m) for m in mirrors],
        "pendingOrdersCount": len(orders),
        "pendingOrders": orders,
    }
