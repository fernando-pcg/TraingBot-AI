# 🚀 Inicio Rápido - TraingBot-AI

## ⚡ Configuración en 5 Minutos

### Paso 1: Instalar Dependencias
```bash
pip install -r requirements.txt
```

### Paso 2: Configurar CryptoCompare (Opcional pero Recomendado)
1. Registrarse (gratis): https://www.cryptocompare.com/cryptopian/api-keys
2. Copiar tu API key
3. Configurar:

**Windows (PowerShell)**:
```powershell
$env:CRYPTOCOMPARE_API_KEY = "tu-api-key-aqui"
```

**Windows (CMD)**:
```cmd
set CRYPTOCOMPARE_API_KEY=tu-api-key-aqui
```

**Linux/Mac**:
```bash
export CRYPTOCOMPARE_API_KEY="tu-api-key-aqui"
```

### Paso 3: Verificar Configuración
```bash
python test_apis_config.py
```

### Paso 4: Ejecutar el Bot
```bash
# Opción 1: Con análisis de sentiment (recomendado)
python src/main.py --symbol BTCUSDT --duration 60

# Opción 2: Solo análisis técnico
python src/main.py --symbol BTCUSDT --duration 60 --no-sentiment

# Opción 3: Con GPT para señales ambiguas (requiere OpenAI API key)
python src/main.py --symbol BTCUSDT --duration 60 --use-gpt
```

## 📊 ¿Qué APIs usa el bot?

### ✅ Gratuitas (sin configuración):
- **CoinGecko**: Precios, market cap, trending
- **Fear & Greed Index**: Sentiment del mercado

### ⚠️ Gratuitas (requieren registro):
- **CryptoCompare**: Noticias, datos sociales

### 💰 Opcional (de pago):
- **OpenAI GPT**: Análisis mejorado de señales ambiguas

## 🎯 Opciones del Bot

```bash
python src/main.py --help

Opciones:
  --symbol BTCUSDT        Par a tradear (default: BTCUSDT)
  --duration 60           Duración en minutos (default: 10)
  --interval 60           Intervalo entre checks en segundos (default: 60)
  --no-sentiment          Deshabilitar análisis de sentiment
  --use-gpt               Habilitar GPT (requiere API key)
  --dry-run               Modo simulación
  --profile testnet       Perfil de configuración (default: testnet)
```

## 📚 Documentación Completa

- **FASE3_SETUP_GUIDE.md**: Guía detallada de todas las APIs
- **trading-bot-evolution.plan.md**: Plan completo del proyecto
- **README.md**: Documentación general

## 🆘 Problemas Comunes

### "CryptoCompare API error"
→ Configura tu API key (ver Paso 2)

### "No module named 'openai'"
→ Instala: `pip install openai`

### "Rate limit exceeded"
→ El sistema de caché debería prevenir esto, espera 1 minuto

### El bot no genera señales
→ Normal, espera a que las condiciones de mercado sean favorables

## 💡 Consejos

1. **Empieza en testnet**: El bot usa testnet por defecto
2. **Usa dry-run**: Prueba sin riesgo con `--dry-run`
3. **Configura CryptoCompare**: Mejora mucho el análisis
4. **GPT es opcional**: El bot funciona bien sin él
5. **Revisa los logs**: Toda la info está en `logs/`

## 🎉 ¡Listo!

Tu bot está configurado y listo para operar. ¡Buena suerte! 🚀

