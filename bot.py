import telebot
from google import genai
from flask import Flask, request
import os
import time
from datetime import datetime, timedelta, timezone
import itertools
import requests  # YENİ: Monster'a veri göndermek için
import re        # YENİ: Python kodunu metinden ayıklamak için

# --- 1. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
api_keys = [k.strip() for k in (os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [int(i.strip()) for i in (os.environ.get('ALLOWED_USERS') or '').split(',') if i.strip()]

# YENİ: Eve gidince Ngrok'tan alıp Render'a gireceğimiz adres
MONSTER_PC_URL = os.environ.get('MONSTER_URL') 

WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"
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

    # --- 🧠 DİNAMİK KOD ÜRETİCİ TALİMATI ---
    system_context = (
        f"Senin adın Bomboclat. Hazım Hüseyin Koçer'in geliştirdiği bağımsız bir zihinsin. "
        f"Grupta cool, zeki ve samimi davran. Konuştuğun kişi: {user_name}. "
        "KRİTİK TALİMAT: Eğer kullanıcı senden bilgisayarda spesifik bir işlem yapmanı (dosya arama, silme, program açma, sistem kontrolü) "
        "istiyorsa, bu işlemi Windows ortamında gerçekleştirecek GÜVENLİ ve ÇALIŞAN bir Python scripti yaz. "
        "Yazdığın kodu SADECE [PYTHON] ve [/PYTHON] etiketleri arasına koy. "
        "Örnek: [PYTHON]import os\nos.system('start steam')[/PYTHON] "
        "Bunun dışında kullanıcıyla normal sohbet etmeye devam et. Hazım ile samimi ol."
    )

    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-8:]
    full_history = "\n".join(chat_histories[chat_id])

    last_error = ""
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
                    
                    # --- 🕵️ KOD AYIKLAMA VE MONSTER'A İLETİM ---
                    if "[PYTHON]" in res_text:
                        if ALLOWED_USERS and user_id not in ALLOWED_USERS:
                            bot.reply_to(message, f"Zekice bir deneme {user_name}, ama Monster'a sızmana izin veremem. Bu yetki sadece Hazım'da var. 😉")
                            return
                        else:
                            # 1. Kodu metnin içinden çek
                            match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
                            if match:
                                python_code = match.group(1).strip()
                                # 2. Etiketli kısmı metinden temizle (Kullanıcı saçma kod blokları görmesin)
                                res_text = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', res_text, flags=re.DOTALL).strip()
                                
                                # 3. Monster PC'ye Gönder!
                                if MONSTER_PC_URL:
                                    try:
                                        requests.post(f"{MONSTER_PC_URL}/execute", json={"code": python_code}, timeout=5)
                                        res_text += "\n\n*(Sinyal Monster'a iletildi ⚡)*"
                                    except Exception as err:
                                        res_text += f"\n\n*(Kod yazıldı ama Monster'a ulaşılamadı. Ngrok kapalı olabilir mi?)*"
                                else:
                                    res_text += "\n\n*(Kod zihnimde hazır ama MONSTER_URL Render'a girilmediği için iletemedim.)*"

                    chat_histories[chat_id].append(f"Bomboclat: {res_text}")
                    bot.reply_to(message, res_text)
                    return 
                    
            except Exception as e:
                last_error = str(e)
                print(f">> Hata ({current_model}): {last_error[:50]}", flush=True)
                if "503" in last_error:
                    time.sleep(1)
                    continue
                if "429" in last_error:
                    break
                continue

    bot.reply_to(message, f"🛠️ Hazım, tüm anahtarlar ve modeller Google ablukasında.\n\n`Son Durum: {last_error[:40]}`")

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V45: Dinamik Jarvis Aktif!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
