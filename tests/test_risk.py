from datetime import datetime, timezone

import pytest

from etoro_mcp.config import MacroEvent, RiskConfig, load_risk_config, load_universe, load_macro_calendar
from etoro_mcp.risk import (
    AccountState,
    active_blackouts,
    compute_sizing,
    evaluate,
    loss_caps_status,
    realized_pnl_since,
    week_start,
)

NOW = datetime(2026, 9, 18, 14, 0, tzinfo=timezone.utc)  # viernes


def state(**kw) -> AccountState:
    base = dict(available_credit=200.0, open_positions=0)
    base.update(kw)
    return AccountState(**base)


def test_repo_config_files_are_valid(repo_config_dir):
    cfg = load_risk_config(repo_config_dir / "risk.json")
    assert cfg.capital_usd == 200
    assert cfg.max_leverage == 1
    uni = load_universe(repo_config_dir / "universe.json")
    assert {"SPY", "BTC", "ETH"} <= uni.symbols
    events = load_macro_calendar(repo_config_dir / "macro_calendar.json")
    assert events and all(e.datetime_utc.endswith("Z") for e in events)


def test_sizing_risk_equals_pct_of_capital(cfg):
    # 2% de 200 = 4 USD; stop al 2% -> 200 USD, pero max_position 40% = 80 USD
    s = compute_sizing(cfg, entry=100, stop=98, take_profit=104, is_buy=True, risk_pct=None, available_credit=500)
    assert s.risk_usd == 4.0
    assert s.stop_distance_pct == 2.0
    assert s.amount_usd == 80.0
    assert "max_position_pct_of_capital" in s.capped_by
    assert s.reward_to_risk == 2.0


def test_sizing_uncapped(cfg):
    # stop al 5% -> 4/0.05 = 80 -> justo el tope, no capado por crédito
    s = compute_sizing(cfg, entry=50, stop=47.5, take_profit=None, is_buy=True, risk_pct=None, available_credit=200)
    assert s.amount_usd == 80.0
    assert s.units == pytest.approx(1.6)


def test_sizing_capped_by_credit(cfg):
    s = compute_sizing(cfg, entry=100, stop=95, take_profit=None, is_buy=True, risk_pct=None, available_credit=3.09)
    assert s.amount_usd == 3.09
    assert "available_credit" in s.capped_by


def test_sizing_rejects_wrong_side(cfg):
    with pytest.raises(ValueError):
        compute_sizing(cfg, entry=100, stop=101, take_profit=None, is_buy=True, risk_pct=None, available_credit=100)
    with pytest.raises(ValueError):
        compute_sizing(cfg, entry=100, stop=99, take_profit=None, is_buy=False, risk_pct=None, available_credit=100)
    with pytest.raises(ValueError):
        compute_sizing(cfg, entry=100, stop=98, take_profit=99, is_buy=True, risk_pct=None, available_credit=100)


def test_happy_path(cfg, universe):
    v = evaluate(cfg, universe, state(), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, now=NOW)
    assert v.ok, v.violations
    assert v.sizing.amount_usd == 80.0
    assert v.warnings == []


def test_stop_mandatory(cfg, universe):
    v = evaluate(cfg, universe, state(), symbol="SPY", is_buy=True, entry=500, stop=None, take_profit=520, leverage=1, risk_pct=None, now=NOW)
    assert not v.ok
    assert any("Stop-loss obligatorio" in x for x in v.violations)


def test_no_leverage(cfg, universe):
    v = evaluate(cfg, universe, state(), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=2, risk_pct=None, now=NOW)
    assert any("Apalancamiento" in x for x in v.violations)


def test_universe_enforced(cfg, universe):
    v = evaluate(cfg, universe, state(), symbol="GME", is_buy=True, entry=20, stop=19, take_profit=23, leverage=1, risk_pct=None, now=NOW)
    assert any("universo" in x for x in v.violations)


def test_hard_max_risk(cfg, universe):
    v = evaluate(cfg, universe, state(), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=4.0, now=NOW)
    assert any("máximo duro" in x for x in v.violations)


def test_weekly_cap_pauses_everything(cfg, universe):
    v = evaluate(cfg, universe, state(realized_pnl_week=-10.0), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, now=NOW)
    assert any("semanal" in x for x in v.violations)


def test_daily_cap(cfg, universe):
    v = evaluate(cfg, universe, state(realized_pnl_today=-6.0), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, now=NOW)
    assert any("diaria" in x for x in v.violations)


def test_unrealized_counts_as_warning(cfg, universe):
    v = evaluate(cfg, universe, state(realized_pnl_week=-6.0, unrealized_pnl=-5.0), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, now=NOW)
    assert v.ok
    assert any("flotante" in w for w in v.warnings)


def test_max_positions_and_no_pyramiding(cfg, universe):
    v = evaluate(cfg, universe, state(open_positions=5), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, now=NOW)
    assert any("posiciones abiertas" in x for x in v.violations)
    v = evaluate(cfg, universe, state(open_positions=1, open_symbols={"spy"}), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, now=NOW)
    assert any("no se piramida" in x for x in v.violations)


