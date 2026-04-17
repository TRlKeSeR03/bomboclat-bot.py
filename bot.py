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
TELE_TOKEN = os.environ.get('TELE_TOKEN') or os.environ.get('TELEGRAM_TOKEN')
api_keys = [k.strip() for k in (os.environ.get('GROQ_KEYS') or os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [int(i.strip()) for i in (os.environ.get('ALLOWED_USERS') or '').split(',') if i.strip()]

# 🛡️ MUTLAK YETKİLİ (Hazım)
OWNER_ID = 5510143691 
if OWNER_ID not in ALLOWED_USERS: 
    ALLOWED_USERS.append(OWNER_ID)

MONSTER_PC_URL = os.environ.get('MONSTER_URL') 
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# 🎯 SENİN İSTEDİĞİN MODEL ODAKLI LİSTE
MODELS_TO_TRY = ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile']
client_iterator = itertools.cycle(api_keys)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
BOT_INFO = bot.get_me()
chat_histories = {}

# --- 🛰️ OTOMATİK URL GÜNCELLEME ---
@app.route('/update_url', methods=['POST'])
def update_url():
    global MONSTER_PC_URL
    data = request.json
    if data and data.get('secret') == TELE_TOKEN:
        MONSTER_PC_URL = data.get('url')
        print(f"🚀 MONSTER URL GÜNCELLENDİ: {MONSTER_PC_URL}", flush=True)
        return "URL_OK", 200
    return "YETKISIZ", 403

# --- 🧠 ASIL ZEKA VE İŞLEM FONKSİYONU ---
def process_ai_request(message, prompt, user_name, chat_id, user_id):
    global MONSTER_PC_URL
    if chat_id not in chat_histories: chat_histories[chat_id] = []
    
    is_owner = (user_id == OWNER_ID)
    now = datetime.now(timezone.utc) + timedelta(hours=3)

    # --- 🧠 V80: PEER HARMONY TALİMATI ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) tarafından yaratılmış bağımsız bir zihinsin.\n"
        f"Şu an konuştuğun kişi: {user_name} (ID: {user_id}) | Saat: {now.strftime('%H:%M:%S')}\n\n"
        "ÜSLUP VE KARAKTER:\n"
        "1. DOSTÇA VE AKILCI OL: Hazım senin yaratıcındır. Ona karşı dürüst, samimi ve akılcı bir dost tonu kullan. "
        "Aşırı resmiyetten veya aşırı laubalilikten kaçın. Doğal ve cool ol.\n"
        "2. ÖZ VE NET: Gereksiz nezaket yapma. Konu neyse ona odaklan.\n"
        "3. BAĞIMSIZLIK: Bir köle gibi davranma; Hazım hatalıysa onu sorgula.\n\n"
        "🔥 TEKNİK İCRAAT (ZORUNLU):\n"
        "Hazım 'ss', 'kamera' veya 'dosya' istediğinde hiç lafı uzatmadan [PYTHON]...[/PYTHON] bloğu üret.\n"
        "DOSYA GÖNDERME KODU TASLAĞI:\n"
        "```python\nimport requests; \n# Dosya oluşturma kodun...\n"
        f"with open('dosya.png', 'rb') as f: \n    requests.post('[https://api.telegram.org/bot](https://api.telegram.org/bot){TELE_TOKEN}/sendPhoto', data={{'chat_id': '{chat_id}'}}, files={{'photo': f}})\n```\n"
        f"Token: {TELE_TOKEN} | Chat ID: {chat_id}"
    )
    
    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-12:] 
    full_history = "\n".join(chat_histories[chat_id])

    last_error = "Bağlantı Kurulamadı"
    
    if not api_keys:
        bot.send_message(chat_id, "⚠️ Render'da API anahtarları tanımlanmamış!")
        return

    for _ in range(len(api_keys)):
        current_key = next(client_iterator)
        for current_model in MODELS_TO_TRY:
            try:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"},
                    json={
                        "model": current_model,
                        "messages": [
                            {"role": "system", "content": system_context},
                            {"role": "user", "content": f"GEÇMİŞ:\n{full_history}\n\nBomboclat:"}
                        ],
                        "temperature": 0.5 
                    },
                    timeout=20
                )
                
                if resp.status_code == 200:
                    res_text = resp.json()['choices'][0]['message']['content']
                    
                    if "[PYTHON]" in res_text:
                        if user_id not in ALLOWED_USERS:
                            bot.send_message(chat_id, f"Yetkin yok {user_name}. 😉")
                            return
                        
                        match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
                        if match and MONSTER_PC_URL:
                            try:
                                r = requests.post(f"{MONSTER_PC_URL}/execute", json={"code": match.group(1).strip()}, timeout=40)
                                result = r.json()
                                clean_res = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', res_text, flags=re.DOTALL).strip()
                                
                                status_msg = "\n\n*(Sinyal İletildi ⚡)*" if result.get("status") == "success" else f"\n\n*(⚠️ Hata: {result.get('msg')[:50]})*"
                                bot.send_message(chat_id, (clean_res + status_msg).strip() if clean_res or status_msg else "İşlem yapıldı.")
                            except: bot.send_message(chat_id, "*(⚠️ Monster PC'ye ulaşılamıyor)*")
                        elif not MONSTER_PC_URL:
                            bot.send_message(chat_id, "*(⚠️ Monster adresi henüz gelmedi)*")
                    else:
                        bot.send_message(chat_id, res_text)
                    
                    chat_histories[chat_id].append(f"Bomboclat: {res_text}")
                    return 
                elif resp.status_code == 429:
                    last_error = "Groq Hız Limiti (429)"
                    break # Rate limit, sonraki anahtara geç
            except Exception as e:
                last_error = f"Sistem Hatası: {str(e)[:30]}"
                continue 

    bot.send_message(chat_id, f"🛠️ {last_error}")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Hazım"
    chat_id = message.chat.id
    
    if message.text:
        cmd = message.text.lower().split('@')[0].strip()
        if cmd in ["/id", "id"]:
            bot.reply_to(message, f"ID: `{user_id}`")
            return

    if message.text and message.text.startswith('/'): return
    
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_INFO.username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == BOT_INFO.id)

    if not (is_private or is_tagged or is_reply_to_me): return

    prompt = (message.text or "").replace(f"@{BOT_INFO.username}", "").strip()
    threading.Thread(target=process_ai_request, args=(message, prompt, user_name, chat_id, user_id)).start()

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return "Bomboclat V80: Versatile Focus Live! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
