import yfinance as yf
import pandas as pd
import numpy as np
from telegram import Bot
import asyncio
from datetime import datetime, timedelta
import os

# =============== CONFIGURAZIONE ===============
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Coppie Forex Major
FOREX_PAIRS = [
    "EURUSD=X",
    "GBPUSD=X",
    "USDJPY=X",
    "USDCHF=X",
    "AUDUSD=X",
    "USDCAD=X",
    "NZDUSD=X",
]

# Parametri strategia
LOOKBACK_TREND = 10
LOOKBACK_RANGE = 20
RANGE_TOLERANCE = 0.02

# =============== FUNZIONI ANALISI LONG ===============

def is_uptrend(df, lookback=LOOKBACK_TREND):
    """Verifica se ci sono massimi e minimi crescenti"""
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
    """Verifica se il prezzo ha toccato il supporto"""
    if support is None:
        return False
    
    recent_lows = df['Low'].tail(candles)
    tolerance = support * 0.001
    
    return any(abs(low - support) <= tolerance for low in recent_lows)


# =============== FUNZIONI ANALISI SHORT ===============

def is_downtrend(df, lookback=LOOKBACK_TREND):
    """Verifica se ci sono massimi e minimi decrescenti"""
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
    """Verifica se il prezzo ha toccato la resistenza"""
    if resistance is None:
        return False
    
    recent_highs = df['High'].tail(candles)
    tolerance = resistance * 0.001
    
    return any(abs(high - resistance) <= tolerance for high in recent_highs)


# =============== FUNZIONI COMUNI ===============

def identify_range(df, lookback=LOOKBACK_RANGE):
    """Identifica supporto e resistenza del range"""
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
    """Verifica se il prezzo è in range"""
    if support is None or resistance is None:
        return False
    
    current_price = df['Close'].iloc[-1]
    return support <= current_price <= resistance


def analyze_pair(symbol, timeframe='1h'):
    """Analizza una coppia forex per opportunità LONG e SHORT"""
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
        
        in_range = is_in_range(df, support, resistance)
        if not in_range:
            return None
        
        current_price = df['Close'].iloc[-1]
        
        if is_uptrend(df) and touches_support(df, support):
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'current_price': current_price,
                'support': support,
                'resistance': resistance,
                'signal': 'LONG',
                'entry_zone': f"{support:.5f} - {support * 1.002:.5f}",
                'target': resistance,
                'stop_loss': support * 0.995
            }
        
        if is_downtrend(df) and touches_resistance(df, resistance):
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'current_price': current_price,
                'support': support,
                'resistance': resistance,
                'signal': 'SHORT',
                'entry_zone': f"{resistance * 0.998:.5f} - {resistance:.5f}",
                'target': support,
                'stop_loss': resistance * 1.005
            }
        
        return None
        
    except Exception as e:
        print(f"Errore nell'analisi di {symbol} su {timeframe}: {e}")
        return None


async def send_telegram_message(bot, message):
    """Invia un messaggio su Telegram"""
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')
        print(f"Messaggio inviato: {message[:50]}...")
    except Exception as e:
        print(f"Errore nell'invio del messaggio: {e}")


def format_signal(signal):
    """Formatta il segnale per Telegram"""
    if signal['signal'] == 'LONG':
        emoji = "🚀"
        direction_emoji = "📈"
        trend_text = "Uptrend confermato (massimi e minimi crescenti)"
        action_text = "Nuovo minimo del range toccato"
    else:
        emoji = "🔻"
        direction_emoji = "📉"
        trend_text = "Downtrend confermato (massimi e minimi decrescenti)"
        action_text = "Nuovo massimo del range toccato"
    
    return f"""
{emoji} <b>SEGNALE TRADING FOREX - {signal['signal']}</b> {emoji}

📊 Coppia: <b>{signal['symbol'].replace('=X', '')}</b>
⏰ Timeframe: <b>{signal['timeframe']}</b>
{direction_emoji} Direzione: <b>{signal['signal']}</b>

💰 Prezzo attuale: {signal['current_price']:.5f}
🎯 Zona di entrata: {signal['entry_zone']}
🟢 Target: {signal['target']:.5f}
🔴 Stop Loss: {signal['stop_loss']:.5f}

📍 Supporto: {signal['support']:.5f}
📍 Resistenza: {signal['resistance']:.5f}

✅ Condizioni verificate:
- {trend_text}
- Prezzo in range
- {action_text}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""


async def main():
    """Funzione principale del bot"""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    print("🤖 Bot Forex COMBINATO avviato...")
    print(f"📊 Monitoraggio di {len(FOREX_PAIRS)} coppie forex")
    print(f"⏰ Timeframes: H1 e D1")
    print(f"📈 Strategia LONG: Uptrend + supporto")
    print(f"📉 Strategia SHORT: Downtrend + resistenza")
    print("-" * 50)
    
    await send_telegram_message(
        bot, 
        "🤖 <b>Bot Forex Signals avviato!</b>\n\n"
        "Monitoraggio attivo su H1 e D1.\n"
        "📈 Cerca opportunità LONG (acquisto)\n"
        "📉 Cerca opportunità SHORT (vendita)"
    )
    
    while True:
        try:
            print(f"\n🔍 Scansione in corso... {datetime.now().strftime('%H:%M:%S')}")
            
            for pair in FOREX_PAIRS:
                print(f"  Analizzando {pair}...")
                
                for timeframe in ['1h', '1d']:
                    signal = analyze_pair(pair, timeframe)
                    
                    if signal:
                        signal_type = signal['signal']
                        print(f"  ✅ SEGNALE {signal_type} TROVATO su {pair} ({timeframe})!")
                        message = format_signal(signal)
                        await send_telegram_message(bot, message)
                        await asyncio.sleep(2)
            
            print(f"✅ Scansione completata. Prossima scansione tra 3 ore...")
            await asyncio.sleep(10800)
            
        except KeyboardInterrupt:
            print("\n⚠️ Bot interrotto dall'utente")
            await send_telegram_message(bot, "⚠️ <b>Bot arrestato</b>")
            break
        except Exception as e:
            print(f"❌ Errore nel loop principale: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════╗
║   BOT TELEGRAM FOREX - LONG + SHORT       ║
║   Segnali automatici combinati            ║
╚═══════════════════════════════════════════╝

STRATEGIA COMBINATA:
📈 LONG: Uptrend + range + supporto
📉 SHORT: Downtrend + range + resistenza
⏰ Timeframes: H1 e D1
🔄 Scansione ogni 3 ore
""")
    
    asyncio.run(main())
