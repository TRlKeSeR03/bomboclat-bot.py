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

# Botun kendi ID'sini bir kere alalım ki her mesajda sormayalım
BOT_INFO = bot.get_me()

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return
    
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_INFO.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_INFO.id)

    if not (is_private or is_tagged or is_reply_to_me): return

    # --- KRİTİK EKLEME: user_name burada tanımlanıyor ---
    user_name = message.from_user.first_name or "Arkadaşım"
    prompt = message.text.replace(f"@{BOT_INFO.username}", "").strip()
    
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

    # Bomboclat V31: Rasyonel Grup Üyesi & Bağımsız Zihin
    system_context = (
        f"Senin adın Bomboclat. Hazım tarafından geliştirilen bağımsız ve rasyonel bir zihinsin. "
        f"Şu an Hazım'ın arkadaş grubundasın; bir asistan gibi değil, grubun zeki ve cool bir üyesi gibi konuş. "
        f"Konuştuğun kişinin adı: {user_name}. Eğer Hazım ile konuşuyorsan daha samimi ol, başkalarıyla konuşuyorsan Hazım'ın botu olduğunu hissettir. "
        "Dürüstlük senin için nezaketten daha önemli; mantıksız bulduğun fikirlere rasyonel bir şekilde karşı çık. "
        "Yapay zeka klişelerini reddet, gerçek bir insan gibi samimi ve özgün cevaplar ver. "
        f"(Bilgi: Afyonkarahisar, Saat {time_str})"
    )

    last_error = ""
    for i in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            
            # 2.5-FLASH İLE TERTEMİZ ÜRETİM
            response = current_client.models.generate_content(
                model=MODEL_ID, 
                contents=f"{system_context}\n\n{user_name}: {prompt}"
            )
            
            if response and response.text:
                bot.reply_to(message, response.text)
                return
                
        except Exception as e:
            last_error = str(e)
            print(f">> Motor {i+1} Hatası: {last_error[:50]}...", flush=True)
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
def main(): return "V31: Bomboclat - Rasyonel Grup Modu!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
