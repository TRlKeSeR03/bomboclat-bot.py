import telebot
from flask import Flask, request, jsonify
import os
import time
from datetime import datetime, timedelta, timezone
import itertools
import requests
import re
import threading # Yeni: Telegram spammını ve 429/400 hatalarını önlemek için

# --- 1. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
# Groq anahtarlarını GROQ_KEYS üzerinden çekiyoruz
api_keys = [k.strip() for k in (os.environ.get('GROQ_KEYS') or os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [int(i.strip()) for i in (os.environ.get('ALLOWED_USERS') or '').split(',') if i.strip()]

# ⚡ GLOBAL URL: Monster PC açıldığında burayı otomatik güncelleyecek
MONSTER_PC_URL = os.environ.get('MONSTER_URL') 

WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# 🛡️ GÜNCEL GROQ MODEL LİSTESİ (400 Hatasını önlemek için güncellendi)
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
        print(f"🚀 MONSTER ADRESİ GÜNCELLENDİ: {MONSTER_PC_URL}", flush=True)
        return "URL_OK", 200
    return "YETKISIZ_ERISIM", 403

# --- 🧠 ANA İŞLEM MOTORU (Threading ile çalışır) ---
def process_bomboclat(message, user_id, user_name, chat_id, prompt):
    global MONSTER_PC_URL
    if chat_id not in chat_histories: chat_histories[chat_id] = []

    # Şimdiki zamanı koda ekleyelim (Saat sormak için Monster'a gitmesin)
    now = datetime.now(timezone.utc) + timedelta(hours=3)
    current_info = f"Bugün: {now.strftime('%d/%m/%Y %A')} | Saat: {now.strftime('%H:%M:%S')}"

    # --- 🧠 V67: TAKINTI ÖNLEYİCİ SİSTEM TALİMATI ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) tarafından yönetilen admin birimisin.\n"
        f"Kullanıcı: {user_name} | {current_info}\n\n"
        "DAVRANIŞ KURALLARI:\n"
        "1. SOHBET: Selamlaşma, saat/tarih, matematik, sayma gibi işlerde ASLA [PYTHON] kodu üretme. Bunları kendin cevapla.\n"
        "2. İPTAL: Kullanıcı 'iptal' veya 'boşver' derse, önceki tüm hataları/görevleri UNUT, yeni sayfa aç.\n"
        "3. KOMUT: Sadece fiziksel işlerde (SS, dosya, sistem verisi) [PYTHON]...[/PYTHON] bloğu üret.\n"
        "4. MONSTER PC: 'telebot' YOKTUR! requests.post ile Telegram API üzerinden işlem yap.\n"
        f"Token: {TELE_TOKEN} | Chat ID: {chat_id}"
    )
    
    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-8:]
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
                
                resp = requests.post(groq_url, headers=headers, json=payload, timeout=20)
                
                if resp.status_code == 200:
                    res_text = resp.json()['choices'][0]['message']['content']
                    ai_reply_to_save = res_text # Hafızaya sadece temiz cevabı alacağız
                    
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
                                    r = requests.post(f"{MONSTER_PC_URL}/execute", json={"code": python_code}, timeout=25)
                                    result_data = r.json()
                                    status = "\n\n*(Sinyal İletildi ⚡)*" if result_data.get("status") == "success" else f"\n\n*(⚠️ Monster Hatası: {result_data.get('msg')})*"
                                    bot.send_message(chat_id, (clean_res + status).strip())
                                except: bot.send_message(chat_id, clean_res + "\n\n*(⚠️ Monster PC ulaşılamaz)*")
                            else:
                                # KRİTİK: Hata mesajını kullanıcıya gönder ama hafızaya kaydetme!
                                bot.send_message(chat_id, clean_res + "\n\n*(⚠️ İşlem için Monster URL bildirilmedi!)*")
                    else:
                        bot.send_message(chat_id, res_text)
                    
                    # TAKINTI ÖNLEYİCİ: Sadece AI'nın metin cevabını hafızaya al, sistem hatalarını alma.
                    chat_histories[chat_id].append(f"Bomboclat: {ai_reply_to_save}")
                    return 
                
                elif resp.status_code == 429:
                    last_error = "429 Rate Limit"
                    break # Sonraki anahtara geç
                else:
                    last_error = f"{resp.status_code} - {resp.text[:50]}"
                    continue

            except Exception as e:
                last_error = str(e)
                continue 

    bot.send_message(chat_id, f"🛠️ Tüm anahtarlar veya Groq meşgul Hazım.\n`Hata: {last_error[:35]}`")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Hazım"
    chat_id = message.chat.id
    
    if message.text and message.text.lower() in ["/id", "id"]:
        bot.reply_to(message, f"ID: `{user_id}`")
        return

    if message.text and message.text.startswith('/'): return
    if not (message.chat.type == 'private' or f"@{BOT_INFO.username}" in (message.text or "") or (message.reply_to_message and message.reply_to_message.from_user.id == BOT_INFO.id)): return

    prompt = (message.text or "").replace(f"@{BOT_INFO.username}", "").strip()
    
    # 🚀 Threading: Telegram'ın 15 saniye kuralını aşar, 400 ve 429 hatalarını minimize eder.
    threading.Thread(target=process_bomboclat, args=(message, user_id, user_name, chat_id, prompt)).start()

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V67: Groq Migration & Memory Purge Live! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
