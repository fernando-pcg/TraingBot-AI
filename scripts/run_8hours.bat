@echo off
echo ========================================
echo BOT DE TRADING - SESION DE 8 HORAS
echo Configuracion: CONSERVADORA
echo Moneda: BTCUSDT
echo ========================================
echo.
echo Iniciando bot con parametros conservadores...
echo - Stop Loss: 0.3%%
echo - Take Profit: 0.6%%
echo - Riesgo por operacion: 1%%
echo - Limite de perdida diaria: 5%%
echo - Exposicion maxima: 30%%
echo.

cd /d "%~dp0"

python -m src.main --profile testnet --symbol BTCUSDT --duration 60 --interval 60 --dry-run

echo.
echo ========================================
echo Sesion de trading completada
echo Revisa los logs en la carpeta 'logs' para ver los resultados
echo ========================================
pause

