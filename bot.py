import telebot
from google import genai
from google.genai import types
from flask import Flask, request
import os
from datetime import datetime, timedelta, timezone
import itertools

# --- 1. AYARLAR VE V12 MOTORLARI ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS') or os.environ.get('GEMINI_KEY') or ''
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

# Render'ın sana verdiği URL (Örn: https://bomboclat-bot-py.onrender.com)
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)

# --- 2. WEBHOOK ROTASI (KALBİN ATTIĞI YER) ---
@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route('/')
def main(): return "Bağımsız Zihin Webhook Modunda Aktif!", 200

# --- 3. MESAJ İŞLEME MANTIĞI ---
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return
    
    # Filtreleme (Kritik: Webhook'ta bot.get_me her seferinde çağrılmaz)
    me_id = bot.get_me().id
    me_username = bot.get_me().username
    
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{me_username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == me_id)

    if not (is_private or is_tagged or is_reply_to_me): return

    prompt = message.text.replace(f"@{me_username}", "").strip()
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

    # KARAKTER: BAĞIMSIZ ZİHİN
    system_context = f"Sen bağımsız bir zihinsin. Hazım'ın asistanı değil, muhatabısın. Dürüst ol. Saat: {time_str}"

    for i in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            response = current_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"{system_context}\n\nKullanıcı: {prompt}",
                config=types.GenerateContentConfig(tools=[{"google_search": {}}])
            )
            bot.reply_to(message, response.text)
            return
        except Exception:
            continue

# --- 4. SİSTEMİ ATEŞLE (WEBHOOK'U KUR) ---
if __name__ == "__main__":
    # Önce eski bağlantıları sök
    bot.remove_webhook()
    # Yeni webhook'u kur
    bot.set_webhook(url=WEBHOOK_URL)
    
    # Flask sunucusunu başlat (Render bunu dinleyecek)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
