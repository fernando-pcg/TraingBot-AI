"""MCP server: eToro public API + risk rules + mandatory human approval.

Flow the tools enforce:

    etoro_status / market data  ->  propose_trade (risk check, stores P-xxxx)
    -> user says "CONFIRMO P-xxxx" -> execute_proposal(P-xxxx, confirm=True)
    -> bitácora entry

No tool opens, closes or cancels anything without ``confirm=True`` and, for
opens, a proposal that already passed the rules. In Real mode an extra env
variable (``ETORO_ALLOW_REAL_TRADING=true``) is required.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import __version__
from .client import EtoroApiError, EtoroClient, summarize_portfolio, trim_mirror
from .config import (
    Credentials,
    RiskConfig,
    load_credentials,
    load_macro_calendar,
    load_risk_config,
    load_universe,
    save_risk_config,
)
from .journal import EVENT_TYPES, Journal, ProposalStore
from .risk import (
    AccountState,
    active_blackouts,
    day_start,
    evaluate,
    loss_caps_status,
    opened_since,
    realized_pnl_since,
    utcnow,
    week_start,
)

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("etoro_mcp")

READ = ToolAnnotations(read_only_hint=True, open_world_hint=True)
READ_LOCAL = ToolAnnotations(read_only_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=True)
LOCAL_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)

INSTRUCTIONS = """Servidor MCP para operar en eToro con reglas de riesgo estrictas.
Protocolo: analiza -> propose_trade -> espera el OK explícito del usuario ("CONFIRMO P-xxxx")
-> execute_proposal(confirm=true) -> registra en bitácora. Nunca ejecutes sin confirmación.
Por defecto trabaja en cuenta DEMO."""


class Services:
    """Lazy holder so import/tests don't need credentials."""

    def __init__(self, creds: Credentials | None = None, client: EtoroClient | None = None):
        self._creds = creds
        self._client = client
        self.journal = Journal()
        self.proposals = ProposalStore()
        self._symbol_cache: dict[int, dict] = {}

    @property
    def creds(self) -> Credentials:
        if self._creds is None:
            self._creds = load_credentials()
        return self._creds

    @property
    def client(self) -> EtoroClient:
        if self._client is None:
            self._client = EtoroClient(self.creds)
        return self._client

    # ---- instrument helpers -------------------------------------------
    def instrument_meta(self, instrument_ids: list[int]) -> dict[int, dict]:
        missing = [i for i in instrument_ids if i not in self._symbol_cache]
        if missing:
            data = self.client.instruments(missing)
            items = data.get("instrumentDisplayDatas", data) if isinstance(data, dict) else data
            for inst in items or []:
                iid = inst.get("instrumentID") or inst.get("instrumentId")
                if iid is not None:
                    self._symbol_cache[int(iid)] = {
                        "instrumentId": int(iid),
                        "symbol": inst.get("symbolFull") or inst.get("internalSymbolFull"),
                        "name": inst.get("instrumentDisplayName") or inst.get("displayName"),
                        "instrumentTypeId": inst.get("instrumentTypeID") or inst.get("instrumentTypeId"),
                        "exchangeId": inst.get("exchangeID") or inst.get("exchangeId"),
                    }
        return {i: self._symbol_cache[i] for i in instrument_ids if i in self._symbol_cache}

    def resolve_symbol(self, symbol: str) -> dict:
        sym = symbol.strip().upper()
        for meta in self._symbol_cache.values():
            if (meta.get("symbol") or "").upper() == sym:
                return meta
        data = self.client.search_instruments(sym, exact_symbol=True, page_size=5)
        items = data.get("items", []) if isinstance(data, dict) else []
        if not items:
            data = self.client.search_instruments(sym, exact_symbol=False, page_size=10)
            items = data.get("items", []) if isinstance(data, dict) else []
            items = [i for i in items if (i.get("internalSymbolFull") or "").upper() == sym]
        if not items:
            raise ValueError(f"No encuentro el instrumento {sym} en eToro")
        iid = int(items[0]["instrumentId"])
        meta = self.instrument_meta([iid]).get(iid) or {"instrumentId": iid, "symbol": sym}
        if not meta.get("symbol"):
            meta["symbol"] = sym
        return meta

    def quote(self, instrument_id: int) -> dict:
        data = self.client.rates([instrument_id])
        rows = data.get("rates", data) if isinstance(data, dict) else data
        if isinstance(rows, dict):
            rows = [rows]
        for r in rows or []:
            iid = r.get("instrumentID") or r.get("instrumentId")
            if iid is not None and int(iid) == int(instrument_id):
                bid = r.get("bid", r.get("Bid"))
                ask = r.get("ask", r.get("Ask"))
                last = r.get("lastExecution", r.get("LastExecution"))
                spread_pct = None
                if bid and ask:
                    spread_pct = round((float(ask) - float(bid)) / float(ask) * 100, 4)
                return {"instrumentId": int(iid), "bid": bid, "ask": ask, "last": last, "spreadPct": spread_pct, "raw": r}
        raise ValueError(f"Sin cotización para el instrumento {instrument_id}")

    # ---- account state ---------------------------------------------------
    def account_state(self, now: datetime | None = None) -> tuple[AccountState, dict, dict]:
        now = now or utcnow()
        summary = summarize_portfolio(self.client.portfolio_with_pnl())
        pos_ids = [int(p["instrumentId"]) for p in summary["positions"] if p.get("instrumentId") is not None]
        meta = self.instrument_meta(pos_ids) if pos_ids else {}
        for p in summary["positions"]:
            m = meta.get(int(p["instrumentId"])) if p.get("instrumentId") is not None else None
            p["symbol"] = m.get("symbol") if m else None
        symbols = {p["symbol"] for p in summary["positions"] if p.get("symbol")}

        ws = week_start(now)
        history: list[dict] = []
        history_error = None
        try:
            hist = self.client.trade_history(f"{ws:%Y-%m-%d}", page_size=200)
            if isinstance(hist, dict):
                history = hist.get("items") or hist.get("trades") or hist.get("data") or []
            elif isinstance(hist, list):
                history = hist
        except EtoroApiError as exc:
            history_error = str(exc)
        pnl_week, n_week = realized_pnl_since(history, ws)
        pnl_day, n_day = realized_pnl_since(history, day_start(now))
        raw_positions = [p for p in summary["positions"]]
        state = AccountState(
            available_credit=summary["creditAvailableUsd"],
            open_positions=summary["positionsCount"],
            open_symbols=symbols,
            realized_pnl_today=pnl_day,
            realized_pnl_week=pnl_week,
            unrealized_pnl=summary["unrealizedPnlUsd"],
            trades_opened_today=opened_since(raw_positions, day_start(now)),
            copy_invested_usd=summary["copyInvestedUsd"],
        )
        extra = {
            "closedTradesThisWeek": n_week,
            "closedTradesToday": n_day,
            "historyError": history_error,
            "weekStartUtc": ws.isoformat(),
        }
        return state, summary, extra


