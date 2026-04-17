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
MODEL_ID = 'gemini-2.5-flash' # Senin keşfettiğin canavar

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
BOT_INFO = bot.get_me()

# --- HAFIZA SİSTEMİ (Chat başına 8 mesaj hatırlar) ---
chat_histories = {}

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return
    
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_INFO.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_INFO.id)

    if not (is_private or is_tagged or is_reply_to_me): return

    chat_id = message.chat.id
    user_name = message.from_user.first_name or "Arkadaşım"
    prompt = message.text.replace(f"@{BOT_INFO.username}", "").strip()
    
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

    # Hafıza başlatma
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    # --- SİSTEM TALİMATI (Grup Dostu ve Rasyonel) ---
    system_context = (
        f"Senin adın Bomboclat. Hazım Hüseyin Koçer tarafından geliştirilen, rasyonel ve bağımsız bir zihinsin. "
        f"Grubun zeki, samimi ve cool bir üyesi gibi davran. Konuştuğun kişi: {user_name}. "
        f"Hazım ile konuşurken samimi ol; başkalarıyla konuşurken Hazım'ın botu olduğunu hissettir. "
        "Dürüst ve mantıklı ol. Zaman bilgisini (Afyon, {time_str}) sadece sorulursa kullan. "
        "Sohbet geçmişine bakarak doğal bir akış sağla."
    )

    # Mesajı hafızaya ekle ve son 8 mesajı tut (Hız için 8 idealdir)
    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-8:]
    full_history = "\n".join(chat_histories[chat_id])

    last_error = ""
    # Anahtar sayısı kadar deneme yap (Eğer biri 429 verirse saniyesinde diğerine geçer)
    for i in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            
            response = current_client.models.generate_content(
                model=MODEL_ID, 
                contents=f"{system_context}\n\nGEÇMİŞ:\n{full_history}\n\nBomboclat:"
            )
            
            if response and response.text:
                # Botun cevabını hafızaya ekle
                chat_histories[chat_id].append(f"Bomboclat: {response.text}")
                bot.reply_to(message, response.text)
                return
                
        except Exception as e:
            last_error = str(e)
            print(f">> Motor {i+1} Hatası: {last_error[:40]}... Hemen diğerine geçiliyor.", flush=True)
            # Bekleme süresini 0.5 saniyeye düşürdüm (Hız için)
            time.sleep(0.5)
            continue

    bot.reply_to(message, f"🛠️ Hazım, tüm anahtarlar (3/3) Google ablukasında. 1-2 dakika nefes alalım.")

# Flask ve Webhook (Değişmedi)
@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return "V35: Bomboclat - Turbo Mod Aktif!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
