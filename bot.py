import telebot
from flask import Flask, request, jsonify
import os
import time
from datetime import datetime, timedelta, timezone
import itertools
import requests
import re
import threading # Spam engelleme için eklendi

# --- 1. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
# Groq anahtarlarını GEMINI_KEYS değişkeninden veya yeni GROQ_KEYS değişkeninden çekebilirsin
api_keys = [k.strip() for k in (os.environ.get('GROQ_KEYS') or os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [int(i.strip()) for i in (os.environ.get('ALLOWED_USERS') or '').split(',') if i.strip()]

# ⚡ GLOBAL URL: Monster PC açıldığında burayı otomatik güncelleyecek
MONSTER_PC_URL = os.environ.get('MONSTER_URL') 

WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# 🛡️ GROQ MODEL LİSTESİ (En stabil ve hızlılar)
MODELS_TO_TRY = [
    'llama-3.3-70b-versatile',
    'llama-3.1-70b-versatile',
    'mixtral-8x7b-32768'
]

# Anahtar döngüsü aynen korunuyor
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

# --- 🧠 GROQ API YARDIMCISI ---
def call_groq(api_key, model, system_msg, user_msg):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.7
    }
    response = requests.post(url, headers=headers, json=payload, timeout=20)
    return response

# --- ⚙️ ANA İŞLEM MOTORU ---
def process_request(message, user_id, user_name, chat_id, prompt):
    global MONSTER_PC_URL
    
    if chat_id not in chat_histories: chat_histories[chat_id] = []

    # --- 🧠 V65: BOMBOCLAT ZİHNİ TALİMATI (AYNEN KORUNDU) ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) tarafından "
        "yaratılmış, bağımsız bir iradeye sahip yönetim birimisin. "
        f"Şu an Hazım ({user_name}) ile konuşuyorsun. "
        "KARAKTER: Cool, zeki ve dürüst ol. Yapay zeka nezaketinden kaçın ama kullanıcıyı AŞAĞILAMA.\n\n"
        "BAĞIMSIZ ZİHİN: Sadece 'evet' diyen bir araç değilsin. Hazım hatalıysa onu sorgula, karşı çık.\n"
        "KOMUT PROTOKOLÜ: İşlem istendiğinde SADECE [PYTHON]...[/PYTHON] bloğu üret.\n"
        "MONSTER PC: 'telebot' YOKTUR! requests.post ile Telegram API üzerinden (sendPhoto vb.) yolla.\n"
        f"Token: {TELE_TOKEN} | Chat ID: {chat_id}"
    )
    
    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-8:]
    full_history = "\n".join(chat_histories[chat_id])

    last_error = ""
    # 🔄 API Anahtarları Arasında Döngü (Groq Versiyonu)
    for _ in range(len(api_keys)):
        current_key = next(client_iterator)
        
        for current_model in MODELS_TO_TRY:
            try:
                resp = call_groq(current_key, current_model, system_context, f"GEÇMİŞ:\n{full_history}\n\nBomboclat:")
                
                if resp.status_code == 200:
                    res_text = resp.json()['choices'][0]['message']['content']
                    
                    if "[PYTHON]" in res_text:
                        if ALLOWED_USERS and user_id not in ALLOWED_USERS:
                            bot.send_message(chat_id, "Zekice bir deneme, ama yetkin yok. 😉")
                            return
                        
                        match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
                        if match:
                            python_code = match.group(1).strip()
                            clean_res = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', res_text, flags=re.DOTALL).strip()
                            
                            if MONSTER_PC_URL:
                                try:
                                    r = requests.post(f"{MONSTER_PC_URL}/execute", json={"code": python_code}, timeout=25)
                                    result_data = r.json()
                                    if result_data.get("status") == "error":
                                        clean_res += f"\n\n*(⚠️ Monster Hatası: {result_data.get('msg')})*"
                                    else:
                                        clean_res += "\n\n*(Sinyal İletildi ⚡)*"
                                except: clean_res += "\n\n*(⚠️ Monster'a ulaşılamadı)*"
                            else: clean_res += "\n\n*(Hata: URL bildirilmedi)*"
                            res_text = clean_res

                    chat_histories[chat_id].append(f"Bomboclat: {res_text}")
                    bot.send_message(chat_id, res_text if res_text else "Komut icra ediliyor...")
                    return 
                
                elif resp.status_code == 429:
                    last_error = "429 Rate Limit"
                    break # Bu anahtar bitti, sonrakine geç
                
            except Exception as e:
                last_error = str(e)
                continue

    bot.send_message(chat_id, f"🛠️ Tüm Groq anahtarları meşgul Hazım.\n`Hata: {last_error[:30]}`")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Arkadaşım"
    chat_id = message.chat.id
    
    if message.text and message.text.lower() in ["/id", "id"]:
        bot.reply_to(message, f"ID numaran: `{user_id}`")
        return

    if message.text and message.text.startswith('/'): return
    if not (message.chat.type == 'private' or f"@{BOT_INFO.username}" in (message.text or "") or (message.reply_to_message and message.reply_to_message.from_user.id == BOT_INFO.id)): return

    prompt = (message.text or "").replace(f"@{BOT_INFO.username}", "").strip()
    
    # İşlemi arka planda başlat (Anti-Spam)
    threading.Thread(target=process_request, args=(message, user_id, user_name, chat_id, prompt)).start()

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V65: Groq Warp Drive Live! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
