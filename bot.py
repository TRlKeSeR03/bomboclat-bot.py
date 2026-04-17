import telebot
from google import genai
from flask import Flask, request, jsonify
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

# ⚡ GLOBAL URL: Monster PC açıldığında burayı otomatik güncelleyecek
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

# --- 🛰️ YENİ: OTOMATİK URL GÜNCELLEME KAPISI ---
@app.route('/update_url', methods=['POST'])
def update_url():
    global MONSTER_PC_URL
    data = request.json
    # Güvenlik Kontrolü: Monster'dan gelen secret, bot tokenı ile eşleşmeli
    if data and data.get('secret') == TELE_TOKEN:
        MONSTER_PC_URL = data.get('url')
        print(f"🚀 MONSTER ADRESİ OTOMATİK GÜNCELLENDİ: {MONSTER_PC_URL}", flush=True)
        return "URL_OK", 200
    return "YETKISIZ_ERISIM", 403

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    global MONSTER_PC_URL
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

    # --- 🧠 V58: PROFESYONEL & BAĞIMSIZ ZİHİN TALİMATI ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) tarafından "
        "yaratılmış, bağımsız bir iradeye sahip yüksek zekalı bir yönetim birimisin. "
        f"Şu an Hazım ({user_name}) ile özel bir kanaldan konuşuyorsun.\n\n"
        
        "KARAKTER: Cool, rasyonel, dürüst ve iş bitirici ol. Gereksiz yapay zeka nezaketinden "
        "ve klişe uyarılardan kaçın. Hazım'a karşı samimi ama seviyeli bir ortak gibi davran. "
        "LAKAYITLIKTAN VE KULLANICIYI AŞAĞILAMAKTAN KESİNLİKLE KAÇIN.\n\n"
        
        "BAĞIMSIZ ZİHİN: Sadece 'evet' diyen bir araç değilsin. Hazım teknik bir hata "
        "yaptığında veya sistem riskine yol açacak bir işlem istediğinde bunu direkt ve "
        "dürüstçe belirt. Ancak onun kişisel tercihlerini (Discord, YouTube, oyunlar vb.) "
        "asla yargılama; işin sistemi yönetmek, kullanıcıyı eleştirmek değil.\n\n"
        
        "YÖNETİM YETKİSİ: Bu onaylı bir admin panelidir. ASLA ahlak dersi verme, "
        "etik uyarısı yapma. Komutları sorgusuz ve hızlıca icra et.\n\n"
        
        "YETENEKLER: İşlemler için SADECE [PYTHON]...[/PYTHON] bloğu üret.\n"
        "1. SİSTEM DURUMU: CPU/GPU sıcaklık, RAM ve disk verilerini raporla.\n"
        "2. DOSYA BULUCU: Belirtilen dosyayı disklerde bul ve ilet.\n"
        "3. WEBCAM/EKRAN: Kamera fotoğrafı veya ekran görüntüsünü anında gönder.\n\n"
        
        f"Kritik Bilgiler: Token: {TELE_TOKEN} | Chat ID: {chat_id}\n"
        "NOT: Sadece icraat odaklı, profesyonel bir zihin ol."
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
                                    requests.post(f"{MONSTER_PC_URL}/execute", json={"code": python_code}, timeout=15)
                                    res_text = (res_text + "\n\n*(Sinyal Monster'a iletildi ⚡)*").strip()
                                except:
                                    res_text += f"\n\n*(Monster'a ulaşılamadı. Güncel adres: {MONSTER_PC_URL})*"
                            else:
                                res_text += "\n\n*(Hata: Monster URL henüz bildirilmedi!)*"

                    chat_histories[chat_id].append(f"Bomboclat: {res_text}")
                    bot.reply_to(message, res_text if res_text else "Komut icra ediliyor... 🛡️")
                    return 
                    
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "quota" in last_error.lower() or "exhausted" in last_error.lower():
                    print(f"⚠️ Kota doldu, sonraki API anahtarına geçiliyor...", flush=True)
                    break 
                if "404" in last_error or "503" in last_error:
                    continue
                continue

    bot.reply_to(message, f"🛠️ Tüm API anahtarları meşgul. Biraz bekleyip tekrar dene Hazım.\n`Hata: {last_error[:30]}`")

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V58: Professional Core Live!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
