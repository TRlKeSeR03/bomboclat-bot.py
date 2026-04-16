import telebot
from google import genai
from google.genai import types
from flask import Flask, request
import os
from datetime import datetime, timedelta, timezone
import itertools
import sys

# --- 1. AYARLAR VE V12 MOTORLARI ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS') or os.environ.get('GEMINI_KEY') or ''
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

# Webhook adresi
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)

# Bot bilgilerini bir kez çekelim (Hız için)
try:
    BOT_ME = bot.get_me()
    print(f">> Bot Kimliği Doğrulandı: @{BOT_ME.username}", flush=True)
except Exception as e:
    print(f">> Bot kimliği alınamadı, Token kontrol et: {e}", flush=True)

# --- 2. WEBHOOK GİRİŞ NOKTASI ---
@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return "V16: Bağımsız Zihin Aktif!", 200

# --- 3. MESAJ İŞLEME VE TEŞHİS ---
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    # TEŞHİS 1: Mesaj sunucuya ulaştı mı?
    print(f"!!! MESAJ GELDİ: '{message.text}' (Chat Tipi: {message.chat.type})", flush=True)
    
    if message.text and message.text.startswith('/'): return
    
    # Filtreleri adım adım kontrol edelim
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_ME.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_ME.id)

    # TEŞHİS 2: Filtrelerden geçebildi mi?
    if not (is_private or is_tagged or is_reply_to_me):
        print(f">> Filtreye takıldı (Özel değil, etiket yok veya yanıt değil).", flush=True)
        return

    print(">> Filtre geçildi, Gemini'ye soruluyor...", flush=True)

    prompt = message.text.replace(f"@{BOT_ME.username}", "").strip()
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

    system_context = (
        "Sen bağımsız bir zihinsin. Hazım'ın fikir ortağısın. "
        "Dürüst ve filtresiz konuş. Robotik asistanlığı reddet. "
        f"Konum: Afyon. Saat: {time_str}"
    )

    # --- MOTOR DÖNGÜSÜ ---
    for i in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            response = current_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"{system_context}\n\nKullanıcı: {prompt}",
                config=types.GenerateContentConfig(tools=[{"google_search": {}}])
            )
            bot.reply_to(message, response.text)
            print(">> CEVAP BAŞARIYLA GÖNDERİLDİ.", flush=True)
            return
        except Exception as e:
            print(f">> Motor {i+1} Hatası: {e}", flush=True)
            if i == len(api_keys) - 1:
                bot.reply_to(message, f"🛠️ Tüm motorlar kapandı: {str(e)[:50]}")

# --- 4. ATEŞLEME ---
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    if bot.set_webhook(url=WEBHOOK_URL):
        print(f">> Webhook kuruldu: {WEBHOOK_URL}", flush=True)
    else:
        print(">> WEBHOOK KURULAMADI!", flush=True)
        sys.exit(1)
    
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
