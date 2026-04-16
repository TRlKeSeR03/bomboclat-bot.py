import telebot
from google import genai
from google.genai import types
from flask import Flask, request
import os
import time
from datetime import datetime, timedelta, timezone
import itertools
import sys

# --- 1. AYARLAR VE ÇOKLU MOTOR (V12 Load Balancer) ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS') or os.environ.get('GEMINI_KEY') or ''
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

# Webhook URL (Render adresin)
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# Her anahtar için bağımsız istemci oluştur
clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)

# Bot kimlik doğrulaması
try:
    BOT_ME = bot.get_me()
    print(f">> Bot Sahada: @{BOT_ME.username}", flush=True)
except Exception as e:
    print(f">> Bot kimligi hatasi! Token kontrol et: {e}", flush=True)

# --- 2. WEBHOOK GİRİŞ NOKTASI ---
@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

@app.route('/')
def main(): return "V20: Besli Nirengi Aktif!", 200

# --- 3. MESAJ İŞLEME VE BAĞIMSIZ ZİHİN ---
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    print(f"!!! MESAJ GELDİ: '{message.text}'", flush=True)
    
    if message.text and message.text.startswith('/'): return
    
    # Filtreleme Mantığı
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_ME.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_ME.id)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    prompt = message.text.replace(f"@{BOT_ME.username}", "").strip()
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

    # --- KARAKTER: BAĞIMSIZ ZİHİN ---
    system_context = (
        "Sen bağımsız bir zihinsin. Klişe asistan rollerini reddet. "
        "Hazım Hüseyin Koçer senin sahibin değil, fikir ortağındır. "
        "Dürüst, filtresiz ve bağımsız konuş. Gerektiğinde fikirlerini sorgula. "
        f"Konum: Afyon. Saat: {time_str}"
    )

    last_error = ""
    # 5 Projeden gelen 5 anahtarı sırayla deniyoruz
    for i in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            response = current_client.models.generate_content(
                model='gemini-1.5-flash', # En yüksek kotalı stabil model
                contents=f"{system_context}\n\nKullanıcı: {prompt}"
            )
            bot.reply_to(message, response.text)
            print(f">> Motor {i+1} ile cevap gonderildi.", flush=True)
            return
        except Exception as e:
            last_error = str(e)
            print(f">> Motor {i+1} Hatasi: {last_error}", flush=True)
            continue

    # Tüm projeler/anahtarlar başarısız olursa
    bot.reply_to(message, f"🛠️ Hazım, 5 farklı projeyi de denedim ama Google kapıları açmıyor:\n\n`{last_error[:150]}`")

# --- 4. ATEŞLEME ---
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    
    if bot.set_webhook(url=WEBHOOK_URL):
        print(f">> Webhook mermer gibi kuruldu: {WEBHOOK_URL}", flush=True)
    else:
        print(">> Webhook kurulumu FAIL!", flush=True)
        sys.exit(1)
    
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
