# Checklist diario (versión corta)

```
[ ] 1. etoro_status        modo · keys · pausa · topes · ventanas · crédito (~200) · posiciones
[ ] 2. Portafolio          por posición: P&L, distancia a stop/TP, tesis vigente?
[ ] 3. Coherencia          ¿lo que devuelve la API coincide con el Agent Portfolio en la app?
[ ] 4. Calendario          risk_rules + WebSearch: FOMC/CPI/NFP hoy-mañana, earnings 24 h
[ ] 5. Noticias            de las posiciones abiertas y de los candidatos
[ ] 6. Análisis            1-3 candidatos: etoro_candles (OneDay 60, OneHour 48) + etoro_quote
[ ] 7. Propuestas          propose_trade con tesis; tabla al usuario; opción "no operar"
[ ] 8. OK                  esperar "CONFIRMO P-xxxx" literal (o reject_proposal)
[ ] 9. Ejecución           execute_proposal(id, confirm=true); reportar respuesta literal
[ ] 10. Bitácora           journal_log("checkin", ...)  · viernes: journal_log("review") + benchmark_status
```

## Semanal (viernes tras el cierre)

```
[ ] Nº operaciones, ganadoras/perdedoras, P&L neto, comisiones estimadas
[ ] Peor decisión de la semana y qué regla la habría evitado
[ ] Pérdida semanal vs tope 5 %: ¿pausa?
[ ] benchmark_status: cuenta vs ETF S&P 500
[ ] Calendario macro de la semana siguiente actualizado en config/macro_calendar.json
[ ] ¿Sigue teniendo sentido seguir en Demo / pasar a Real / parar?
```
