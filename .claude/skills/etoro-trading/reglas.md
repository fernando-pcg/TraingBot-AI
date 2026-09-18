# Reglas de riesgo: detalle y justificación

Todas viven en `config/risk.json` y las aplica `etoro_mcp/risk.py`. Los tests en `tests/test_risk.py` son la especificación ejecutable.

| Regla | Valor | Por qué |
|---|---|---|
| Capital de referencia | 200 USD | Base para todos los porcentajes. Ajústala si depositas o retiras. |
| Apalancamiento | 1x, sin excepción | Sin overnight fees de CFD, sin margin call, pérdida máxima = tamaño. |
| Universo | ETFs de índices, large caps, BTC/ETH | Liquidez y spread bajo. Nada de small caps, memes ni pares exóticos. |
| Riesgo por operación | 2 % (máx. duro 3 %) | 4-6 USD. Diez pérdidas seguidas = -20 %, recuperable. |
| Stop-loss | Obligatorio, entre 0.3 % y 10 % de la entrada | <0.3 % lo barre el spread; >10 % no es una operación de corto plazo. |
| Take profit | Ratio ≥ 1.5 | Con win-rate 45 % y ratio 1.5 la esperanza es positiva antes de costes. |
| Tamaño máximo | 40 % del capital | Diversifica entre al menos 3 posiciones. |
| Mínimo por posición | 10 USD | Mínimo habitual de eToro; verifica por activo. |
| Posiciones abiertas | ≤ 5 | Con 200 USD no caben más sin trocear demasiado. |
| Aperturas por día | ≤ 2 | Frena el sobreoperar, la mayor fuga de dinero en cuentas pequeñas. |
| Pérdida diaria | 3 % realizada | Corta la mala racha del día. |
| Pérdida semanal | 5 % realizada | Pausa total hasta el lunes. Se activa `trading_paused`. |
| Eventos macro | 2 h antes / 1 h después de FOMC, CPI | Spreads y whipsaws. Calendario en `config/macro_calendar.json`. |
| Eventos del activo | 24 h antes de earnings | Una posición abierta hoy atraviesa el evento. |
| Vida de una propuesta | 30 min | Los precios cambian; se repropone. |
| Deslizamiento máximo | 0.5 % | Si el precio se movió más, la propuesta ya no es la misma. |

## Cálculo del tamaño

```
riesgo_usd     = capital × riesgo_pct / 100          # 200 × 2 % = 4 USD
distancia_stop = |entrada − stop| / entrada          # 2 % → 0.02
tamaño_usd     = riesgo_usd / distancia_stop         # 4 / 0.02 = 200 → capado a 80 (40 %)
```

El tamaño después se limita por el 40 % del capital y por el crédito realmente disponible. Si queda por debajo de 10 USD, la operación no cabe.

## Agent Portfolio

Las keys controlan el Agent Portfolio (sub-cuenta independiente). Su crédito es el capital operable y es lo que devuelve `etoro_status.portfolio.creditAvailableUsd`. `capital_usd` en `config/risk.json` debe coincidir con la asignación hecha en la app (200 USD). Si el portafolio mostrara mirrors (`copyInvestedUsd > 0`), ese dinero no está disponible para operar directo.

## Costes que hay que mirar antes de cada propuesta

- Spread: eToro lo muestra como diferencia bid/ask; `etoro_quote` devuelve `spreadPct`. Si el spread supera el 20 % de la distancia al stop, el trade está mal planteado.
- Crypto: comisión ~1 % por lado. Con 4 USD de riesgo, 0.8 USD de comisiones es el 20 %. Solo operar BTC/ETH con stops amplios y horizonte de días.
- Acciones y ETFs sin apalancamiento: sin comisión de apertura en la mayoría de regiones, pero conversión de divisa si la cuenta no es USD.
