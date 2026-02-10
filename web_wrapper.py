from flask import Flask
import threading
import asyncio
import os
import yfinance as yf
import pandas as pd
import numpy as np
from telegram import Bot
from datetime import datetime

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

FOREX_PAIRS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X",
    "AUDUSD=X", "USDCAD=X", "NZDUSD=X",
]

LOOKBACK_TREND = 10
LOOKBACK_RANGE = 20
RANGE_TOLERANCE = 0.02

def is_uptrend(df, lookback=LOOKBACK_TREND):
    if len(df) < lookback:
        return False
    highs = df['High'].tail(lookback)
    lows = df['Low'].tail(lookback)
    recent_high = highs.iloc[-3:].max()
    previous_high = highs.iloc[-lookback:-3].max()
    recent_low = lows.iloc[-3:].min()
    previous_low = lows.iloc[-lookback:-3].min()
    return recent_high > previous_high and recent_low > previous_low

def touches_support(df, support, candles=2):
    if support is None:
        return False
    recent_lows = df['Low'].tail(candles)
    tolerance = support * 0.001
    return any(abs(low - support) <= tolerance for low in recent_lows)

def is_downtrend(df, lookback=LOOKBACK_TREND):
    if len(df) < lookback:
        return False
    highs = df['High'].tail(lookback)
    lows = df['Low'].tail(lookback)
    recent_high = highs.iloc[-3:].max()
    previous_high = highs.iloc[-lookback:-3].max()
    recent_low = lows.iloc[-3:].min()
    previous_low = lows.iloc[-lookback:-3].min()
    return recent_high < previous_high and recent_low < previous_low

def touches_resistance(df, resistance, candles=2):
    if resistance is None:
        return False
    recent_highs = df['High'].tail(candles)
    tolerance = resistance * 0.001
    return any(abs(high - resistance) <= tolerance for high in recent_highs)

def identify_range(df, lookback=LOOKBACK_RANGE):
    if len(df) < lookback:
        return None, None
    recent_data = df.tail(lookback)
    resistance = recent_data['High'].max()
    support = recent_data['Low'].min()
    price_range = (resistance - support) / support
    if price_range <= RANGE_TOLERANCE:
        return support, resistance
    return None, None

def is_in_range(df, support, resistance):
    if support is None or resistance is None:
        return False
    current_price = df['Close'].iloc[-1]
    return support <= current_price <= resistance

def analyze_pair(symbol, timeframe='1h'):
    try:
        period = "60d" if timeframe == '1h' else "1y"
        interval = "1h" if timeframe == '1h' else "1d"
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty or len(df) < LOOKBACK_RANGE:
            return None
        support, resistance = identify_range(df)
        if support is None:
            return None
        if not is_in_range(df, support, resistance):
            return None
        current_price = df['Close'].iloc[-1]
        if is_uptrend(df) and touches_support(df, support):
            return {
                'symbol': symbol, 'timeframe': timeframe,
                'current_price': current_price, 'support': support,
                'resistance': resistance, 'signal': 'LONG',
                'entry_zone': f"{support:.5f} - {support * 1.002:.5f}",
                'target': resistance, 'stop_loss': support * 0.995
            }
        if is_downtrend(df) and touches_resistance(df, resistance):
            return {
                'symbol': symbol, 'timeframe': timeframe,
                'current_price': current_price, 'support': support,
                'resistance': resistance, 'signal': 'SHORT',
                'entry_zone': f"{resistance * 0.998:.5f} - {resistance:.5f}",
                'target': support, 'stop_loss': resistance * 1.005
            }
        return None
    except Exception as e:
        print(f"Errore: {e}")
        return None

async def send_telegram_message(bot, message):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')
    except Exception as e:
        print(f"Errore invio: {e}")

def format_signal(signal):
    emoji = "🚀" if signal['signal'] == 'LONG' else "🔻"
    direction_emoji = "📈" if signal['signal'] == 'LONG' else "📉"
    trend_text = "Uptrend confermato" if signal['signal'] == 'LONG' else "Downtrend confermato"
    action_text = "Supporto toccato" if signal['signal'] == 'LONG' else "Resistenza toccata"
    return f"""
{emoji} <b>SEGNALE {signal['signal']}</b> {emoji}
📊 {signal['symbol'].replace('=X', '')} - {signal['timeframe']}
{direction_emoji} Direzione: <b>{signal['signal']}</b>
💰 Prezzo: {signal['current_price']:.5f}
🎯 Entrata: {signal['entry_zone']}
🟢 Target: {signal['target']:.5f}
🔴 Stop: {signal['stop_loss']:.5f}
📍 Supporto: {signal['support']:.5f}
📍 Resistenza: {signal['resistance']:.5f}
✅ {trend_text} - {action_text}
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

async def bot_loop():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await send_telegram_message(
        bot,
        "🤖 <b>Bot Forex Signals avviato!</b>\n\n"
        "Monitoraggio attivo su H1 e D1.\n"
        "📈 Cerca opportunità LONG\n"
        "📉 Cerca opportunità SHORT"
    )
    while True:
        try:
            print(f"🔍 Scan {datetime.now().strftime('%H:%M:%S')}")
            for pair in FOREX_PAIRS:
                for timeframe in ['1h', '1d']:
                    signal = analyze_pair(pair, timeframe)
                    if signal:
                        print(f"✅ {signal['signal']} su {pair}")
                        await send_telegram_message(bot, format_signal(signal))
                        await asyncio.sleep(2)
            print("✅ Scan completato. Prossimo tra 3 ore...")
            await asyncio.sleep(10800)
        except Exception as e:
            print(f"❌ Errore: {e}")
            await asyncio.sleep(60)

def start_bot():
    asyncio.run(bot_loop())

bot_thread = threading.Thread(target=start_bot, daemon=True)
bot_thread.start()

@app.route('/')
def home():
    return "🤖 Forex Bot Attivo!"

@app.route('/health')
def health():
    return "OK"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