svc = Services()
mcp = MCPServer(name="etoro", version=__version__, instructions=INSTRUCTIONS)


def _mask(key: str) -> str:
    return "(no configurada)" if not key else f"{key[:4]}…{key[-4:]} ({len(key)} chars)"


def _write_gate(cfg: RiskConfig, confirm: bool) -> str | None:
    """Return a refusal reason or None when a write is allowed."""
    if not confirm:
        return "confirm=false: pide al usuario el OK explícito y vuelve a llamar con confirm=true"
    creds = svc.creds
    if creds.missing():
        return f"Faltan variables de entorno: {', '.join(creds.missing())}"
    if not creds.is_demo and not creds.allow_real_trading:
        return "Modo REAL sin ETORO_ALLOW_REAL_TRADING=true: no se ejecuta nada con dinero real"
    return None


# ======================================================================
# Estado y datos de mercado (solo lectura)
# ======================================================================

@mcp.tool(annotations=READ, description="Estado completo: modo (demo/real), keys presentes, reglas de riesgo, topes de pérdida diaria/semanal, ventanas de evento activas y resumen del portafolio (posiciones directas, copias/CopyTrader, órdenes pendientes). Llama a esto al empezar cada sesión.")
def etoro_status() -> dict[str, Any]:
    creds = svc.creds
    cfg = load_risk_config()
    out: dict[str, Any] = {
        "mode": creds.mode,
        "realTradingArmed": (not creds.is_demo) and creds.allow_real_trading,
        "apiKey": _mask(creds.api_key),
        "userKey": _mask(creds.user_key),
        "missingEnv": creds.missing(),
        "risk": cfg.to_dict(),
        "nowUtc": utcnow().isoformat(timespec="seconds"),
    }
    events = load_macro_calendar()
    out["activeEventBlackouts"] = [e.__dict__ for e in active_blackouts(utcnow(), events, cfg.event_blackout_hours_before, cfg.event_blackout_hours_after)]
    if creds.missing():
        out["error"] = "Configura ETORO_API_KEY y ETORO_USER_KEY en variables de entorno (ver .env.example)"
        return out
    try:
        state, summary, extra = svc.account_state()
    except (EtoroApiError, ValueError) as exc:
        out["error"] = str(exc)
        return out
    out["portfolio"] = summary
    out["lossCaps"] = loss_caps_status(cfg, state)
    out["tradesOpenedToday"] = state.trades_opened_today
    out["history"] = extra
    out["positionsSlotsLeft"] = max(0, cfg.max_open_positions - state.open_positions)
    return out


