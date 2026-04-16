import telebot
from google import genai
from google.genai import types
import os
import threading
from flask import Flask
from datetime import datetime, timedelta, timezone 
import itertools
import time
import sys

# --- 1. RENDER SAĞLIK KONTROLÜ ---
app = Flask(__name__)
@app.route('/')
def health(): return "Sistem Stabil!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    print(f">> Flask sunucusu {port} portunda baslatiliyor...", flush=True)
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- 2. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS') or os.environ.get('GEMINI_KEY') or ''
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

print(f">> {len(api_keys)} adet Gemini anahtari yuklendi.", flush=True)

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

# Bot objesini olustur (Baglantiyi henuz acma)
bot = telebot.TeleBot(TELE_TOKEN)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    # Mesaj geldigi an Render'da gormeliyiz
    print(f"!!! YENİ MESAJ: {message.text} (Kimden: {message.from_user.id})", flush=True)
    
    if message.text and message.text.startswith('/'): return

    # Filtreleme (Senin calisan kodundaki mantik)
    try:
        # BOT_INFO'yu burada cekiyoruz ki baslangicta takilmasin
        me = bot.get_me()
        is_private = message.chat.type == 'private'
        is_tagged = (message.text and f"@{me.username}" in message.text)
        is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == me.id)

        if not (is_private or is_tagged or is_reply_to_me):
            return

        prompt = message.text.replace(f"@{me.username}", "").strip()
        tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
        time_str = tr_time.strftime("%d.%m.%Y - %H:%M")
        
        system_context = (
            "Sen bağımsız bir zihinsin. Hazım senin sahibin değil, fikir ortağındır. "
            "Robotik asistan rollerini reddet, dürüst ve bağımsız konuş. "
            f"Afyon / {time_str}"
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
                print(f">> Cevap gonderildi.", flush=True)
                return 
            except Exception as e:
                if "429" in str(e): continue
                bot.reply_to(message, f"🛠️ Pürüz: {str(e)[:50]}")
                return
    except Exception as e:
        print(f"HATA: {e}", flush=True)

# --- 3. SİSTEMİ ATEŞLE (Sıralı ve Güvenli) ---
if __name__ == "__main__":
    print(">> Bot operasyonu basliyor...", flush=True)
    
    # 1. Flask'i ayri kanalda baslat
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. Bekle ve temizlik yap
    time.sleep(2)
    try:
        print(">> Telegram webhook temizleniyor...", flush=True)
        bot.delete_webhook(drop_pending_updates=True)
        
        # Bot ismini kontrol et
        me = bot.get_me()
        print(f">> Bot @{me.username} (ID: {me.id}) mermer gibi hazir!", flush=True)
    except Exception as e:
        print(f">> KRITIK BAGLANTI HATASI: {e}", flush=True)
        sys.exit(1)

    # 3. Polling baslat
    print(">> Mesaj dinleme (Polling) basladi...", flush=True)
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
    
