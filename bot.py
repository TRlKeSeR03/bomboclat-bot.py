import telebot
from flask import Flask, request, jsonify
import os
import time
from datetime import datetime, timedelta, timezone
import itertools
import requests
import re
import threading

# --- 1. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
api_keys = [k.strip() for k in (os.environ.get('GROQ_KEYS') or os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]

# 🛡️ PATRON KİMLİĞİ (Hazım) - BU ID'Yİ TELEGRAMDAN TEYİT ET
OWNER_ID = 5510143691 

# Render'daki listede yoksan bile seni otomatik listeye ekler
ALLOWED_USERS = [int(i.strip()) for i in (os.environ.get('ALLOWED_USERS') or '').split(',') if i.strip()]
if OWNER_ID not in ALLOWED_USERS:
    ALLOWED_USERS.append(OWNER_ID)

MONSTER_PC_URL = os.environ.get('MONSTER_URL') 
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

MODELS_TO_TRY = ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile', 'mixtral-8x7b-32768']
client_iterator = itertools.cycle(api_keys)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
BOT_INFO = bot.get_me()
chat_histories = {}

# --- 🛰️ OTOMATİK URL GÜNCELLEME KAPISI ---
@app.route('/update_url', methods=['POST'])
def update_url():
    global MONSTER_PC_URL
    data = request.json
    if data and data.get('secret') == TELE_TOKEN:
        MONSTER_PC_URL = data.get('url')
        print(f"🚀 MONSTER ADRESİ GÜNCELLENDİ: {MONSTER_PC_URL}", flush=True)
        return "URL_OK", 200
    return "YETKISIZ", 403

# --- 🧠 ANA İŞLEM MOTORU (V73: Titan Fixed) ---
def process_bomboclat(message, user_id, user_name, chat_id, prompt):
    global MONSTER_PC_URL
    if chat_id not in chat_histories: chat_histories[chat_id] = []

    now = datetime.now(timezone.utc) + timedelta(hours=3)
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%d/%m/%Y, %A")

    is_owner = (user_id == OWNER_ID)
    user_status = "MUTLAK PATRON (Hazım)" if is_owner else f"MİSAFİR ({user_name})"
    
    # --- 🧠 V73: KESİN TALİMATLAR ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) tarafından yaratıldın.\n"
        f"Şu an konuştuğun kişi: {user_status} (ID: {user_id})\n"
        f"📍 TARİH/SAAT: {current_date} {current_time}\n\n"
        "GÜVENLİK VE İCRAAT KURALLARI:\n"
        f"1. KİMLİK: Karşındaki kişi Hazım ise (is_owner=True) ona her konuda itaat et. O senin patronundur.\n"
        "2. MİSAFİR YASAĞI: Karşındaki Hazım DEĞİLSE, teknik komut verme, bilgi sızdırma, sadece yüzeysel sohbet et.\n"
        "3. HAYAL GÖRME YASAĞI: 'ss', 'ekran', 'kamera' komutlarında ASLA 'gönderdim' deme. ÖNCE [PYTHON]...[/PYTHON] bloğunu üret. Kod bloğu yoksa işlem yok demektir.\n"
        "4. GEVEZELİK: Komut gelince lafı uzatma, icraata geç.\n"
        f"Token: {TELE_TOKEN} | Chat ID: {chat_id}"
    )
    
    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-15:] 
    full_history = "\n".join(chat_histories[chat_id])

    last_error = ""
    for _ in range(len(api_keys)):
        current_key = next(client_iterator)
        for current_model in MODELS_TO_TRY:
            try:
                groq_url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}
                payload = {
                    "model": current_model,
                    "messages": [
                        {"role": "system", "content": system_context},
                        {"role": "user", "content": f"GEÇMİŞ:\n{full_history}\n\nİcraat (Python Kodu):"}
                    ],
                    "temperature": 0.4 
                }
                
                response_raw = requests.post(groq_url, headers=headers, json=payload, timeout=20)
                
                if response_raw.status_code == 200:
                    res_text = response_raw.json()['choices'][0]['message']['content']
                    ai_reply_to_save = res_text 
                    
                    if "[PYTHON]" in res_text:
                        # --- 🛡️ YETKİ KONTROLÜ (GÜNCELLENDİ) ---
                        if user_id not in ALLOWED_USERS:
                            bot.send_message(chat_id, f"Üzgünüm {user_name}, bu yetki sadece patronum Hazım'da var. 😉 (Senin ID: {user_id})")
                            return
                        
                        match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
                        if match:
                            python_code = match.group(1).strip()
                            clean_res = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', res_text, flags=re.DOTALL).strip()
                            
                            if MONSTER_PC_URL:
                                try:
                                    r = requests.post(f"{MONSTER_PC_URL}/execute", json={"code": python_code}, timeout=40) 
                                    result_data = r.json()
                                    status = "\n\n*(Sinyal İletildi ⚡)*" if result_data.get("status") == "success" else f"\n\n*(⚠️ Monster Hatası: {result_data.get('msg')})*"
                                    bot.send_message(chat_id, (clean_res + status).strip())
                                except: bot.send_message(chat_id, clean_res + "\n\n*(⚠️ Monster PC ulaşılamıyor. Bilgisayar açık mı?)*")
                            else: bot.send_message(chat_id, clean_res + "\n\n*(⚠️ Monster URL bildirilmedi!)*")
                    else:
                        bot.send_message(chat_id, res_text)
                    
                    chat_histories[chat_id].append(f"Bomboclat: {ai_reply_to_save}")
                    return 
                elif response_raw.status_code == 429: break 
                else: continue
            except Exception as e:
                last_error = str(e)
                continue 

    bot.send_message(chat_id, f"🛠️ Sinyal Hatası: {last_error[:30]}")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Arkadaşım"
    chat_id = message.chat.id
    
    # --- 🆔 GELİŞMİŞ ID KOMUTU (Grupta 'id' veya '/id' algılar) ---
    if message.text:
        msg_text = message.text.lower().strip()
        cmd = msg_text.split('@')[0]
        if cmd in ["/id", "id", "/id@bomboclatsweetbot"]:
            bot.reply_to(message, f"Merhaba {user_name}, senin ID numaran: `{user_id}`")
            return

    # Filtreler (Özel mesaj, etiketleme veya yanıt)
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_INFO.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_INFO.id)

    if not (is_private or is_tagged or is_reply_to_me): return

    prompt = (message.text or "").replace(f"@{BOT_INFO.username}", "").strip()
    threading.Thread(target=process_bomboclat, args=(message, user_id, user_name, chat_id, prompt)).start()

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return "Bomboclat V73: Titan Fixed Live! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
