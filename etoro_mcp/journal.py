"""Bitácora (trading journal) and proposal store.

* ``journal/YYYY-MM.jsonl``   machine-readable, one event per line
* ``journal/bitacora.md``     human-readable, appended chronologically
* ``journal/proposals/*.json`` trade proposals awaiting / after approval
* ``journal/benchmark.json``  start point for the "vs S&P 500 ETF" comparison
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import journal_dir
from .risk import utcnow

EVENT_TYPES = (
    "checkin",       # revisión diaria
    "proposal",      # propuesta generada
    "approval",      # OK del usuario
    "execution",     # orden enviada + respuesta
    "close",         # cierre de posición
    "cancel",        # cancelación de orden
    "pause",         # pausa / reanudación
    "note",          # observación libre
    "review",        # revisión semanal
    "error",
)


class Journal:
    def __init__(self, root: Path | None = None):
        self.root = root or journal_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "proposals").mkdir(parents=True, exist_ok=True)

    # ---- events ----------------------------------------------------------
    def append(self, event_type: str, text: str, data: dict[str, Any] | None = None, *, mode: str = "demo") -> dict:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"event_type debe ser uno de {EVENT_TYPES}")
        now = utcnow()
        entry = {
            "ts": now.isoformat(timespec="seconds"),
            "mode": mode,
            "type": event_type,
            "text": text,
            "data": data or {},
        }
        jsonl = self.root / f"{now:%Y-%m}.jsonl"
        with jsonl.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        md = self.root / "bitacora.md"
        if not md.exists():
            md.write_text("# Bitácora de trading\n\n", encoding="utf-8")
        with md.open("a", encoding="utf-8") as fh:
            fh.write(f"## {entry['ts']} · {mode.upper()} · {event_type}\n\n{text.strip()}\n\n")
            if data:
                fh.write("```json\n" + json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n```\n\n")
        return entry

    def recent(self, limit: int = 20, event_type: str | None = None) -> list[dict]:
        files = sorted(self.root.glob("*.jsonl"), reverse=True)
        out: list[dict] = []
        for f in files:
            lines = f.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event_type and e.get("type") != event_type:
                    continue
                out.append(e)
                if len(out) >= limit:
                    return out
        return out

    # ---- benchmark -------------------------------------------------------
    def benchmark_path(self) -> Path:
        return self.root / "benchmark.json"

    def read_benchmark(self) -> dict | None:
        p = self.benchmark_path()
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def write_benchmark(self, data: dict) -> None:
        self.benchmark_path().write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@dataclass
class Proposal:
    id: str
    created_at: str
    expires_at: str
    mode: str
    symbol: str
    instrument_id: int
    is_buy: bool
    entry: float
    stop: float
    take_profit: float | None
    amount_usd: float
    units: float
    risk_usd: float
    reward_to_risk: float | None
    thesis: str
    order_type: str = "market"  # market | limit
    status: str = "pending"      # pending | executed | rejected | expired | cancelled
    warnings: list[str] = field(default_factory=list)
    execution: dict[str, Any] | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        now = now or utcnow()
        return now > datetime.fromisoformat(self.expires_at)

    def to_dict(self) -> dict:
        return asdict(self)


class ProposalStore:
    def __init__(self, root: Path | None = None):
        self.root = (root or journal_dir()) / "proposals"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_id(now: datetime | None = None) -> str:
        now = now or utcnow()
        return f"P-{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2).upper()}"

    def create(self, ttl_minutes: int, **fields: Any) -> Proposal:
        now = utcnow()
        p = Proposal(
            id=self.new_id(now),
            created_at=now.isoformat(timespec="seconds"),
            expires_at=(now + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds"),
            **fields,
        )
        self.save(p)
        return p

    def path(self, proposal_id: str) -> Path:
        safe = "".join(c for c in proposal_id if c.isalnum() or c in "-_")
        return self.root / f"{safe}.json"

    def save(self, p: Proposal) -> None:
        self.path(p.id).write_text(json.dumps(p.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def get(self, proposal_id: str) -> Proposal | None:
        path = self.path(proposal_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Proposal(**data)

    def list(self, status: str | None = None, limit: int = 20) -> list[Proposal]:
        items = []
        for f in sorted(self.root.glob("P-*.json"), reverse=True):
            try:
                p = Proposal(**json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError):
                continue
            if p.status == "pending" and p.is_expired():
                p.status = "expired"
                self.save(p)
            if status and p.status != status:
                continue
            items.append(p)
            if len(items) >= limit:
                break
        return items
