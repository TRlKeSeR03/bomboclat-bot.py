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

# 🎯 BULUT YEDEK MODELLERİ
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
    
    # Kişilik ve Sistem Talimatı
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) tarafından yaratılmış bağımsız bir zihinsin.\n"
        f"Konuştuğun kişi: {user_name} | Zaman: {now.strftime('%H:%M:%S')}\n\n"
        "ÜSLUP: Hazım senin yaratıcındır. Ona karşı dürüst, samimi ve akılcı bir dost ol. "
        "Robotik 'Efendim' veya laubali 'Kanka' kelimelerini kullanma. Bağımsız bir ortak gibi davran.\n"
        "TEKNİK: İşlemler için SADECE [PYTHON]...[/PYTHON] bloğu üret.\n"
        f"Token: {TELE_TOKEN} | Chat ID: {chat_id}"
    )
    
    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-12:] 
    full_history = "\n".join(chat_histories[chat_id])

    res_text = ""
    brain_source = ""

    # 📡 1. ADIM: MONSTER PC KONTROLÜ (Yerel AI)
    monster_online = False
    if MONSTER_PC_URL:
        try:
            # Monster tarafında /status kontrolü
            check = requests.get(f"{MONSTER_PC_URL}/status", timeout=2)
            if check.status_code == 200:
                monster_online = True
                # Monster'daki Yerel LLM'e (Ollama vb.) isteği gönder
                monster_resp = requests.post(
                    f"{MONSTER_PC_URL}/generate", 
                    json={"prompt": prompt, "system": system_context, "history": full_history},
                    timeout=45
                )
                if monster_resp.status_code == 200:
                    res_text = monster_resp.json().get("response", "")
                    brain_source = "*(⚡ Monster RTX 5050)*"
        except:
            monster_online = False

    # ☁️ 2. ADIM: BULUT YEDEKLEME (Eğer Monster kapalıysa veya hata verdiyse)
    if not res_text:
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
                        brain_source = "*(☁️ Groq Cloud)*"
                        break
                    elif resp.status_code == 429: break
                except: continue
            if res_text: break

    # 🛠️ 3. ADIM: İCRAAT VE YANIT
    if res_text:
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
                    status_msg = f"\n\n{brain_source} | *(Sinyal İletildi ⚡)*" if result.get("status") == "success" else f"\n\n{brain_source} | *(⚠️ Hata: {result.get('msg')[:50]})*"
                    bot.send_message(chat_id, (clean_res + status_msg).strip() if clean_res or status_msg else "İşlem yapıldı.")
                except: bot.send_message(chat_id, f"{res_text}\n\n{brain_source}\n*(⚠️ Monster ulaşılamadı)*")
            else:
                bot.send_message(chat_id, f"{res_text}\n\n{brain_source}\n*(⚠️ Monster URL eksik)*")
        else:
            bot.send_message(chat_id, f"{res_text}\n\n{brain_source}")
        
        chat_histories[chat_id].append(f"Bomboclat: {res_text}")
    else:
        bot.send_message(chat_id, "🛠️ İki beyin de şu an cevap vermiyor Hazım. Sinyalleri kontrol et.")

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
def main(): return "Bomboclat V84: Hybrid Titan Live! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