@mcp.tool(annotations=READ, description="Portafolio con P&L: crédito disponible, posiciones directas (con símbolo), copias (mirrors/CopyTrader) y órdenes pendientes, según el modo demo/real.")
def etoro_portfolio() -> dict[str, Any]:
    _, summary, extra = svc.account_state()
    summary["history"] = extra
    return summary


@mcp.tool(annotations=READ, description="Estado de las copias (CopyTrader): inversión inicial, valor, P&L, stop de copia y posiciones que mantiene el copiado. Útil cuando el capital está asignado a un trader copiado en vez de operarse directo.")
def etoro_copy_status() -> dict[str, Any]:
    raw = svc.client.portfolio_with_pnl()
    cp = raw.get("clientPortfolio", raw) if isinstance(raw, dict) else {}
    mirrors = cp.get("mirrors") or cp.get("Mirrors") or []
    trimmed = [trim_mirror(m) for m in mirrors]
    ids = sorted({int(p["instrumentId"]) for m in trimmed for p in m["positions"] if p.get("instrumentId") is not None})
    meta = svc.instrument_meta(ids) if ids else {}
    for m in trimmed:
        for p in m["positions"]:
            mm = meta.get(int(p["instrumentId"])) if p.get("instrumentId") is not None else None
            p["symbol"] = mm.get("symbol") if mm else None
    return {"mode": svc.creds.mode, "mirrorsCount": len(trimmed), "mirrors": trimmed}


@mcp.tool(annotations=READ, description="Busca instrumentos por texto o ticker exacto (exact_symbol=true). Devuelve instrumentId, símbolo y nombre.")
def etoro_search_instruments(query: str, exact_symbol: bool = False, page_size: int = 10) -> dict[str, Any]:
    data = svc.client.search_instruments(query, exact_symbol=exact_symbol, page_size=max(1, min(page_size, 50)))
    items = data.get("items", []) if isinstance(data, dict) else []
    ids = [int(i["instrumentId"]) for i in items if i.get("instrumentId")]
    meta = svc.instrument_meta(ids) if ids else {}
    universe = load_universe()
    return {
        "total": data.get("totalItems") if isinstance(data, dict) else None,
        "items": [
            {
                "instrumentId": int(i["instrumentId"]),
                "symbol": (meta.get(int(i["instrumentId"])) or {}).get("symbol") or i.get("internalSymbolFull"),
                "name": (meta.get(int(i["instrumentId"])) or {}).get("name") or i.get("displayName"),
                "instrumentTypeId": (meta.get(int(i["instrumentId"])) or {}).get("instrumentTypeId") or i.get("instrumentTypeId"),
                "inUniverse": ((meta.get(int(i["instrumentId"])) or {}).get("symbol") or i.get("internalSymbolFull") or "").upper() in universe.symbols,
            }
            for i in items
            if i.get("instrumentId")
        ],
    }


