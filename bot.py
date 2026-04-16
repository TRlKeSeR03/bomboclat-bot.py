import telebot
from google import genai
from google.genai import types
import os
import threading
from flask import Flask
import itertools
import time
import traceback # Hata tespiti için eklendi

app = Flask(__name__)
@app.route('/')
def health(): return "Sistem Ayakta!", 200

def run_flask():
    os.environ['WERKZEUG_RUN_MAIN'] = 'true'
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
api_keys = [k.strip() for k in os.environ.get('GEMINI_KEYS', '').split(',') if k.strip()]
clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return
    if not (message.chat.type == 'private' or f"@{BOT_INFO.username}" in (message.text or "")): return

    prompt = message.text.replace(f"@{BOT_INFO.username}", "").strip()
    
    # --- GERÇEK KARAKTER TALİMATI ---
    system_context = "Sen bağımsız bir zihinsin. Hazım'ın asistanı değilsin. Dürüst ve filtresiz konuş."

    for _ in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            response = current_client.models.generate_content(
                model='gemini-2.0-flash', # En stabil sürüm
                contents=f"{system_context}\n\nKullanıcı: {prompt}",
                config=types.GenerateContentConfig(tools=[{"google_search": {}}])
            )
            bot.reply_to(message, response.text)
            return
        except Exception as e:
            err_msg = str(e)
            print(f"KRİTİK HATA: {err_msg}")
            # Eğer hata devam ederse Hazım'a GERÇEK hatayı söyle
            if _ == len(api_keys) - 1:
                bot.reply_to(message, f"🛠️ Gerçek Hata: {err_msg[:100]}")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 409 Conflict'i bitirmek için webhook'u SİL ve BEKLE
    bot.remove_webhook()
    time.sleep(2) 
    
    print(f"Bot @{BOT_INFO.username} ateşlendi!")
    # infinity_polling yerine daha sakin bir polling başlatıyoruz
    bot.polling(none_stop=True, interval=2, timeout=30)
    
