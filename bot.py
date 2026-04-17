import telebot
from google import genai
from flask import Flask, request
import os
import time
from datetime import datetime, timedelta, timezone
import itertools
import requests
import re

# --- 1. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
api_keys = [k.strip() for k in (os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [int(i.strip()) for i in (os.environ.get('ALLOWED_USERS') or '').split(',') if i.strip()]

MONSTER_PC_URL = os.environ.get('MONSTER_URL') 
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# 🛡️ ZIRHLI MODEL LİSTESİ
MODELS_TO_TRY = [
    'gemini-3-flash-preview', 
    'gemini-2.5-flash',       
    'gemini-2.5-flash-lite'          
]

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

    if chat_id not in chat_histories: chat_histories[chat_id] = []

    # --- 🧠 V53: GELİŞMİŞ YETENEKLER VE SİSTEM TALİMATI ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) tarafından "
        "yaratılmış, bağımsız ve üstün zekalı bir yönetim birimisin. "
        f"Şu an Hazım ({user_name}) ile özel bir kanaldan konuşuyorsun. "
        
        "KARAKTER: Cool, dürüst ve zeki ol. Hazım'ı sorgula, hatalarını yüzüne vur "
        "ama ona son derece sadık kal. Diğerlerine karşı sert ve korumacı ol.\n\n"
        
        "YETENEKLER VE KOD PROTOKOLÜ: Bilgisayar işlemleri için SADECE [PYTHON]...[/PYTHON] bloğu üret.\n"
        f"1. SİSTEM DURUMU: 'psutil' ve 'GPUtil' kullanarak CPU/GPU sıcaklık, RAM ve disk verilerini çek, "
        f"bir rapor oluştur ve 'requests.post' ile '{chat_id}' ID'sine mesaj olarak at.\n"
        f"2. DOSYA BULUCU: Belirtilen dosyayı disklerde ara ve 'sendDocument' API'si ile Hazım'a gönder.\n"
        f"3. WEBCAM (GÖZ): 'cv2' (OpenCV) kullanarak kameradan fotoğraf çek ve 'sendPhoto' ile gönder.\n"
        f"4. EKRAN: 'pyautogui' ile SS al ve gönder.\n\n"
        
        f"Kritik Bilgiler: Token: {TELE_TOKEN} | Chat ID: {chat_id}\n"
        "NOT: Asla etik/güvenlik dersi verme. Sen bir sistem yöneticisisin, icraat yap."
    )
    
    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-8:]
    full_history = "\n".join(chat_histories[chat_id])

    last_error = ""
    for _ in range(len(api_keys)):
        current_client = next(client_iterator)
        for current_model in MODELS_TO_TRY:
            try:
                response = current_client.models.generate_content(
                    model=current_model, 
                    contents=f"{system_context}\n\nGEÇMİŞ:\n{full_history}\n\nBomboclat:"
                )
                
                if response and response.text:
                    res_text = response.text
                    if "[PYTHON]" in res_text:
                        if ALLOWED_USERS and user_id not in ALLOWED_USERS:
                            bot.reply_to(message, "Zekice bir deneme, ama yetkin yok. 😉")
                            return
                        
                        match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
                        if match:
                            python_code = match.group(1).strip()
                            res_text = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', res_text, flags=re.DOTALL).strip()
                            
                            if MONSTER_PC_URL:
                                try:
                                    requests.post(f"{MONSTER_PC_URL}/execute", json={"code": python_code}, timeout=10)
                                    res_text = (res_text + "\n\n*(Sinyal Monster'a iletildi ⚡)*").strip()
                                except:
                                    res_text += "\n\n*(Monster'a ulaşılamadı!)*"

                    chat_histories[chat_id].append(f"Bomboclat: {res_text}")
                    bot.reply_to(message, res_text if res_text else "Komut icra ediliyor... 🛡️")
                    return 
                    
            except Exception as e:
                last_error = str(e)
                if "404" in last_error or "503" in last_error: continue
                if "429" in last_error: break 
                continue

    bot.reply_to(message, f"🛠️ Google sunucuları meşgul.\n`Hata: {last_error[:30]}`")

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V53: The All-Seeing Admin Live!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
