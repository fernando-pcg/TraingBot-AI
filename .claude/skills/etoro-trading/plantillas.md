# Plantillas de bitácora

## Check-in diario (`journal_log("checkin", texto, data)`)

```
Cuenta (DEMO): crédito 120.00 · invertido directo 80.00 · en copia 0 · flotante -1.20
Topes: día -0.00/6.00 · semana -3.50/10.00 · posiciones 1/5 · aperturas hoy 0/2
Ventanas activas: ninguna · Próximo evento: CPI 2026-10-14 12:30 UTC
Posiciones: SPY long 80 USD @500.10, stop 490, TP 520, P&L -1.20 (-1.5 %), tesis vigente
Propuestas hoy: P-… SPY (ejecutada) · P-… BTC (rechazada por usuario: spread alto)
Noticias relevantes: …
Lección del día: …
```

`data` sugerido: `{"credit": 120.0, "positions": 1, "weekly_loss": 3.5, "proposals": ["P-…"]}`

## Ejecución (la escribe el MCP automáticamente)

Incluye propuesta completa, precio al enviar, respuesta de la API y `requestId`. No hace falta duplicarla.

## Cierre manual (`close_position`)

`reason` debe decir qué cambió: "tesis invalidada: cierre bajo soporte 495 con volumen", "stop a break-even alcanzado, cierro mitad", "evento imprevisto: …". Nunca "por si acaso".

## Revisión semanal (`journal_log("review", texto, data)`)

```
Semana 2026-09-14 → 2026-09-18 (DEMO)
Operaciones: 4 (2 ganadoras, 2 perdedoras) · P&L neto +2.10 USD (+1.05 %) · comisiones est. 0.60
Mejor: … · Peor: … · Regla que lo habría evitado: …
Disciplina: propuestas 6, confirmadas 4, rechazadas 2, ejecutadas fuera de regla 0
Benchmark: cuenta +1.05 % vs SPY +0.80 % (diferencia +0.25 %)
Calendario próxima semana: FOMC no · CPI no · earnings del universo: …
Decisión: seguir en Demo / pasar a Real / parar. Motivo: …
```
