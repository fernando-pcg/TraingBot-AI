"""Script para ver resumen de trades del bot."""

import json
from pathlib import Path
from datetime import datetime

def load_trades():
    trades_file = Path("state/trades.json")
    if not trades_file.exists():
        print("❌ No hay trades registrados aún")
        return []
    
    with open(trades_file, 'r') as f:
        return json.load(f)

def show_summary():
    trades = load_trades()
    
    if not trades:
        print("\n📊 No hay operaciones registradas\n")
        return
    
    total_trades = len(trades)
    winning = [t for t in trades if t.get('pnl', 0) > 0]
    losing = [t for t in trades if t.get('pnl', 0) < 0]
    
    total_pnl = sum(t.get('pnl', 0) for t in trades)
    win_rate = (len(winning) / total_trades * 100) if total_trades > 0 else 0
    
    avg_win = sum(t['pnl'] for t in winning) / len(winning) if winning else 0
    avg_loss = sum(t['pnl'] for t in losing) / len(losing) if losing else 0
    
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE TRADING")
    print("=" * 70)
    print(f"\n📈 Total operaciones: {total_trades}")
    print(f"✅ Operaciones ganadoras: {len(winning)}")
    print(f"❌ Operaciones perdedoras: {len(losing)}")
    print(f"🎯 Win Rate: {win_rate:.2f}%")
    print(f"\n💰 P&L Total: {total_pnl:.2f} USDT")
    print(f"📊 Ganancia promedio: {avg_win:.2f} USDT")
    print(f"📉 Pérdida promedio: {avg_loss:.2f} USDT")
    
    if avg_loss != 0:
        profit_factor = abs(avg_win * len(winning) / (avg_loss * len(losing)))
        print(f"⚖️  Profit Factor: {profit_factor:.2f}")
    
    print("\n" + "=" * 70)
    print("📋 ÚLTIMAS 10 OPERACIONES:")
    print("=" * 70)
    
    for trade in trades[-10:]:
        timestamp = datetime.fromtimestamp(trade['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        symbol = trade['symbol']
        pnl = trade['pnl']
        entry = trade['entry_price']
        exit = trade['exit_price']
        pnl_pct = (exit / entry - 1) * 100
        
        emoji = "✅" if pnl > 0 else "❌"
        print(f"{emoji} {timestamp} | {symbol} | Entry: {entry:.2f} | Exit: {exit:.2f} | PnL: {pnl:+.2f} USDT ({pnl_pct:+.2f}%)")
    
    print("=" * 70 + "\n")

if __name__ == "__main__":
    show_summary()

