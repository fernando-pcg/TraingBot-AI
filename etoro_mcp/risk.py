"""Pure risk logic: position sizing and rule evaluation.

Nothing here talks to the network. Every rule the skill promises is enforced in
``evaluate`` so that a proposal can only be executed after passing it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .config import MacroEvent, RiskConfig, Universe


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def week_start(now: datetime) -> datetime:
    """Monday 00:00 UTC of the week containing ``now``."""
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass
class Sizing:
    risk_usd: float
    stop_distance_pct: float
    amount_usd: float
    units: float
    reward_to_risk: float | None
    capped_by: list[str] = field(default_factory=list)


def compute_sizing(
    cfg: RiskConfig,
    entry: float,
    stop: float,
    take_profit: float | None,
    is_buy: bool,
    risk_pct: float | None,
    available_credit: float,
) -> Sizing:
    """Size a position so the loss at the stop equals ``risk_pct`` of capital.

    amount = risk_usd / stop_distance, then capped by max position size and by the
    credit actually available in the account.
    """
    if entry <= 0 or stop <= 0:
        raise ValueError("entry y stop deben ser > 0")
    if is_buy and stop >= entry:
        raise ValueError("en una compra el stop debe estar por debajo de la entrada")
    if not is_buy and stop <= entry:
        raise ValueError("en una venta el stop debe estar por encima de la entrada")
    if take_profit is not None:
        if is_buy and take_profit <= entry:
            raise ValueError("en una compra el take profit debe estar por encima de la entrada")
        if not is_buy and take_profit >= entry:
            raise ValueError("en una venta el take profit debe estar por debajo de la entrada")

    risk_pct = cfg.max_risk_per_trade_pct if risk_pct is None else risk_pct
    risk_usd = cfg.capital_usd * risk_pct / 100.0
    stop_distance = abs(entry - stop) / entry
    stop_distance_pct = stop_distance * 100.0

    amount = risk_usd / stop_distance
    capped: list[str] = []

    max_pos = cfg.capital_usd * cfg.max_position_pct_of_capital / 100.0
    if amount > max_pos:
        amount = max_pos
        capped.append("max_position_pct_of_capital")
    if amount > available_credit:
        amount = available_credit
        capped.append("available_credit")

    amount = round(amount, 2)
    units = amount / entry if entry else 0.0
    rr = None
    if take_profit is not None:
        rr = abs(take_profit - entry) / abs(entry - stop)
    return Sizing(
        risk_usd=round(risk_usd, 2),
        stop_distance_pct=round(stop_distance_pct, 3),
        amount_usd=amount,
        units=round(units, 6),
        reward_to_risk=None if rr is None else round(rr, 2),
        capped_by=capped,
    )


@dataclass
class AccountState:
    """Snapshot of the account used by the rule engine."""

    available_credit: float
    open_positions: int
    open_symbols: set[str] = field(default_factory=set)
    realized_pnl_today: float = 0.0
    realized_pnl_week: float = 0.0
    unrealized_pnl: float = 0.0
    trades_opened_today: int = 0
    copy_invested_usd: float = 0.0


@dataclass
class Verdict:
    ok: bool
    violations: list[str]
    warnings: list[str]
    sizing: Sizing | None


def active_blackouts(
    now: datetime,
    events: Iterable[MacroEvent],
    hours_before: float,
    hours_after: float,
) -> list[MacroEvent]:
    out = []
    for ev in events:
        t = parse_iso(ev.datetime_utc)
        if t - timedelta(hours=hours_before) <= now <= t + timedelta(hours=hours_after):
            out.append(ev)
    return out


def loss_caps_status(cfg: RiskConfig, state: AccountState) -> dict:
    daily_cap = cfg.capital_usd * cfg.daily_loss_cap_pct / 100.0
    weekly_cap = cfg.capital_usd * cfg.weekly_loss_cap_pct / 100.0
    daily_loss = max(0.0, -state.realized_pnl_today)
    weekly_loss = max(0.0, -state.realized_pnl_week)
    return {
        "daily_loss_usd": round(daily_loss, 2),
        "daily_cap_usd": round(daily_cap, 2),
        "daily_cap_hit": daily_loss >= daily_cap,
        "weekly_loss_usd": round(weekly_loss, 2),
        "weekly_cap_usd": round(weekly_cap, 2),
        "weekly_cap_hit": weekly_loss >= weekly_cap,
        "weekly_loss_including_unrealized_usd": round(
            max(0.0, -(state.realized_pnl_week + min(0.0, state.unrealized_pnl))), 2
        ),
    }


def evaluate(
    cfg: RiskConfig,
    universe: Universe,
    state: AccountState,
    *,
    symbol: str,
    is_buy: bool,
    entry: float,
    stop: float | None,
    take_profit: float | None,
    leverage: int,
    risk_pct: float | None,
    macro_events: Iterable[MacroEvent] = (),
    extra_event_dates: Iterable[str] = (),
    thesis_is_the_event: bool = False,
    now: datetime | None = None,
) -> Verdict:
    now = now or utcnow()
    violations: list[str] = []
    warnings: list[str] = []
    sym = symbol.upper()

    if cfg.trading_paused:
        violations.append(f"Trading en PAUSA: {cfg.trading_paused_reason or 'sin motivo registrado'}")

    if leverage != 1:
        violations.append(f"Apalancamiento {leverage}x no permitido (máximo {cfg.max_leverage}x)")

    if sym not in universe.symbols:
        violations.append(f"{sym} no está en el universo permitido (config/universe.json)")

    if stop is None:
        violations.append("Stop-loss obligatorio: la propuesta no tiene stop")

    if risk_pct is not None and risk_pct > cfg.hard_max_risk_per_trade_pct:
        violations.append(
            f"Riesgo {risk_pct}% supera el máximo duro {cfg.hard_max_risk_per_trade_pct}% por operación"
        )

    caps = loss_caps_status(cfg, state)
    if caps["weekly_cap_hit"]:
        violations.append(
            f"Tope de pérdida semanal alcanzado ({caps['weekly_loss_usd']} USD >= {caps['weekly_cap_usd']} USD): todo en pausa hasta el lunes"
        )
    if caps["daily_cap_hit"]:
        violations.append(
            f"Tope de pérdida diaria alcanzado ({caps['daily_loss_usd']} USD >= {caps['daily_cap_usd']} USD): no se abre nada más hoy"
        )
    if caps["weekly_loss_including_unrealized_usd"] >= caps["weekly_cap_usd"] and not caps["weekly_cap_hit"]:
        warnings.append(
            "Contando el flotante negativo ya se supera el tope semanal; revisar antes de añadir riesgo"
        )

    if state.open_positions >= cfg.max_open_positions:
        violations.append(f"Ya hay {state.open_positions} posiciones abiertas (máximo {cfg.max_open_positions})")

    if sym in {s.upper() for s in state.open_symbols}:
        violations.append(f"Ya existe una posición abierta en {sym}: no se piramida")

    if state.trades_opened_today >= cfg.max_trades_per_day:
        violations.append(f"Ya se abrieron {state.trades_opened_today} operaciones hoy (máximo {cfg.max_trades_per_day})")

    blackout = active_blackouts(now, macro_events, cfg.event_blackout_hours_before, cfg.event_blackout_hours_after)
    extra = [MacroEvent(name="Evento del activo (earnings u otro)", datetime_utc=d) for d in extra_event_dates]
    # Earnings u otros eventos del propio activo: una posición abierta hoy los atraviesa,
    # así que la ventana previa es más ancha (por defecto 24 h).
    blackout += active_blackouts(now, extra, cfg.asset_event_blackout_hours_before, cfg.event_blackout_hours_after)
    if blackout:
        names = ", ".join(f"{e.name} @ {e.datetime_utc}" for e in blackout)
        if thesis_is_the_event:
            warnings.append(f"Operando dentro de ventana de evento por tesis explícita: {names}")
        else:
            violations.append(f"Ventana de evento activa, no se abren operaciones: {names}")

    sizing: Sizing | None = None
    if stop is not None:
        try:
            sizing = compute_sizing(cfg, entry, stop, take_profit, is_buy, risk_pct, state.available_credit)
        except ValueError as exc:
            violations.append(str(exc))

    if sizing is not None:
        if sizing.stop_distance_pct < cfg.min_stop_distance_pct:
            violations.append(
                f"Stop demasiado cerca ({sizing.stop_distance_pct}% < {cfg.min_stop_distance_pct}%): lo barre el spread"
            )
        if sizing.stop_distance_pct > cfg.max_stop_distance_pct:
            violations.append(
                f"Stop demasiado lejos ({sizing.stop_distance_pct}% > {cfg.max_stop_distance_pct}%): no es una operación de corto plazo"
            )
        if sizing.amount_usd < cfg.min_position_usd:
            violations.append(
                f"Tamaño {sizing.amount_usd} USD por debajo del mínimo {cfg.min_position_usd} USD "
                f"(crédito disponible {state.available_credit:.2f} USD). Con el stop propuesto no cabe la operación."
            )
        if take_profit is None:
            warnings.append("Sin take profit: define un objetivo o un plan de salida explícito en la bitácora")
        elif sizing.reward_to_risk is not None and sizing.reward_to_risk < cfg.min_reward_to_risk:
            violations.append(
                f"Ratio beneficio/riesgo {sizing.reward_to_risk} < mínimo {cfg.min_reward_to_risk}"
            )
        if "available_credit" in sizing.capped_by:
            warnings.append(
                f"Tamaño limitado por el crédito disponible ({state.available_credit:.2f} USD); "
                f"el riesgo real en el stop será menor que {sizing.risk_usd} USD"
            )
        if state.copy_invested_usd > 0:
            warnings.append(
                f"Hay {state.copy_invested_usd:.2f} USD en copias (mirrors). Ese capital no está disponible para operar directo "
                "y su riesgo lo controla el copiado, no esta skill"
            )

    return Verdict(ok=not violations, violations=violations, warnings=warnings, sizing=sizing)


def realized_pnl_since(trades: Iterable[dict], since: datetime) -> tuple[float, int]:
    """Sum realized P&L of closed trades at/after ``since``. Returns (pnl, count).

    Tolerant to the field names eToro uses (``closeDateTime``/``CloseDateTime``,
    ``netProfit``/``NetProfit``/``profit``).
    """
    total = 0.0
    count = 0
    for t in trades:
        close_ts = t.get("closeDateTime") or t.get("CloseDateTime") or t.get("closeDate")
        if not close_ts:
            continue
        try:
            closed = parse_iso(str(close_ts))
        except ValueError:
            continue
        if closed < since:
            continue
        pnl = t.get("netProfit", t.get("NetProfit", t.get("profit", t.get("Profit", 0.0))))
        try:
            total += float(pnl or 0.0)
        except (TypeError, ValueError):
            continue
        count += 1
    return round(total, 2), count


def opened_since(positions: Iterable[dict], since: datetime) -> int:
    n = 0
    for p in positions:
        ts = p.get("openDateTime") or p.get("OpenDateTime")
        if not ts:
            continue
        try:
            if parse_iso(str(ts)) >= since:
                n += 1
        except ValueError:
            continue
    return n
