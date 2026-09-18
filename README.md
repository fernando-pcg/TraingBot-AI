# TraingBot-AI · eToro MCP + skill de trading disciplinado

Un servidor MCP propio que envuelve la API pública de eToro y una skill de Claude Code que impone la disciplina: **tú apruebas cada operación antes de que se ejecute**. Pensado para una cuenta pequeña (~200 USD), sin apalancamiento y con topes de pérdida.

- El MCP son las manos: consulta portafolio, cotizaciones y velas; genera propuestas que pasan por el motor de riesgo; ejecuta solo con `confirm=true` sobre una propuesta aprobada; escribe la bitácora.
- La skill es la disciplina: reglas, checklist diario, formato de propuesta y protocolo de confirmación (`.claude/skills/etoro-trading/`).

> No es asesoramiento financiero. Con 200 USD en plazos cortos, spreads y comisiones pesan mucho y ningún sistema de señales gana de forma consistente. Úsalo como laboratorio con disciplina, empieza en Demo y compara contra un ETF del S&P 500.

## Estructura

```
.mcp.json                         Configuración MCP para Claude Code (lee las keys del entorno)
.env.example                      Variables de entorno necesarias
etoro_mcp/
  server.py                       19 herramientas MCP (stdio)
  client.py                       Cliente HTTP de la API pública (headers, rutas demo/real)
  risk.py                         Motor de reglas: tamaño, topes, ventanas de evento
  journal.py                      Bitácora (jsonl + markdown), propuestas, benchmark
  config.py                       Carga de env y de config/*.json
config/
  risk.json                       Reglas de riesgo (editable)
  universe.json                   Activos permitidos
  macro_calendar.json             Fechas FOMC/CPI (mantener al día)
.claude/skills/etoro-trading/     SKILL.md + reglas.md + checklist.md + plantillas.md
journal/                          Bitácora y propuestas (no se versionan)
tests/                            46 tests: riesgo, cliente, bitácora, flujo completo con API simulada
```

## 1. Keys de eToro (nunca en el chat)

1. Entra en <https://api-portal.etoro.com/> y crea las keys. Cada key sirve para **un solo entorno** (Demo o Real) y se elige permiso Read o Write.
2. Crea primero una key **Demo con Write** para probar.
3. La key **Real** créala solo cuando decidas pasar a real, con whitelist de IP y fecha de expiración corta.
4. Guárdalas en variables de entorno de tu máquina (o en un `.env` local que no se versiona):

```bash
cp .env.example .env
# edita .env y rellena ETORO_API_KEY y ETORO_USER_KEY
set -a; source .env; set +a      # o exporta las variables en tu shell profile
```

## 2. Instalación (en tu PC)

El servidor debe correr donde estén las keys: tu máquina. Claude Code en la nube no llega a `public-api.etoro.com` (egress bloqueado) y sus contenedores son efímeros, así que allí solo se edita código.

Se necesita Python 3.11 o superior. El Python que trae macOS (3.9) no sirve, así que la vía recomendada es **uv**, que descarga el Python correcto y crea el entorno solo:

```bash
# instalar uv (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell): powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

cd TraingBot-AI
uv sync --extra dev                 # crea .venv con Python 3.11+ e instala dependencias
uv run python -m pytest -q          # 46 passed
uv run python -m etoro_mcp          # debe imprimir "etoro-mcp 0.1.0 · modo=..."; Ctrl+C para salir
```

`.mcp.json` ya lanza el servidor con `uv run`, así que Claude Code usará ese mismo entorno sin configurar nada más. Si prefieres no usar uv, instala Python 3.11+ (por ejemplo `brew install python@3.12`) y cambia `command`/`args` de `.mcp.json` a ese intérprete con `-m etoro_mcp`.

## 1b. Qué key es cada variable

eToro entrega dos valores por key. Se mapean así:

| eToro | Header | Variable |
|---|---|---|
| Key pública (API key) | `x-api-key` | `ETORO_API_KEY` |
| Key privada (User key) | `x-user-key` | `ETORO_USER_KEY` |

No las pegues en el chat de Claude: van en `.env` o en el entorno del sistema. Si una key se filtró, revócala en el portal y crea otra.

## 3. Conectar en Claude Code

El repo trae `.mcp.json`; al abrir Claude Code en esta carpeta te pedirá aprobar el servidor `etoro`. Las keys se leen de tu entorno con `${ETORO_API_KEY}`, nunca del archivo.

