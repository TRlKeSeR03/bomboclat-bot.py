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

# --- 🔒 GÜVENLİK DUVARI ---
allowed_ids_env = os.environ.get('ALLOWED_USERS') or ''
ALLOWED_USERS = [int(i.strip()) for i in allowed_ids_env.split(',') if i.strip()]

WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"
MODEL_ID = 'gemini-2.5-flash' 

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
BOT_INFO = bot.get_me()

chat_histories = {}

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Yabancı"
    
    # --- 🆔 ID ÖĞRENME (Her zaman çalışır) ---
    if message.text and message.text.lower() in ["/id", "id", "numaram kaç"]:
        bot.reply_to(message, f"Senin Telegram ID numaran: `{user_id}`")
        return

    # 🕵️ GÜVENLİK KONTROLÜ
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        if message.chat.type == 'private':
            bot.reply_to(message, f"Üzgünüm {user_name}, Hazım'dan izin almadan benimle konuşamazsın. ID numaran: `{user_id}`")
        return

    # --- Standart Mesaj İşleme ---
    if message.text and message.text.startswith('/'): return
    
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_INFO.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_INFO.id)

    if not (is_private or is_tagged or is_reply_to_me): return

    chat_id = message.chat.id
    prompt = message.text.replace(f"@{BOT_INFO.username}", "").strip()
    
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    system_context = (
        f"Senin adın Bomboclat. Hazım Hüseyin Koçer tarafından geliştirilen bağımsız bir zihinsin. "
        f"Grup üyesi gibi cool ve rasyonel davran. Konuştuğun kişi: {user_name}. "
        f"Hazım ile samimi ol, başkalarıyla mesafeli ol. (Saat: {time_str})"
    )

    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-8:]
    full_history = "\n".join(chat_histories[chat_id])

    last_error = ""
    for i in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            response = current_client.models.generate_content(
                model=MODEL_ID, 
                contents=f"{system_context}\n\nGEÇMİŞ:\n{full_history}\n\nBomboclat:"
            )
            
            if response and response.text:
                chat_histories[chat_id].append(f"Bomboclat: {response.text}")
                bot.reply_to(message, response.text)
                return
                
        except Exception as e:
            last_error = str(e)
            print(f">> Hata: {last_error[:40]}", flush=True)
            time.sleep(0.3)
            continue

    bot.reply_to(message, f"🛠️ Hazım, sistemler meşgul. Hata: {last_error[:40]}")

# Flask ve Webhook (Aynı kalıyor)
@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V41: ID Sistemi Aktif!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
