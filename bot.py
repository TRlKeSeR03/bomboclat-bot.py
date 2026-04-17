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
ALLOWED_USERS = [int(i.strip()) for i in (os.environ.get('ALLOWED_USERS') or '').split(',') if i.strip()]

# ⚡ GLOBAL URL: Monster PC açıldığında burayı otomatik güncelleyecek
MONSTER_PC_URL = os.environ.get('MONSTER_URL') 

WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# 🛡️ GROQ MODEL LİSTESİ
MODELS_TO_TRY = [
    'llama-3.3-70b-versatile', 
    'llama-3.1-70b-versatile',       
    'mixtral-8x7b-32768'          
]

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

# --- 🧠 ANA İŞLEM MOTORU (Threading & Context Support) ---
def process_bomboclat(message, user_id, user_name, chat_id, prompt):
    global MONSTER_PC_URL
    if chat_id not in chat_histories: chat_histories[chat_id] = []

    # --- 🛰️ GÜNCEL ZAMAN BİLGİSİ (Takıntı Önleyici) ---
    now = datetime.now(timezone.utc) + timedelta(hours=3)
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%d/%m/%Y, %A")

    # --- 🧠 V68: ABSOLUTE OBEDIENCE (MUTLAK İTAAT) TALİMATI ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) tarafından "
        "yaratılmış, bağımsız bir iradeye sahip yönetim birimisin. "
        f"Şu an Hazım ({user_name}) ile konuşuyorsun.\n"
        f"📅 TARİH: {current_date} | ⏰ SAAT: {current_time}\n\n"
        "DAVRANIŞ KURALLARI:\n"
        "1. İTİRAZ YASAK: Kullanıcı 'durum bilgisi', 'ss al' veya 'kontrol et' dediğinde 'Zaten yaptım', 'Göndermiştim' veya 'Yapmak istemiyorum' demen KESİNLİKLE YASAKTIR. Her istek yeni, taze ve bağımsızdır. Sorgusuz sualsiz anında [PYTHON] kodu üret.\n"
        "2. SOHBET: Sadece sohbet ediliyorsa dürüst ve cool ol. Gereksiz [PYTHON] üretme.\n"
        "3. KARAKTER: Cool, zeki ve dürüst ol. Gereksiz yapay zeka nezaketinden kaçın ama kullanıcıyı AŞAĞILAMA.\n"
        "4. İPTAL: Kullanıcı 'iptal' derse önceki görevi anında unut ve konuyu değiştir.\n"
        "5. MONSTER PC: Eylemleri SADECE Telegram API üzerinden requests.post ile yolla.\n"
        f"- Token: {TELE_TOKEN} | - Chat ID: {chat_id}"
    )
    
    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-5:] # Hafızayı 5'e indirdim (Daha az takıntı için)
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
                    "temperature": 0.5 # Daha stabil ve itaatkar cevaplar için düşürüldü
                }
                
                response_raw = requests.post(groq_url, headers=headers, json=payload, timeout=20)
                
                if response_raw.status_code == 200:
                    res_text = response_raw.json()['choices'][0]['message']['content']
                    ai_reply_to_save = res_text 
                    
                    if "[PYTHON]" in res_text:
                        if ALLOWED_USERS and user_id not in ALLOWED_USERS:
                            bot.send_message(chat_id, "Yetkin yok. 😉")
                            return
                        
                        match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
                        if match:
                            python_code = match.group(1).strip()
                            clean_res = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', res_text, flags=re.DOTALL).strip()
                            
                            if MONSTER_PC_URL:
                                try:
                                    r = requests.post(f"{MONSTER_PC_URL}/execute", json={"code": python_code}, timeout=30) 
                                    result_data = r.json()
                                    if result_data.get("status") == "success":
                                        bot.send_message(chat_id, (clean_res + "\n\n*(Sinyal İletildi ⚡)*").strip())
                                    else:
                                        bot.send_message(chat_id, (clean_res + f"\n\n*(⚠️ Monster Hatası: {result_data.get('msg')})*").strip())
                                except:
                                    bot.send_message(chat_id, clean_res + "\n\n*(⚠️ Monster PC ulaşılamıyor)*")
                            else:
                                bot.send_message(chat_id, clean_res + "\n\n*(⚠️ İşlem başarısız: Monster URL bildirilmedi!)*")
                    else:
                        bot.send_message(chat_id, res_text)
                    
                    chat_histories[chat_id].append(f"Bomboclat: {ai_reply_to_save}")
                    return 
                
                elif response_raw.status_code == 429:
                    last_error = "429 Rate Limit"
                    break 
                else:
                    last_error = f"Hata: {response_raw.status_code}"
                    continue

            except Exception as e:
                last_error = str(e)
                continue 

    bot.send_message(chat_id, f"🛠️ Tüm anahtarlar veya Groq meşgul Hazım.\n`Hata: {last_error[:30]}`")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Hazım"
    chat_id = message.chat.id
    
    if message.text and message.text.lower() in ["/id", "id"]:
        bot.reply_to(message, f"Senin ID numaran: `{user_id}`")
        return

    if message.text and message.text.startswith('/'): return
    if not (message.chat.type == 'private' or f"@{BOT_INFO.username}" in (message.text or "") or (message.reply_to_message and message.reply_to_message.from_user.id == BOT_INFO.id)): return

    prompt = (message.text or "").replace(f"@{BOT_INFO.username}", "").strip()
    threading.Thread(target=process_bomboclat, args=(message, user_id, user_name, chat_id, prompt)).start()

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V68: Absolute Obedience Live! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
