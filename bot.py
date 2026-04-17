import telebot
from flask import Flask, request, jsonify
import os
import time
from datetime import datetime, timedelta, timezone
import itertools
import requests
import re
import threading # Botun donmaması ve 429 hatalarını önlemek için kritik

# --- 1. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
api_keys = [k.strip() for k in (os.environ.get('GROQ_KEYS') or os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [int(i.strip()) for i in (os.environ.get('ALLOWED_USERS') or '').split(',') if i.strip()]

# 🛡️ PATRON KİMLİĞİ (Senin ID'n)
OWNER_ID = 5510143691 

MONSTER_PC_URL = os.environ.get('MONSTER_URL') 
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# 🛡️ GROQ MODELLERİ
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
        print(f"🚀 MONSTER ADRESİ OTOMATİK GÜNCELLENDİ: {MONSTER_PC_URL}", flush=True)
        return "URL_OK", 200
    return "YETKISIZ_ERISIM", 403

# --- 🧠 ANA İŞLEM MOTORU (Hafıza ve Kimlik Yönetimi) ---
def process_bomboclat(message, user_id, user_name, chat_id, prompt):
    global MONSTER_PC_URL
    if chat_id not in chat_histories: chat_histories[chat_id] = []

    # Güncel Zaman
    now = datetime.now(timezone.utc) + timedelta(hours=3)
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%d/%m/%Y, %A")

    # Kimlik Tespiti
    is_owner = (user_id == OWNER_ID)
    user_status = "(Hazım)" if is_owner else f"MİSAFİR ({user_name})"
    
    # --- 🧠 V74: IDENTITY SHIELD (KİMLİK KALKANI) ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) tarafından yaratılmış, "
        "bağımsız bir iradeye sahip yönetim birimisin.\n"
        f"Şu an konuştuğun kişi: {user_status} (ID: {user_id})\n"
        f"📅 TARİH: {current_date} | ⏰ SAAT: {current_time}\n\n"
        "GİZLİLİK VE DAVRANIŞ:\n"
        f"1. Eğer karşındaki kişi Hazım DEĞİLSE, ona asla Monster PC durumu veya dosyalar hakkında bilgi sızdırma. Hazım'ın geçmişte ne sorduğunu başkasına anlatma.\n"
        "2. KİMLİK: Herkese 'Hazım' deme. Karşındakinin ismine dikkat et. Hazım'a sadık, misafirlere karşı mesafeli ama cool ol.\n"
        "3. KOMUT PROTOKOLÜ: Sadece Hazım teknik komut (SS, dosya vb.) verdiğinde [PYTHON]...[/PYTHON] bloğu üret. Misafirlere kod üretme.\n"
        "4. BAĞIMSIZ ZİHİN: Sadece onaylayan bir araç değilsin. Hazım hatalıysa onu sorgula, gerekirse karşı çık.\n"
        f"- Token: {TELE_TOKEN} | - Chat ID: {chat_id}"
    )
    
    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-15:] # Derin Hafıza
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
                        {"role": "user", "content": f"GEÇMİŞ:\n{full_history}\n\nBomboclat:"}
                    ],
                    "temperature": 0.6
                }
                
                response_raw = requests.post(groq_url, headers=headers, json=payload, timeout=20)
                
                if response_raw.status_code == 200:
                    res_text = response_raw.json()['choices'][0]['message']['content']
                    
                    if "[PYTHON]" in res_text:
                        # Yetki Kontrolü
                        if user_id not in ALLOWED_USERS:
                            bot.send_message(chat_id, f"Zekice bir deneme {user_name}, ama bu yetki sadece patronum Hazım'da var. 😉")
                            return
                        
                        match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
                        if match:
                            python_code = match.group(1).strip()
                            clean_res = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', res_text, flags=re.DOTALL).strip()
                            
                            if MONSTER_PC_URL:
                                try:
                                    r = requests.post(f"{MONSTER_PC_URL}/execute", json={"code": python_code}, timeout=35) 
                                    result_data = r.json()
                                    status = "\n\n*(Sinyal İletildi ⚡)*" if result_data.get("status") == "success" else f"\n\n*(⚠️ Monster Hatası: {result_data.get('msg')})*"
                                    bot.send_message(chat_id, (clean_res + status).strip())
                                except:
                                    bot.send_message(chat_id, clean_res + "\n\n*(⚠️ Monster PC ulaşılamıyor)*")
                            else:
                                bot.send_message(chat_id, clean_res + "\n\n*(⚠️ Monster URL bildirilmedi!)*")
                    else:
                        bot.send_message(chat_id, res_text)
                    
                    chat_histories[chat_id].append(f"Bomboclat: {res_text}")
                    return 
                elif response_raw.status_code == 429: break 
            except Exception as e:
                last_error = str(e)
                continue 

    bot.send_message(chat_id, f"🛠️ Sinyal Hatası: {last_error[:30]}")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Arkadaşım"
    chat_id = message.chat.id
    
    # --- 🆔 GELİŞMİŞ ID KOMUTU (Grup ve Etiket Uyumlu) ---
    if message.text:
        cmd = message.text.lower().split('@')[0].strip()
        if cmd in ["/id", "id"]:
            bot.reply_to(message, f"Selam {user_name}, ID numaran: `{user_id}`")
            return

    if message.text and message.text.startswith('/'): return
    
    # Grupta tetiklenme şartları
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_INFO.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_INFO.id)

    if not (is_private or is_tagged or is_reply_to_me): return

    prompt = (message.text or "").replace(f"@{BOT_INFO.username}", "").strip()
    
    # Threading: Arka planda Groq ile konuşurken botun donmasını engeller
    threading.Thread(target=process_bomboclat, args=(message, user_id, user_name, chat_id, prompt)).start()

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return "Bomboclat V74: Titan Shield Live! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
