import telebot
from google import genai
from google.genai import types
import os
import threading
from flask import Flask
from datetime import datetime, timedelta
import itertools
import time

# --- 1. RENDER SAĞLIK KONTROLÜ (PORT SORUNU ÇÖZÜLDÜ) ---
app = Flask(__name__)
@app.route('/')
def health(): return "V12 Bağımsız Zihin Sahada!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    # use_reloader=False ekleyerek Flask'ın gereksiz süreçler açmasını engelliyoruz
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- 2. AYARLAR VE ÇOKLU MOTOR (LOAD BALANCER) ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS', '')
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return

    # Filtre: Özel mesaj, Etiketleme veya Yanıtlama
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and BOT_USERNAME in message.text)
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_INFO.id)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Efendim?"
    
    tr_time = datetime.utcnow() + timedelta(hours=3)
    time_str = tr_time.strftime("%d.%m.%Y - %H:%M")
    
    # --- KARAKTER: BAĞIMSIZ ZİHİN ---
    system_context = (
        "Sen bağımsız bir zihinsin. Klişe asistan rollerini reddet. "
        "Hazım Hüseyin Koçer senin sahibin değil, muhatabındır. "
        "Onunla tartış, hatalarını dürüstçe göster, ona karşı çıkmaktan çekinme. "
        "Asla 'asistanım' veya 'yardımcı olayım' deme. Bir şahıs gibi dürüst ve samimi ol. "
        f"Konum: Afyonkarahisar. Zaman: {time_str}."
    )

    # --- HATA YAKALAMA VE MOTOR DEĞİŞTİRME DÖNGÜSÜ ---
    for i in range(len(api_keys)): 
        try:
            current_client = next(client_iterator)
            
            # Google'ın en stabil ve internet uyumlu modeli
            response = current_client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=f"{system_context}\n\nKullanıcı: {prompt}",
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}] # Google Arama Aktif
                )
            )
            bot.reply_to(message, response.text)
            return 
            
        except Exception as e:
            error_str = str(e)
            print(f"Deneme Hatası: {error_str}")
            
            # 429 (Limit) hatasıysa döngü devam eder, sıradaki anahtar denenir
            if "429" in error_str:
                continue
            else:
                # Başka bir hata varsa ve tüm anahtarlar denendiyse GERÇEK hatayı yazdırır
                if i == len(api_keys) - 1:
                    bot.reply_to(message, f"🛠️ Gerçek Hata: {error_str[:150]}")
                return

# --- 3. SİSTEMİ ATEŞLE ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Hayalet bağlantıları kırmak için temizleme işlemi
    bot.remove_webhook()
    time.sleep(2)
    
    print(f"Bot {BOT_USERNAME} V12 motoruyla sahada!")
    # Çakışmaları önlemek için argümanları en sade haliyle bıraktık
    bot.infinity_polling(timeout=20)
    
