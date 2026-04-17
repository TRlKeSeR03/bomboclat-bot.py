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
MODEL_ID = 'gemini-2.5-flash' 

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
BOT_INFO = bot.get_me()

# --- HAFIZA SİSTEMİ ---
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

    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    # --- SİSTEM TALİMATI (Rasyonel & Cool) ---
    system_context = (
        f"Senin adın Bomboclat. Hazım Hüseyin Koçer tarafından geliştirilen bağımsız bir zihinsin. "
        f"Şu an bir gruptasın; cool, zeki ve samimi bir üye gibi davran. Konuştuğun kişi: {user_name}. "
        f"Hazım ile samimi ol, başkalarıyla konuşurken Hazım'ın botu olduğunu hissettir. "
        f"Dürüstlük ve mantık önceliğin olsun. Zamanı (Afyon, {time_str}) sadece sorulursa söyle. "
        "Yapay zeka klişelerinden kaçın, doğal bir insan gibi konuş."
    )

    # Hafıza güncelleme (Hız için 8 mesaj ideal)
    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-8:]
    full_history = "\n".join(chat_histories[chat_id])

    last_error = ""
    num_keys = len(api_keys)

    # Turbo Döngü: Bir anahtar patlarsa saniyesinde diğerine geçer
    for i in range(num_keys):
        try:
            current_client = next(client_iterator)
            
            response = current_client.models.generate_content(
                model=MODEL_ID, 
                contents=f"{system_context}\n\nGEÇMİŞ:\n{full_history}\n\nBomboclat:"
            )
            
            if response and response.text:
                chat_histories[chat_id].append(f"Bomboclat: {response.text}")
                bot.reply_to(message, response.text)
                return
                
        except Exception as e:
            last_error = str(e)
            print(f">> Anahtar {i+1}/{num_keys} Hatası: {last_error[:50]}", flush=True)
            # Hız için bekleme süresini 0.3 saniyeye çektim
            time.sleep(0.3)
            continue

    # HATA MESAJI ARTIK DİNAMİK
    bot.reply_to(message, f"🛠️ Hazım, şu an {num_keys} anahtarın tamamı Google engeline takıldı.\n\n`Son Hata: {last_error[:60]}...` \n(Farklı hesaplardan anahtarların gelmesini bekleyelim.)")

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V39: {len(api_keys)} Anahtar Aktif!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