Comprueba con `/mcp` que aparece `etoro` con 19 herramientas y pide: "sesión de trading" para activar la skill.

Si prefieres el servidor a nivel de usuario (fuera del repo):

```bash
claude mcp add etoro -s user -e ETORO_MODE=demo -e ETORO_API_KEY=... -e ETORO_USER_KEY=... -- uv run --project /ruta/al/repo python -m etoro_mcp
```

### Claude Desktop

En `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "etoro": {
      "command": "uv",
      "args": ["run", "--project", "/ruta/al/repo", "python", "-m", "etoro_mcp"],
      "env": { "ETORO_MODE": "demo", "ETORO_API_KEY": "…", "ETORO_USER_KEY": "…", "ETORO_MCP_HOME": "/ruta/al/repo" }
    }
  }
}
```

### Desde el móvil

Claude Code se puede manejar en remoto desde la app de Claude. La sesión diaria (checklist, propuestas, confirmación) funciona igual: el servidor corre donde tengas las keys.

## 4. Flujo de una sesión

```
Tú:     sesión de trading
Claude: etoro_status → portafolio → calendario/noticias → análisis → propose_trade
        Propuesta P-20260918-140501-3F2A · SPY compra · 80 USD · stop 490 · TP 520 · riesgo 4 USD
        Para ejecutar responde exactamente: CONFIRMO P-20260918-140501-3F2A
Tú:     CONFIRMO P-20260918-140501-3F2A
Claude: execute_proposal(…, confirm=true) → orden aceptada → bitácora
```

Sin la frase literal no hay ejecución. Las propuestas expiran a los 30 min y se bloquean si el precio se movió más de 0.5 %.

## 5. Reglas que aplica el MCP (config/risk.json)

| Regla | Valor |
|---|---|
| Apalancamiento | 1x |
| Universo | ETFs de índices, large caps, BTC/ETH (`config/universe.json`) |
| Riesgo por operación | 2 % (máx. 3 %) → 4-6 USD |
| Stop-loss | Obligatorio, 0.3 %-10 % de la entrada |
| Ratio beneficio/riesgo | ≥ 1.5 |
| Posiciones / aperturas por día | ≤ 5 / ≤ 2 |
| Pérdida diaria / semanal | 3 % / 5 % realizada → pausa |
| Eventos | FOMC/CPI: 2 h antes, 1 h después · earnings del activo: 24 h antes |
| Mínimo por posición | 10 USD (verifica en eToro) |

## 6. Agent Portfolio de eToro

eToro permite crear un **Agent Portfolio**: un sub-portafolio independiente controlado con su propia API key, que tu cuenta principal copia con la asignación que elijas (por ejemplo 200 USD). Es el montaje recomendado para este MCP:

- Las keys del Agent Portfolio operan solo ese portafolio; el resto de tu cuenta queda fuera del alcance del agente.
- `etoro_status` debe devolver `creditAvailableUsd` ≈ tu asignación. Ajusta `capital_usd` en `config/risk.json` si cambias la asignación en la app.
- Es dinero real: su key va con `ETORO_MODE=real` y `ETORO_ALLOW_REAL_TRADING=true`. Para las primeras semanas usa una key Demo normal.
- `etoro_copy_status` muestra mirrors si el portafolio los tuviera; en un Agent Portfolio normalmente estará vacío.

## 7. Paso a Real (doble candado)

1. Key Real con Write, whitelist de IP y expiración corta.
2. `ETORO_MODE=real` **y** `ETORO_ALLOW_REAL_TRADING=true`. Sin la segunda variable, las herramientas de ejecución se niegan.
3. Solo después de 3-4 semanas en Demo con bitácora y `benchmark_status` favorable.
4. Primera sesión en Real: solo `etoro_status`, y comprobar que crédito y posiciones coinciden con el Agent Portfolio en la app antes de proponer nada.

## Notas técnicas

- Endpoints: `https://public-api.etoro.com/api/v1`, headers `x-request-id`, `x-api-key`, `x-user-key`. Rutas Demo: `/trading/info/demo/...` y `/trading/execution/demo/...`. Los paths se tomaron de la API pública y de dos wrappers open source; la documentación oficial no era accesible desde el entorno donde se escribió esto, así que la primera sesión en Demo sirve para verificarlos (`etoro_status` ejercita portafolio e historial).
- Logs a stderr; stdout es el transporte MCP.
- Historial anterior del repo (bot de Binance) eliminado; sigue disponible en el historial de git.
