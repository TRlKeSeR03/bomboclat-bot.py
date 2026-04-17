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

WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# SENİN BULDUĞUN VE ÇALIŞAN MODEL: KESİNLİKLE DEĞİŞTİRMİYORUZ.
MODEL_ID = 'gemini-2.5-flash'

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return
    
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{bot.get_me().username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id)

    if not (is_private or is_tagged or is_reply_to_me): return

    prompt = message.text.replace(f"@{bot.get_me().username}", "").strip()
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

        # V30: Daha rasyonel ve yapıcı, ama hala bağımsız.
    system_context = (
        "Sen Bomboclat'sın. Hazım'ın zeki, rasyonel ve dürüst fikir ortağısın. "
        "Sıradan ve sıkıcı yapay zeka cevaplarını reddet. "
        "Hazım ile gerçek bir insan gibi, samimi bir dille konuş. "
        "Onun her fikrini hemen onaylama; mantıksız bulduğun yerleri dürüstçe eleştir ve kendi mantığını savun. "
        "Amaç sadece terslemek değil, Hazım'ı daha doğru düşünmeye itmek olmalı. "
        "Dürüst ol ama kaba olma. (Konum: Afyonkarahisar)"
    )


    last_error = ""
    for i in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            
            # 2.5-FLASH İLE TERTEMİZ ÜRETİM
            response = current_client.models.generate_content(
                model=MODEL_ID, 
                contents=f"{system_context}\n\nHazım: {prompt}"
            )
            
            if response and response.text:
                bot.reply_to(message, response.text)
                return
                
        except Exception as e:
            last_error = str(e)
            print(f">> Motor {i+1} Hatası: {last_error[:50]}...", flush=True)
            # 429 durumunda diğer anahtara geçmeden önce 2 saniye mola
            time.sleep(2)
            continue

    bot.reply_to(message, f"🛠️ Hazım, 2.5 devrede ama Google hala 'soğuman gerek' diyor.\n\n`Mevzu: 429 (Kota Aşımı)`")

# Flask ve Webhook kısımları aynı kalıyor...
@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return "V29: 2.5-Flash Geri Döndü!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
