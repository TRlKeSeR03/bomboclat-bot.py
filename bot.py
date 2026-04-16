import telebot
from google import genai
from google.genai import types
from flask import Flask, request
import os
import time  # İŞTE BURASI: Eksik olan parça buydu!
from datetime import datetime, timedelta, timezone
import itertools
import sys

# --- 1. AYARLAR VE V12 MOTORLARI ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS') or os.environ.get('GEMINI_KEY') or ''
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

# Webhook adresi (Render URL'in)
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)

# Bot bilgilerini çekelim
try:
    BOT_ME = bot.get_me()
    print(f">> Bot Kimliği Doğrulandı: @{BOT_ME.username}", flush=True)
except Exception as e:
    print(f">> Bot kimliği alınamadı: {e}", flush=True)

# --- 2. WEBHOOK GİRİŞİ ---
@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

@app.route('/')
def main(): return "V17: Bağımsız Zihin Yayında!", 200

# --- 3. MESAJ İŞLEME ---
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    print(f"!!! MESAJ GELDİ: '{message.text}'", flush=True)
    
    if message.text and message.text.startswith('/'): return
    
    # Bağımsız Zihin Filtreleri
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_ME.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_ME.id)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    prompt = message.text.replace(f"@{BOT_ME.username}", "").strip()
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

    # --- KARAKTER TALİMATI ---
    system_context = (
        "Sen bağımsız bir zihinsin. Hazım'ın fikir ortağısın. "
        "Asla bir 'yapay zeka asistanı' gibi konuşma. Dürüst, filtresiz ve özgür ol. "
        "Gerektiğinde Hazım'la tartış. Konum: Afyon."
    )

    for i in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            response = current_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"{system_context}\n\nKullanıcı: {prompt}",
                config=types.GenerateContentConfig(tools=[{"google_search": {}}])
            )
            bot.reply_to(message, response.text)
            print(">> Cevap başarıyla gönderildi.", flush=True)
            return
        except Exception as e:
            print(f">> Motor {i+1} Hatası: {e}", flush=True)
            if i == len(api_keys) - 1:
                bot.reply_to(message, "🛠️ Motorlar hararet yaptı, birazdan gelirim.")

# --- 4. ATEŞLEME ---
if __name__ == "__main__":
    # Eski webhookları temizle
    bot.remove_webhook()
    time.sleep(1) # Artık 'time' kütüphanesi yüklü olduğu için hata vermez
    
    # Yeni webhook'u kur
    if bot.set_webhook(url=WEBHOOK_URL):
        print(f">> Webhook mermer gibi kuruldu: {WEBHOOK_URL}", flush=True)
    else:
        print(">> Webhook kurulumu başarısız!", flush=True)
        sys.exit(1)
    
    # Flask sunucusunu başlat
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
