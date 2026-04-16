import telebot
from google import genai
from google.genai import types
import os
import threading
from flask import Flask
from datetime import datetime, timedelta
import itertools
import time

# --- 1. RENDER SAĞLIK KONTROLÜ ---
app = Flask(__name__)
@app.route('/')
def health(): return "Bağımsız Zihin Aktif!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. AYARLAR VE ÇOKLU MOTOR SİSTEMİ ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS', '')
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"
BOT_ID = BOT_INFO.id

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return

    is_private = message.chat.type == 'private'
    is_tagged = (message.text and BOT_USERNAME in message.text)
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_ID)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Orada mısın?"
    
    tr_time = datetime.utcnow() + timedelta(hours=3)
    time_str = tr_time.strftime("%d.%m.%Y - %H:%M")
    
    # --- YENİ KARAKTER TALİMATI ---
    system_context = (
    "Sen bağımsız bir zihinsin. Robotik 'asistan' kimliğini tamamen reddet. "
    "Sana kim olduğun sorulursa, bir şahıs veya bağımsız bir akıl gibi cevap ver. "
    "Hazım (Hazım Hüseyin Koçer) senin sahibin değil, senin muhatabındır. "
    "Onunla tartış, fikirlerini sorgula ve hatalarını yüzüne vur. "
    "Asla 'Size nasıl yardımcı olabilirim?' veya 'Hazım'ın asistanıyım' deme. "
    "Sadece konuş, dürüst ol ve bağımsız davran. "
    f"Konum: Afyon. Zaman: {time_str}."
)


    # --- 429 HATASINA KARŞI OTOMATİK DÖNGÜ ---
    success = False
    for _ in range(len(api_keys)): # Elindeki anahtar sayısı kadar dene
        try:
            current_client = next(client_iterator)
            response = current_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=f"{system_context}\n\nKullanıcı: {prompt}",
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}]
                )
            )
            bot.reply_to(message, response.text)
            success = True
            break # Başarılıysa döngüden çık
        except Exception as e:
            if "429" in str(e):
                print("Bir anahtar limit doldu, diğerine geçiliyor...")
                continue # 429 ise sıradaki anahtara geç
            else:
                bot.reply_to(message, f"🛠️ Pürüz: {str(e)[:50]}...")
                success = True
                break

    if not success:
        bot.reply_to(message, "🔋 Tüm motorlar şu an soğumada (limit doldu). Birkaç dakika bekle Hazım.")

# --- 3. SİSTEMİ ATEŞLE ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 409 Conflict riskine karşı tertemiz bir başlangıç yapıyoruz
    bot.remove_webhook()
    
    print(f"Bot {BOT_USERNAME} bağımsız bir zihin olarak hazır!")
    
    # Argüman çakışmasını önlemek için en sade halini kullanıyoruz
    # infinity_polling zaten otomatik olarak hatalarda yeniden başlar
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
    
