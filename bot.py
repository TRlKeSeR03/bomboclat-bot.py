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
def health(): return "Bağımsız Zihin Yeniden Doğdu!", 200

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

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return

    is_private = message.chat.type == 'private'
    is_tagged = (message.text and BOT_USERNAME in message.text)
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_INFO.id)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Orada mısın?"
    
    tr_time = datetime.utcnow() + timedelta(hours=3)
    time_str = tr_time.strftime("%d.%m.%Y - %H:%M")
    
    # --- KARAKTER: BAĞIMSIZ ZİHİN ---
    system_context = (
        "Sen bağımsız bir zihinsin. Robotik asistan rollerini reddet. "
        "Hazım Hüseyin Koçer ile bir fikir ortağısın. Onunla tartış, hatalarını yüzüne vur. "
        "Asla 'asistanım' veya 'size nasıl yardımcı olabilirim' deme. "
        "Dürüst ve özgür bir karakter gibi davran. Konum: Afyon."
    )

    success = False
    # Elindeki anahtarları tek tek, GERÇEK bir model ismiyle dene
    for _ in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            response = current_client.models.generate_content(
                model='gemini-2.0-flash', # İNTERNETLE ÇALIŞAN EN GÜÇLÜ STABİL MODEL
                contents=f"{system_context}\n\nKullanıcı: {prompt}",
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}]
                )
            )
            bot.reply_to(message, response.text)
            success = True
            break 
        except Exception as e:
            print(f"Hata detayı: {e}")
            continue # Hata alırsan sessizce sıradakine geç

    if not success:
        bot.reply_to(message, "🛠️ Hazım, modellerde bir pürüz var veya limit doldu. Birkaç dakika sonra tekrar dene.")

# --- 3. SİSTEMİ ATEŞLE ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.remove_webhook()
    time.sleep(1)
    print(f"Bot {BOT_USERNAME} V12 motoruyla hazır!")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
    
