import telebot
from google import genai
from google.genai import types
from flask import Flask, request
import os
import time
from datetime import datetime, timedelta, timezone
import itertools
import sys

# --- 1. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS') or os.environ.get('GEMINI_KEY') or ''
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# İstemcileri tazeleyelim
clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)

try:
    BOT_ME = bot.get_me()
    print(f">> Bot Sahada: @{BOT_ME.username}", flush=True)
except Exception as e:
    print(f">> Bot kimligi hatasi! Token gecersiz olabilir: {e}", flush=True)

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Error", 403

@app.route('/')
def main(): return "V21 Yayında!", 200

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    print(f"!!! MESAJ: '{message.text}'", flush=True)
    if message.text and message.text.startswith('/'): return
    
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_ME.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_ME.id)

    if not (is_private or is_tagged or is_reply_to_me): return

    prompt = message.text.replace(f"@{BOT_ME.username}", "").strip()
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

    # --- BAĞIMSIZ ZİHİN TALİMATI ---
    system_context = (
        "Sen bağımsız bir zihinsin. Hazım'ın fikir ortağısın. "
        "Dürüst, filtresiz ve bağımsız konuş. Robotik cevaplardan kaçın. "
        f"Zaman: {time_str}. Konum: Afyonkarahisar."
    )

    last_error = ""
    for i in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            
            # 2026 STANDARDI: gemini-2.0-flash
            # Eğer yine 404 verirse sadece 'gemini-1.5-flash' dene (başına models/ koymadan)
            response = current_client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=f"{system_context}\n\nKullanıcı: {prompt}"
            )
            bot.reply_to(message, response.text)
            print(f">> Motor {i+1} basarili.", flush=True)
            return
        except Exception as e:
            last_error = str(e)
            print(f">> Motor {i+1} Hatasi: {last_error}", flush=True)
            continue

    bot.reply_to(message, f"🛠️ Hazım, Google ile lisan sorunumuz var:\n\n`{last_error[:200]}`")

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(2)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