def test_max_trades_per_day(cfg, universe):
    v = evaluate(cfg, universe, state(trades_opened_today=2), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, now=NOW)
    assert any("operaciones hoy" in x for x in v.violations)


def test_event_blackout_blocks_unless_thesis(cfg, universe):
    ev = [MacroEvent(name="FOMC", datetime_utc="2026-09-18T15:00:00Z")]
    v = evaluate(cfg, universe, state(), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, macro_events=ev, now=NOW)
    assert any("Ventana de evento" in x for x in v.violations)
    v = evaluate(cfg, universe, state(), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, macro_events=ev, thesis_is_the_event=True, now=NOW)
    assert v.ok and any("tesis explícita" in w for w in v.warnings)
    # earnings del propio activo pasados por parámetro: bloquean si caen en las próximas 24 h
    v = evaluate(cfg, universe, state(), symbol="AAPL", is_buy=True, entry=200, stop=196, take_profit=208, leverage=1, risk_pct=None, extra_event_dates=["2026-09-18T20:30:00Z"], now=NOW)
    assert any("Evento del activo" in x for x in v.violations)
    v = evaluate(cfg, universe, state(), symbol="AAPL", is_buy=True, entry=200, stop=196, take_profit=208, leverage=1, risk_pct=None, extra_event_dates=["2026-09-20T20:30:00Z"], now=NOW)
    assert v.ok
    # fuera de ventana no bloquea
    far = [MacroEvent(name="FOMC", datetime_utc="2026-09-20T18:00:00Z")]
    v = evaluate(cfg, universe, state(), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, macro_events=far, now=NOW)
    assert v.ok


def test_stop_distance_bounds(cfg, universe):
    v = evaluate(cfg, universe, state(), symbol="SPY", is_buy=True, entry=500, stop=499.5, take_profit=501, leverage=1, risk_pct=None, now=NOW)
    assert any("demasiado cerca" in x for x in v.violations)
    v = evaluate(cfg, universe, state(), symbol="BTC", is_buy=True, entry=60000, stop=50000, take_profit=80000, leverage=1, risk_pct=None, now=NOW)
    assert any("demasiado lejos" in x for x in v.violations)


def test_min_position_with_tiny_credit(cfg, universe):
    v = evaluate(cfg, universe, state(available_credit=3.09, copy_invested_usd=200.0), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, now=NOW)
    assert not v.ok
    assert any("por debajo del mínimo" in x for x in v.violations)
    assert any("mirrors" in w for w in v.warnings)


def test_reward_to_risk_minimum(cfg, universe):
    v = evaluate(cfg, universe, state(), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=505, leverage=1, risk_pct=None, now=NOW)
    assert any("beneficio/riesgo" in x for x in v.violations)


def test_paused(universe):
    cfg = RiskConfig(trading_paused=True, trading_paused_reason="semana roja")
    v = evaluate(cfg, universe, state(), symbol="SPY", is_buy=True, entry=500, stop=490, take_profit=520, leverage=1, risk_pct=None, now=NOW)
    assert any("PAUSA" in x for x in v.violations)


def test_config_validation_rejects_leverage():
    with pytest.raises(ValueError):
        RiskConfig.from_dict({"max_leverage": 2})


def test_week_start_and_pnl():
    ws = week_start(NOW)
    assert ws == datetime(2026, 9, 14, tzinfo=timezone.utc)
    trades = [
        {"closeDateTime": "2026-09-15T10:00:00Z", "netProfit": -3.5},
        {"CloseDateTime": "2026-09-17T10:00:00Z", "NetProfit": 1.25},
        {"closeDateTime": "2026-09-10T10:00:00Z", "netProfit": -50},  # semana pasada
        {"closeDateTime": None},
    ]
    pnl, n = realized_pnl_since(trades, ws)
    assert pnl == -2.25 and n == 2


def test_loss_caps_status(cfg):
    st = loss_caps_status(cfg, state(realized_pnl_week=-4.0, realized_pnl_today=-1.0, unrealized_pnl=-7.0))
    assert st["weekly_cap_usd"] == 10.0 and st["daily_cap_usd"] == 6.0
    assert not st["weekly_cap_hit"] and not st["daily_cap_hit"]
    assert st["weekly_loss_including_unrealized_usd"] == 11.0


def test_active_blackouts_window():
    ev = [MacroEvent(name="CPI", datetime_utc="2026-09-18T12:30:00Z")]
    assert active_blackouts(datetime(2026, 9, 18, 10, 31, tzinfo=timezone.utc), ev, 2, 1)
    assert not active_blackouts(datetime(2026, 9, 18, 10, 29, tzinfo=timezone.utc), ev, 2, 1)
    assert active_blackouts(datetime(2026, 9, 18, 13, 29, tzinfo=timezone.utc), ev, 2, 1)
    assert not active_blackouts(datetime(2026, 9, 18, 13, 31, tzinfo=timezone.utc), ev, 2, 1)