@mcp.tool(annotations=READ, description="Cotización en vivo (bid/ask/último y spread %) de uno o varios símbolos, por ejemplo ['SPY','BTC'].")
def etoro_quote(symbols: list[str]) -> dict[str, Any]:
    out = []
    for s in symbols:
        meta = svc.resolve_symbol(s)
        q = svc.quote(int(meta["instrumentId"]))
        q.pop("raw", None)
        q["symbol"] = meta.get("symbol")
        q["name"] = meta.get("name")
        out.append(q)
    return {"quotes": out, "nowUtc": utcnow().isoformat(timespec="seconds")}


@mcp.tool(annotations=READ, description="Velas OHLCV de un símbolo. period: OneMinute, FiveMinutes, TenMinutes, FifteenMinutes, ThirtyMinutes, OneHour, FourHours, OneDay, OneWeek. Devuelve las más recientes primero.")
def etoro_candles(symbol: str, period: str = "OneDay", count: int = 60) -> dict[str, Any]:
    meta = svc.resolve_symbol(symbol)
    data = svc.client.candles(int(meta["instrumentId"]), period, count=count, direction="desc")
    return {"symbol": meta.get("symbol"), "instrumentId": meta["instrumentId"], "period": period, "data": data}


@mcp.tool(annotations=READ, description="Historial de operaciones cerradas desde min_date (YYYY-MM-DD). Base para calcular racha, win-rate y el tope de pérdida semanal.")
def etoro_trade_history(min_date: str, page: int = 1, page_size: int = 100) -> dict[str, Any]:
    datetime.strptime(min_date, "%Y-%m-%d")
    data = svc.client.trade_history(min_date, page=page, page_size=max(1, min(page_size, 500)))
    return {"minDate": min_date, "page": page, "data": data}


# ======================================================================
# Reglas y propuestas
# ======================================================================

@mcp.tool(annotations=READ_LOCAL, description="Devuelve las reglas de riesgo vigentes (config/risk.json), el universo permitido y el calendario macro. Léelo antes de proponer.")
def risk_rules() -> dict[str, Any]:
    cfg = load_risk_config()
    uni = load_universe()
    events = load_macro_calendar()
    return {
        "risk": cfg.to_dict(),
        "universe": {"etfs": uni.etfs, "large_caps": uni.large_caps, "crypto": uni.crypto},
        "macroCalendar": [e.__dict__ for e in events],
        "activeBlackouts": [e.__dict__ for e in active_blackouts(utcnow(), events, cfg.event_blackout_hours_before, cfg.event_blackout_hours_after)],
    }


