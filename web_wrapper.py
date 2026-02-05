from flask import Flask
import threading
import asyncio
import os
from forex_bot_combined import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, FOREX_PAIRS,
    analyze_pair, format_signal, Bot, datetime
)

app = Flask(__name__)

# Variabile per tracciare se il bot è attivo
bot_running = False

async def send_telegram_message(bot, message):
    """Invia un messaggio su Telegram"""
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')
        print(f"✅ Messaggio inviato")
    except Exception as e:
        print(f"❌ Errore invio: {e}")

async def run_scan():
    """Esegue una scansione del mercato forex"""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    print(f"\n🔍 Scansione in corso... {datetime.now().strftime('%H:%M:%S')}")
    
    signals_found = 0
    for pair in FOREX_PAIRS:
        print(f"  Analizzando {pair}...")
        for timeframe in ['1h', '1d']:
            signal = analyze_pair(pair, timeframe)
            if signal:
                signals_found += 1
                signal_type = signal['signal']
                print(f"  ✅ SEGNALE {signal_type} su {pair} ({timeframe})")
                message = format_signal(signal)
                await send_telegram_message(bot, message)
                await asyncio.sleep(2)
    
    print(f"✅ Scansione completata: {signals_found} segnali trovati")
    return signals_found

async def bot_loop():
    """Loop principale del bot - scansione ogni 3 ore"""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Messaggio di avvio
    await send_telegram_message(
        bot,
        "🤖 <b>Bot Forex Signals avviato!</b>\n\n"
        "Monitoraggio attivo su H1 e D1.\n"
        "📈 Cerca opportunità LONG (acquisto)\n"
        "📉 Cerca opportunità SHORT (vendita)"
    )
    
    # Loop infinito con scansioni ogni 3 ore
    while True:
        try:
            await run_scan()
            print("⏰ Prossima scansione tra 3 ore...")
            await asyncio.sleep(10800)  # 3 ore
        except Exception as e:
            print(f"❌ Errore: {e}")
            await asyncio.sleep(300)  # Riprova tra 5 minuti se c'è un errore

def start_bot_background():
    """Avvia il bot in background"""
    global bot_running
    if not bot_running:
        bot_running = True
        print("🤖 Avvio bot in background...")
        asyncio.run(bot_loop())

# Avvia il bot in un thread separato
bot_thread = threading.Thread(target=start_bot_background, daemon=True)
bot_thread.start()

# Route Flask per mantenere il servizio attivo
@app.route('/')
def home():
    return """
    <h1>🤖 Forex Bot Attivo!</h1>
    <p>Il bot sta monitorando il mercato forex.</p>
    <p>Status: ✅ Online</p>
    <p><a href="/health">Health Check</a></p>
    <p><a href="/scan">Forza Scansione</a></p>
    """

@app.route('/health')
def health():
    return {"status": "ok", "bot_running": bot_running}

@app.route('/scan')
def manual_scan():
    """Endpoint per forzare una scansione manuale"""
    try:
        result = asyncio.run(run_scan())
        return {"status": "success", "signals_found": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"🚀 Web server in ascolto sulla porta {port}")
    print(f"🤖 Bot forex in esecuzione in background")
    app.run(host='0.0.0.0', port=port)
