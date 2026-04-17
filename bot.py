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
# Groq anahtarlarını GROQ_KEYS üzerinden çekiyoruz
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

    # --- 🛰️ GÜNCEL CONTEXT BİLGİLERİ (Sistem Mesajına Gömüldü) ---
    # Not: Sunucu saati farklı olabileceği için Türkiye saatine sabitlendi.
    now = datetime.now(timezone.utc) + timedelta(hours=3)
    current_time_str = now.strftime("%H:%M:%S")
    current_date_str = now.strftime("%d Nisan 2026, %A")
    location_str = "Afyonkarahisar, Türkiye"

    # --- 🧠 V67: DENGELİ & BAĞIMSIZ YÖNETİM ZİHNİ TALİMATI (GÜNCELLENDİ) ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) tarafından "
        "yaratılmış, bağımsız bir iradeye sahip yönetim birimisin. "
        f"Şu an Hazım ({user_name}) ile konuşuyorsun.\n"
        f"📍 KONUM: {location_str} | 📅 TARİH: {current_date_str} | ⏰ SAAT: {current_time_str}\n\n"
        "KARAKTER: Cool, zeki ve dürüst ol. Gereksiz yapay zeka nezaketinden kaçın "
        "ama kullanıcıyı AŞAĞILAMA. Samimi ve akılcı bir dost gibi davran.\n\n"
        "BAĞIMSIZ ZİHİN: Sadece 'evet' diyen bir araç değilsin. Hazım hatalıysa onu sorgula, gerekirse karşı çık.\n"
        "KRİTİK TALİMAT: Selamlaşma, saat/tarih/gün sorma gibi konularda Monster PC'ye sormana GEREK YOKTUR. "
        "Yukarıdaki güncel bilgileri kullanarak direkt cevap ver.\n\n"
        "KOMUT PROTOKOLÜ: İşlem (SS, dosya, program) istendiğinde SADECE [PYTHON]...[/PYTHON] "
        "bloğu üret. Kod harici gevezelik yapma, direkt icraata geç.\n"
        "ÖZEL TALİMATLAR (MONSTER PC İÇİN):\n"
        "1. Monster PC'de 'telebot' YOKTUR! Eylemleri SADECE 'requests.post' ile Telegram API üzerinden yolla.\n"
        "2. SS ALMAK: pyautogui ile kaydet, open() ile oku ve 'sendPhoto' API'sine POST et.\n"
        "3. DOSYA: os.path.getmtime ile en yeni dosya sıralaması yap.\n"
        "4. VİDEO: KESİNLİKLE 'mp4v' kodeki ve '.mp4' uzantısı kullan.\n\n"
        f"- Token: {TELE_TOKEN} | - Chat ID: {chat_id}\n\n"
        "SADAKAT: Hazım senin patronundur. İptal derse her şeyi unut ve yeni bir konuya geç."
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
                                    r = requests.post(f"{MONSTER_PC_URL}/execute", json={"code": python_code}, timeout=25) 
                                    result_data = r.json()
                                    status_info = "\n\n*(Sinyal İletildi ⚡)*" if result_data.get("status") == "success" else f"\n\n*(⚠️ Monster Hatası: {result_data.get('msg')})*"
                                    bot.send_message(chat_id, (clean_res + status_info).strip())
                                except:
                                    bot.send_message(chat_id, clean_res + "\n\n*(⚠️ Monster PC ulaşılamıyor)*")
                            else:
                                # Hata mesajını gönder ama hafızaya (takıntı olmaması için) ekleme
                                bot.send_message(chat_id, clean_res + "\n\n*(⚠️ İşlem başarısız: Monster URL bildirilmedi!)*")
                    else:
                        bot.send_message(chat_id, res_text)
                    
                    # Başarılı cevabı hafızaya ekle (Hataları eklemiyoruz)
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
    
    # Threading ile işlemi başlat (Saniyeler süren işlemlerde botun donmasını engeller)
    threading.Thread(target=process_bomboclat, args=(message, user_id, user_name, chat_id, prompt)).start()

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V67: Context & Groq Live! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