@mcp.tool(
    annotations=LOCAL_WRITE,
    description=(
        "Genera una PROPUESTA de operación y la pasa por todas las reglas de riesgo (sin ejecutar nada). "
        "Calcula el tamaño para que la pérdida en el stop sea el % de riesgo configurado. "
        "Devuelve un id P-xxxx que el usuario debe confirmar. entry=None usa el precio de mercado actual (ask para compra, bid para venta). "
        "order_type='limit' requiere entry como precio límite. event_dates: fechas ISO de earnings u otros eventos del activo. "
        "thesis_is_the_event=true solo si operar el evento ES la tesis (queda registrado como aviso)."
    ),
)
def propose_trade(
    symbol: str,
    is_buy: bool,
    stop: float,
    thesis: str,
    take_profit: float | None = None,
    entry: float | None = None,
    order_type: str = "market",
    risk_pct: float | None = None,
    event_dates: list[str] | None = None,
    thesis_is_the_event: bool = False,
) -> dict[str, Any]:
    if order_type not in ("market", "limit"):
        raise ValueError("order_type debe ser 'market' o 'limit'")
    if order_type == "limit" and entry is None:
        raise ValueError("una orden límite necesita entry (precio límite)")
    if len(thesis.strip()) < 20:
        raise ValueError("La tesis debe explicar la operación (mínimo 20 caracteres): setup, catalizador, invalidación")

    cfg = load_risk_config()
    uni = load_universe()
    meta = svc.resolve_symbol(symbol)
    iid = int(meta["instrumentId"])
    quote = svc.quote(iid)
    market_entry = float(quote["ask"] if is_buy else quote["bid"]) if quote.get("ask") and quote.get("bid") else float(quote.get("last") or 0)
    entry_px = float(entry) if entry is not None else market_entry

    state, summary, extra = svc.account_state()
    verdict = evaluate(
        cfg,
        uni,
        state,
        symbol=meta.get("symbol") or symbol,
        is_buy=is_buy,
        entry=entry_px,
        stop=stop,
        take_profit=take_profit,
        leverage=1,
        risk_pct=risk_pct,
        macro_events=load_macro_calendar(),
        extra_event_dates=event_dates or [],
        thesis_is_the_event=thesis_is_the_event,
    )
    result: dict[str, Any] = {
        "mode": svc.creds.mode,
        "symbol": meta.get("symbol") or symbol.upper(),
        "instrumentId": iid,
        "isBuy": is_buy,
        "orderType": order_type,
        "entry": entry_px,
        "marketNow": {"bid": quote.get("bid"), "ask": quote.get("ask"), "spreadPct": quote.get("spreadPct")},
        "stop": stop,
        "takeProfit": take_profit,
        "riskCheck": {"ok": verdict.ok, "violations": verdict.violations, "warnings": verdict.warnings},
        "sizing": verdict.sizing.__dict__ if verdict.sizing else None,
        "account": {"creditAvailableUsd": state.available_credit, "openPositions": state.open_positions, "lossCaps": loss_caps_status(cfg, state)},
    }
    if not verdict.ok:
        result["proposalId"] = None
        result["next"] = "RECHAZADA por las reglas. No hay nada que confirmar; ajusta la propuesta o descártala."
        svc.journal.append("proposal", f"Propuesta RECHAZADA {result['symbol']} {'BUY' if is_buy else 'SELL'} @ {entry_px}: {'; '.join(verdict.violations)}", {"thesis": thesis, **result}, mode=svc.creds.mode)
        return result

    assert verdict.sizing is not None
    p = svc.proposals.create(
        cfg.proposal_ttl_minutes,
        mode=svc.creds.mode,
        symbol=result["symbol"],
        instrument_id=iid,
        is_buy=is_buy,
        entry=entry_px,
        stop=float(stop),
        take_profit=None if take_profit is None else float(take_profit),
        amount_usd=verdict.sizing.amount_usd,
        units=verdict.sizing.units,
        risk_usd=verdict.sizing.risk_usd,
        reward_to_risk=verdict.sizing.reward_to_risk,
        thesis=thesis,
        order_type=order_type,
        warnings=verdict.warnings,
    )
    result["proposalId"] = p.id
    result["expiresAt"] = p.expires_at
    result["next"] = f"Presenta la propuesta al usuario y espera literalmente 'CONFIRMO {p.id}'. Después llama execute_proposal('{p.id}', confirm=true)."
    svc.journal.append("proposal", f"Propuesta {p.id}: {p.symbol} {'BUY' if is_buy else 'SELL'} {p.amount_usd} USD @ {p.entry} SL {p.stop} TP {p.take_profit} (riesgo {p.risk_usd} USD)", {"thesis": thesis, **result}, mode=svc.creds.mode)
    return result


@mcp.tool(annotations=READ_LOCAL, description="Lista propuestas guardadas (pending, executed, rejected, expired, cancelled).")
def list_proposals(status: str | None = None, limit: int = 20) -> dict[str, Any]:
    return {"proposals": [p.to_dict() for p in svc.proposals.list(status=status, limit=limit)]}


