import json
from datetime import datetime, timedelta, timezone

from etoro_mcp.journal import Journal, ProposalStore


def test_journal_append_and_recent(tmp_path):
    j = Journal(tmp_path)
    j.append("checkin", "Revisión diaria", {"credit": 3.09})
    j.append("note", "Nota", mode="real")
    entries = j.recent(limit=5)
    assert [e["type"] for e in entries] == ["note", "checkin"]
    assert entries[1]["data"]["credit"] == 3.09
    md = (tmp_path / "bitacora.md").read_text(encoding="utf-8")
    assert "Revisión diaria" in md and "REAL · note" in md
    assert j.recent(event_type="checkin")[0]["type"] == "checkin"


def test_journal_rejects_unknown_type(tmp_path):
    j = Journal(tmp_path)
    try:
        j.append("yolo", "x")
    except ValueError as exc:
        assert "event_type" in str(exc)
    else:
        raise AssertionError("debería fallar")


def proposal_fields(**kw):
    base = dict(mode="demo", symbol="SPY", instrument_id=1001, is_buy=True, entry=500.0, stop=490.0, take_profit=520.0,
                amount_usd=80.0, units=0.16, risk_usd=4.0, reward_to_risk=2.0, thesis="ruptura de rango con volumen y cierre sobre la media")
    base.update(kw)
    return base


def test_proposal_lifecycle(tmp_path):
    store = ProposalStore(tmp_path)
    p = store.create(30, **proposal_fields())
    assert p.id.startswith("P-") and p.status == "pending" and not p.is_expired()
    loaded = store.get(p.id)
    assert loaded is not None and loaded.symbol == "SPY"
    assert [x.id for x in store.list(status="pending")] == [p.id]
    loaded.status = "executed"
    store.save(loaded)
    assert store.list(status="pending") == []
    assert store.get("P-nope") is None


def test_proposal_expiry(tmp_path):
    store = ProposalStore(tmp_path)
    p = store.create(0, **proposal_fields())
    future = datetime.now(timezone.utc) + timedelta(seconds=1)
    assert p.is_expired(future)
    p.expires_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    store.save(p)
    assert store.list()[0].status == "expired"


def test_proposal_id_path_is_sanitized(tmp_path):
    store = ProposalStore(tmp_path)
    assert store.path("../../etc/passwd").name == "etcpasswd.json"
