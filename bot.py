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
api_keys = [k.strip() for k in (os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [int(i.strip()) for i in (os.environ.get('ALLOWED_USERS') or '').split(',') if i.strip()]

WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# DENECEK MODELLER (Sırasıyla: En yeni ve en stabil olanlar)
MODELS_TO_TRY = ['gemini-2.5-flash', 'gemini-1.5-flash']

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
BOT_INFO = bot.get_me()

chat_histories = {}

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Arkadaşım"
    
    if message.text and message.text.lower() in ["/id", "id"]:
        bot.reply_to(message, f"Senin Telegram ID numaran: `{user_id}`")
        return

    if message.text and message.text.startswith('/'): return
    
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_INFO.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_INFO.id)

    if not (is_private or is_tagged or is_reply_to_me): return

    chat_id = message.chat.id
    prompt = message.text.replace(f"@{BOT_INFO.username}", "").strip()
    
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    system_context = (
        f"Senin adın Bomboclat. Hazım Hüseyin Koçer tarafından geliştirilen rasyonel ve bağımsız bir zihinsin. "
        f"Grup içinde cool, zeki ve samimi bir üye gibi davran. Konuştuğun kişi: {user_name}. "
        "KRİTİK TALİMAT: Eğer kullanıcı senden bilgisayarda bir işlem yapmanı, bir programı açmanı/kapatmanı veya "
        "donanımı kontrol etmeni istiyorsa (Örn: CS2 aç, PC'yi kapat, Monster'ı uyut vb.), cevabına mutlaka '[PC_KOMUTU]' "
        "etiketiyle başla. Eğer sadece bilgisayarlar hakkında sohbet ediyorsa bu etiketi kullanma. "
        f"Hazım ile daha samimi ol. (Konum: Afyon, Saat: {time_str})"
    )

    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-8:]
    full_history = "\n".join(chat_histories[chat_id])

    last_error = ""
    # --- 🛡️ HATA SAVAR DÖNGÜSÜ ---
    # Anahtar sayısı kadar tur at, her anahtarda modelleri dene
    for i in range(len(api_keys) * 2):
        current_client = next(client_iterator)
        
        for current_model in MODELS_TO_TRY:
            try:
                response = current_client.models.generate_content(
                    model=current_model, 
                    contents=f"{system_context}\n\nGEÇMİŞ:\n{full_history}\n\nBomboclat:"
                )
                
                if response and response.text:
                    res_text = response.text
                    
                    if "[PC_KOMUTU]" in res_text:
                        if ALLOWED_USERS and user_id not in ALLOWED_USERS:
                            bot.reply_to(message, f"Zekice bir deneme {user_name}, ama bilgisayara erişim yetkin yok. Bu sadece Hazım'ın yapabileceği bir şey. 😉")
                            return
                        else:
                            res_text = res_text.replace("[PC_KOMUTU]", "").strip()

                    chat_histories[chat_id].append(f"Bomboclat: {res_text}")
                    bot.reply_to(message, res_text)
                    return # Başarılı üretim, fonksiyonu sonlandır.
                    
            except Exception as e:
                last_error = str(e)
                print(f">> Hata ({current_model}): {last_error[:50]}", flush=True)
                
                # 503 varsa 1 saniye bekle ve sonraki model/key kombinasyonuna geç
                if "503" in last_error:
                    time.sleep(1)
                    continue
                # 429 varsa beklemeden sonraki key'e atla
                if "429" in last_error:
                    break
                continue

    bot.reply_to(message, f"🛠️ Hazım, tüm anahtarlar ve modeller Google'ın yoğunluk engeline takıldı.\n\n`Son Durum: {last_error[:40]}`")

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V44: Kesintisiz Jarvis Aktif!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