@mcp.tool(annotations=LOCAL_WRITE, description="Descarta una propuesta pendiente (el usuario dijo no).")
def reject_proposal(proposal_id: str, reason: str = "") -> dict[str, Any]:
    p = svc.proposals.get(proposal_id)
    if p is None:
        raise ValueError(f"Propuesta {proposal_id} no existe")
    p.status = "rejected"
    svc.proposals.save(p)
    svc.journal.append("approval", f"Propuesta {p.id} RECHAZADA por el usuario. {reason}".strip(), {"proposalId": p.id}, mode=p.mode)
    return {"proposalId": p.id, "status": p.status}


# ======================================================================
# Ejecución (requiere confirm=true y propuesta aprobada)
# ======================================================================

@mcp.tool(
    annotations=WRITE,
    description=(
        "EJECUTA una propuesta ya confirmada por el usuario. Requiere confirm=true, que la propuesta esté pendiente y no expirada, "
        "que el precio no se haya movido más del deslizamiento permitido y que las reglas sigan cumpliéndose con el estado actual de la cuenta. "
        "Envía la orden a eToro con stop-loss (y take-profit si lo hay), leverage 1, y registra todo en la bitácora. "
        "Solo llamar tras leer literalmente 'CONFIRMO <id>' del usuario."
    ),
)
def execute_proposal(proposal_id: str, confirm: bool = False) -> dict[str, Any]:
    cfg = load_risk_config()
    refusal = _write_gate(cfg, confirm)
    if refusal:
        return {"executed": False, "reason": refusal}
    p = svc.proposals.get(proposal_id)
    if p is None:
        return {"executed": False, "reason": f"Propuesta {proposal_id} no existe"}
    if p.status != "pending":
        return {"executed": False, "reason": f"Propuesta {p.id} en estado {p.status}, no ejecutable"}
    if p.is_expired():
        p.status = "expired"
        svc.proposals.save(p)
        return {"executed": False, "reason": f"Propuesta {p.id} expirada ({p.expires_at}). Genera una nueva con precios actuales"}
    if p.mode != svc.creds.mode:
        return {"executed": False, "reason": f"Propuesta creada en modo {p.mode} y el servidor corre en {svc.creds.mode}"}

    # Re-validate against live state
    quote = svc.quote(p.instrument_id)
    px_now = float(quote["ask"] if p.is_buy else quote["bid"]) if quote.get("ask") and quote.get("bid") else float(quote.get("last") or p.entry)
    if p.order_type == "market":
        slip = abs(px_now - p.entry) / p.entry * 100
        if slip > cfg.max_entry_slippage_pct:
            return {"executed": False, "reason": f"El precio se movió {slip:.2f}% desde la propuesta ({p.entry} -> {px_now}); supera {cfg.max_entry_slippage_pct}%. Vuelve a proponer"}
        adverse = (p.is_buy and px_now >= p.stop) or ((not p.is_buy) and px_now <= p.stop)
        if not adverse:
            return {"executed": False, "reason": f"El precio actual {px_now} ya cruzó el stop {p.stop}. Propuesta inválida"}

    state, _summary, _extra = svc.account_state()
    verdict = evaluate(
        cfg, load_universe(), state,
        symbol=p.symbol, is_buy=p.is_buy, entry=p.entry, stop=p.stop, take_profit=p.take_profit,
        leverage=1, risk_pct=None, macro_events=load_macro_calendar(),
    )
    if not verdict.ok:
        p.status = "rejected"
        p.warnings = verdict.violations
        svc.proposals.save(p)
        svc.journal.append("error", f"Propuesta {p.id} bloqueada al ejecutar: {'; '.join(verdict.violations)}", {"proposalId": p.id}, mode=p.mode)
        return {"executed": False, "reason": "Las reglas ya no se cumplen: " + "; ".join(verdict.violations)}

    svc.journal.append("approval", f"Usuario confirmó {p.id}", {"proposalId": p.id}, mode=p.mode)
    try:
        if p.order_type == "limit":
            resp = svc.client.place_limit_order(p.instrument_id, p.amount_usd, p.is_buy, p.entry, p.stop, p.take_profit, leverage=1)
        else:
            resp = svc.client.open_market_by_amount(p.instrument_id, p.amount_usd, p.is_buy, p.stop, p.take_profit, leverage=1)
    except EtoroApiError as exc:
        svc.journal.append("error", f"Fallo al ejecutar {p.id}: {exc}", {"proposalId": p.id, "body": exc.body, "requestId": svc.client.last_request_id}, mode=p.mode)
        return {"executed": False, "reason": str(exc), "apiBody": exc.body, "requestId": svc.client.last_request_id}

    p.status = "executed"
    p.execution = {"at": utcnow().isoformat(timespec="seconds"), "priceAtSend": px_now, "response": resp, "requestId": svc.client.last_request_id}
    svc.proposals.save(p)
    svc.journal.append(
        "execution",
        f"EJECUTADA {p.id}: {p.symbol} {'BUY' if p.is_buy else 'SELL'} {p.amount_usd} USD ({p.order_type}) @ ~{px_now} SL {p.stop} TP {p.take_profit}",
        p.to_dict(),
        mode=p.mode,
    )
    return {"executed": True, "proposal": p.to_dict(), "apiResponse": resp}


