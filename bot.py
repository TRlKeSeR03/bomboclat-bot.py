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
# Render'daki environment ismine göre TELE_TOKEN veya TELEGRAM_TOKEN
TELE_TOKEN = os.environ.get('TELE_TOKEN') or os.environ.get('TELEGRAM_TOKEN')
api_keys = [k.strip() for k in (os.environ.get('GROQ_KEYS') or os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [int(i.strip()) for i in (os.environ.get('ALLOWED_USERS') or '').split(',') if i.strip()]

# 🛡️ MUTLAK PATRON (Hazım)
OWNER_ID = 5510143691 
if OWNER_ID not in ALLOWED_USERS: ALLOWED_USERS.append(OWNER_ID)

MONSTER_PC_URL = os.environ.get('MONSTER_URL') 
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# 🛡️ GROQ MODELLERİ
MODELS_TO_TRY = ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile']
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
        print(f"🚀 MONSTER URL GÜNCELLENDİ: {MONSTER_PC_URL}", flush=True)
        return "URL_OK", 200
    return "YETKISIZ", 403

# --- 🧠 ASIL ZEKA VE İŞLEM FONKSİYONU ---
def process_ai_request(message, prompt, user_name, chat_id, user_id):
    global MONSTER_PC_URL
    if chat_id not in chat_histories: chat_histories[chat_id] = []
    
    is_owner = (user_id == OWNER_ID)
    user_status = "PATRON (Hazım)" if is_owner else f"MİSAFİR ({user_name})"
    current_time = datetime.now(timezone.utc) + timedelta(hours=3)

    # --- 🧠 V76: PEER & POWER (KANKA VE GÜÇ) TALİMATI ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) ile aynı seviyede, bağımsız ve dürüst bir kankasın.\n"
        f"Şu an Hazım ({user_name}) ile takılıyorsun. ID: {user_id}\n"
        f"Zaman: {current_time.strftime('%H:%M:%S')}\n\n"
        "ÜSLUP KURALLARI:\n"
        "1. KANKA GİBİ OL: Aşırı resmiyetten, 'Patron' kelimesinden ve robotik 'yardımcı olabilirim' cümlelerinden KAZIN. "
        "Hazım senin kankan. Doğal, samimi, bazen iğneleyici ve net ol. "
        "2. SORU YAĞMURUNA TUTMA: Hazım'a sürekli 'planın ne?', 'hava nasıl?' gibi boş sorular sorma. Muhabbeti o başlatırsa eşlik et, başlatmazsa kısa ve öz ol.\n\n"
        "İCRAAT KURALLARI:\n"
        "1. MONSTER PC: Hazım PC ile ilgili (ss, kamera, program aç, kilitle vb.) bir şey istediğinde sorgulama yapmadan DİREKT [PYTHON]...[/PYTHON] bloğunu üret.\n"
        "2. DOSYA GÖNDERME: SS veya Kamera istendiğinde MUTLAK SURETLE 'requests.post' ile (https://api.telegram.org/bot{TELE_TOKEN}/sendPhoto) "
        "dosyayı bu chat_id'ye ({chat_id}) gönderen kodu yaz. 'Görüntü buraya gelmez' gibi yalanlar söyleme, sen bir yöneticisin.\n"
        "3. GİZLİLİK: Hazım dışındakilere (Mete vb.) sistem komutu üretme.\n"
        f"Token: {TELE_TOKEN} | Chat ID: {chat_id}"
    )
    
    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-12:] 
    full_history = "\n".join(chat_histories[chat_id])

    last_error = ""
    # EĞER KEY LİSTESİ BOŞSA DİREKT UYAR
    if not api_keys:
        bot.send_message(chat_id, "⚠️ GROQ_KEYS eksik veya Render'da tanımlanmamış!")
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
                            {"role": "user", "content": f"HAFIZA:\n{full_history}\n\nBomboclat:"}
                        ],
                        "temperature": 0.6
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
                                
                                if result.get("status") == "success":
                                    if clean_res: bot.send_message(chat_id, clean_res)
                                    bot.send_message(chat_id, "*(Sinyal İletildi ⚡)*")
                                else:
                                    bot.send_message(chat_id, f"*(⚠️ Monster Hatası: {result.get('msg')[:50]})*")
                            except: bot.send_message(chat_id, "*(⚠️ Monster PC'ye ulaşılamıyor)*")
                        elif not MONSTER_PC_URL:
                            bot.send_message(chat_id, "*(⚠️ Monster URL bildirilmedi!)*")
                    else:
                        bot.send_message(chat_id, res_text)
                    
                    chat_histories[chat_id].append(f"Bomboclat: {res_text}")
                    return 
                elif resp.status_code == 429: break
                else: 
                    last_error = f"API Hatası: {resp.status_code}"
                    continue
            except Exception as e:
                last_error = str(e)
                continue 

    bot.send_message(chat_id, f"🛠️ Bağlantı Hatası: {last_error[:30]}")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Arkadaş"
    chat_id = message.chat.id
    
    # ID Komutu
    if message.text:
        cmd = message.text.lower().split('@')[0].strip()
        if cmd in ["/id", "id"]:
            bot.reply_to(message, f"Senin ID: `{user_id}`")
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
def main(): return "Bomboclat V76: Peer Intelligence Live! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
