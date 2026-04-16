import telebot
from google import genai
from google.genai import types
from flask import Flask, request
import os
import time
from datetime import datetime, timedelta, timezone
import itertools

# --- 1. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS') or os.environ.get('GEMINI_KEY') or ''
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)

try:
    BOT_ME = bot.get_me()
    print(f">> Bot Sahada: @{BOT_ME.username}", flush=True)
except Exception as e:
    print(f">> Bot kimligi hatasi: {e}", flush=True)

# --- 2. WEBHOOK ---
@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Error", 403

@app.route('/')
def main(): return "V18 Aktif!", 200

# --- 3. MESAJ İŞLEME ---
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return
    
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_ME.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_ME.id)

    if not (is_private or is_tagged or is_reply_to_me): return

    prompt = message.text.replace(f"@{BOT_ME.username}", "").strip()
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

    system_context = (
        "Sen bağımsız bir zihinsin. Klişe asistan rollerini reddet. "
        "Hazım'la dürüstçe tartış. Robotik olma. Konum: Afyon."
    )

    last_error = ""
    for i in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            # DİKKAT: Eğer 2.5 hata verirse burayı 'gemini-2.0-flash' yapmalısın
            response = current_client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=f"{system_context}\n\nKullanıcı: {prompt}",
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}] # Sorun buradaysa bunu silebiliriz
                )
            )
            bot.reply_to(message, response.text)
            return
        except Exception as e:
            last_error = str(e)
            print(f">> Motor {i+1} Hatasi: {last_error}", flush=True)
            continue

    # EĞER BURAYA GELİRSE TÜM MOTORLAR ÇÖKMÜŞTÜR
    bot.reply_to(message, f"🛠️ Hazım, 5 motoru da denedim ama Google şu hatayı verdi:\n\n`{last_error[:200]}`")

# --- 4. ATEŞLEME ---
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