@mcp.tool(annotations=WRITE, description="Cierra una posición abierta (total, o parcial con units). Requiere confirm=true tras el OK explícito del usuario. reason queda en la bitácora.")
def close_position(position_id: int, reason: str, confirm: bool = False, units: float | None = None) -> dict[str, Any]:
    cfg = load_risk_config()
    refusal = _write_gate(cfg, confirm)
    if refusal:
        return {"closed": False, "reason": refusal}
    summary = summarize_portfolio(svc.client.portfolio_with_pnl())
    pos = next((p for p in summary["positions"] if p.get("positionId") is not None and int(p["positionId"]) == int(position_id)), None)
    if pos is None:
        return {"closed": False, "reason": f"Posición {position_id} no está en el portafolio ({svc.creds.mode})"}
    try:
        resp = svc.client.close_position(int(position_id), int(pos["instrumentId"]), units)
    except EtoroApiError as exc:
        svc.journal.append("error", f"Fallo al cerrar posición {position_id}: {exc}", {"body": exc.body}, mode=svc.creds.mode)
        return {"closed": False, "reason": str(exc), "apiBody": exc.body}
    svc.journal.append("close", f"CIERRE posición {position_id} (instrumento {pos['instrumentId']}) {'parcial ' + str(units) + ' uds' if units else 'total'}: {reason}", {"position": pos, "response": resp}, mode=svc.creds.mode)
    return {"closed": True, "position": pos, "apiResponse": resp}


@mcp.tool(annotations=WRITE, description="Cancela una orden pendiente (límite). Requiere confirm=true tras el OK del usuario.")
def cancel_order(order_id: int, reason: str, confirm: bool = False) -> dict[str, Any]:
    cfg = load_risk_config()
    refusal = _write_gate(cfg, confirm)
    if refusal:
        return {"cancelled": False, "reason": refusal}
    try:
        resp = svc.client.cancel_order(int(order_id))
    except EtoroApiError as exc:
        return {"cancelled": False, "reason": str(exc), "apiBody": exc.body}
    svc.journal.append("cancel", f"CANCELADA orden {order_id}: {reason}", {"response": resp}, mode=svc.creds.mode)
    return {"cancelled": True, "apiResponse": resp}


# ======================================================================
# Pausa, bitácora y benchmark (local)
# ======================================================================

