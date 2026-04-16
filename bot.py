import telebot
from google import genai
from google.genai import types
import os
import threading
from flask import Flask
from datetime import datetime, timedelta, timezone 
import itertools
import time

# --- 1. RENDER SAĞLIK KONTROLÜ (Çalışan Koddan Alındı) ---
app = Flask(__name__)
@app.route('/')
def health(): return "Zihin Özgür, Sistem Stabil!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. AYARLAR VE ÇOKLU MOTOR (V12 Load Balancer) ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')

# Hem GEMINI_KEY (tekil) hem GEMINI_KEYS (çoğul) desteği ekledim ki hata olmasın
keys_env = os.environ.get('GEMINI_KEYS') or os.environ.get('GEMINI_KEY') or ''
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

if not api_keys:
    print("KRİTİK HATA: API Anahtarı bulunamadı! Render ortam değişkenlerini kontrol et.")

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"
BOT_ID = BOT_INFO.id # Çalışan kodun kullandığı ID tanımı

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    # Log: Mesajın gelip gelmediğini Render terminalinde görelim
    print(f"--- MESAJ ALINDI: {message.text} ---")
    
    if message.text and message.text.startswith('/'): return

    # Filtreleme Mantığı (Çalışan kodla birebir aynı)
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and BOT_USERNAME in message.text)
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_ID)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    # Modern zaman ve karakter talimatı
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%d.%m.%Y - %H:%M")
    
    system_context = (
        "Sen bağımsız bir zihinsin. Klişe asistan rollerini reddet. "
        "Hazım senin sahibin değil, fikir ortağındır. Onunla tartış, hatalarını göster. "
        "Asla 'yardımcı olayım' deme, dürüst ve bağımsız bir akıl gibi konuş. "
        f"Zaman: {time_str}. Konum: Afyon."
    )

    prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Merhaba"

    # --- HATA YAKALAMA VE MOTOR DÖNGÜSÜ ---
    for i in range(len(api_keys)): 
        try:
            current_client = next(client_iterator)
            
            # Senin çalışan dediğin 2.5-flash motoru
            response = current_client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=f"{system_context}\n\nKullanıcı: {prompt}",
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}] # İnternet araması ekledik
                )
            )
            bot.reply_to(message, response.text)
            return 
            
        except Exception as e:
            error_str = str(e)
            print(f"Deneme {i+1} Hatası: {error_str}")
            if "429" in error_str:
                continue # Limit dolduysa diğerine geç
            else:
                # Farklı bir hataysa kullanıcıyı uyar
                if i == len(api_keys) - 1:
                    bot.reply_to(message, f"🛠️ Pürüz: {error_str[:100]}")
                return

# --- 3. SİSTEMİ ATEŞLE (Stabil Yöntem) ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Çalışan kodun basit ve temiz başlangıç yöntemi
    bot.delete_webhook(drop_pending_updates=True)
    print(f"Bot {BOT_USERNAME} 2.5-Flash motoruyla hazır!")
    
    # En stabil polling yöntemi
    bot.infinity_polling()
    