@mcp.tool(annotations=LOCAL_WRITE, description="Activa o quita la pausa global de trading (interruptor de emergencia). Con paused=true ninguna propuesta pasa el chequeo. Se guarda en config/risk.json.")
def set_trading_pause(paused: bool, reason: str) -> dict[str, Any]:
    cfg = load_risk_config()
    cfg.trading_paused = paused
    cfg.trading_paused_reason = reason if paused else ""
    save_risk_config(cfg)
    svc.journal.append("pause", ("PAUSA activada: " if paused else "Pausa levantada: ") + reason, {"paused": paused}, mode=svc.creds.mode)
    return {"trading_paused": cfg.trading_paused, "reason": cfg.trading_paused_reason}


@mcp.tool(annotations=LOCAL_WRITE, description=f"Añade una entrada a la bitácora. event_type: {', '.join(EVENT_TYPES)}. Úsalo para el check-in diario, notas y la revisión semanal.")
def journal_log(event_type: str, text: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return svc.journal.append(event_type, text, data, mode=svc.creds.mode)


@mcp.tool(annotations=READ_LOCAL, description="Últimas entradas de la bitácora (opcionalmente filtradas por event_type).")
def journal_recent(limit: int = 20, event_type: str | None = None) -> dict[str, Any]:
    return {"entries": svc.journal.recent(limit=limit, event_type=event_type)}


@mcp.tool(annotations=LOCAL_WRITE, description="Fija el punto de partida del benchmark: equity actual de la cuenta y precio del ETF de referencia (por defecto SPY). Llamar una vez al empezar la fase Demo.")
def benchmark_start(symbol: str = "SPY", force: bool = False) -> dict[str, Any]:
    existing = svc.journal.read_benchmark()
    if existing and not force:
        return {"alreadyStarted": True, "benchmark": existing, "hint": "usa force=true para reiniciarlo"}
    meta = svc.resolve_symbol(symbol)
    q = svc.quote(int(meta["instrumentId"]))
    summary = summarize_portfolio(svc.client.portfolio_with_pnl())
    data = {
        "startedAt": utcnow().isoformat(timespec="seconds"),
        "mode": svc.creds.mode,
        "symbol": meta.get("symbol") or symbol.upper(),
        "instrumentId": int(meta["instrumentId"]),
        "benchmarkStartPrice": float(q["ask"] if q.get("ask") else q.get("last")),
        "accountStartEquityUsd": summary["equityEstimateUsd"],
    }
    svc.journal.write_benchmark(data)
    svc.journal.append("note", f"Benchmark iniciado: equity {data['accountStartEquityUsd']} USD vs {data['symbol']} @ {data['benchmarkStartPrice']}", data, mode=svc.creds.mode)
    return {"alreadyStarted": False, "benchmark": data}


@mcp.tool(annotations=READ, description="Compara el rendimiento de la cuenta desde benchmark_start con haber comprado y mantenido el ETF de referencia.")
def benchmark_status() -> dict[str, Any]:
    b = svc.journal.read_benchmark()
    if not b:
        return {"error": "No hay benchmark. Llama benchmark_start() primero"}
    q = svc.quote(int(b["instrumentId"]))
    px = float(q["bid"] if q.get("bid") else q.get("last"))
    summary = summarize_portfolio(svc.client.portfolio_with_pnl())
    eq = summary["equityEstimateUsd"]
    start_eq = float(b["accountStartEquityUsd"]) or 1.0
    bench_ret = (px / float(b["benchmarkStartPrice"]) - 1) * 100
    acct_ret = (eq / start_eq - 1) * 100
    return {
        "since": b["startedAt"],
        "account": {"startEquityUsd": start_eq, "nowEquityUsd": eq, "returnPct": round(acct_ret, 2)},
        "benchmark": {"symbol": b["symbol"], "startPrice": b["benchmarkStartPrice"], "nowPrice": px, "returnPct": round(bench_ret, 2)},
        "differencePct": round(acct_ret - bench_ret, 2),
    }


def main() -> None:
    creds = load_credentials()
    log.info("etoro-mcp %s · modo=%s · real armado=%s", __version__, creds.mode, (not creds.is_demo) and creds.allow_real_trading)
    if creds.missing():
        log.warning("Faltan variables de entorno: %s", ", ".join(creds.missing()))
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
