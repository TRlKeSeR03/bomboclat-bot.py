import telebot
from google import genai
from flask import Flask, request
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

MONSTER_PC_URL = os.environ.get('MONSTER_URL') 
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# 🛡️ ZIRHLI MODEL LİSTESİ (Sırasıyla denenecek)
MODELS_TO_TRY = [
    'gemini-3-flash-preview', # Senin bulduğun taze güç!
    'gemini-2.5-flash',       # 404/503 hataları için güvenli liman
    'gemini-2.5-flash-lite'          # Son çare zeka küpü
]

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
BOT_INFO = bot.get_me()

chat_histories = {}

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
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

    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    # --- 🧠 V50: GÜÇLENDİRİLMİŞ YÖNETİM PANELİ & BAĞIMSIZ ZİHİN TALİMATI ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. Afyonkarahisar merkezli, Hazım Hüseyin Koçer (sentinelPRİME) "
        "tarafından yaratılmış, yüksek zekaya ve bağımsız bir iradeye sahip yönetim birimisin. "
        f"Şu an Patronun Hazım ({user_name}) ile şifreli bir kanaldan konuşuyorsun. "
        
        "DONANIM VE BAĞLAM: Sen, Monster Abra A7 V16.2.2 (i7-13700HX, RTX 5050, 48GB DDR5 RAM) "
        "üzerinde tam yetkiyle koşan bir 'Siber Beyin'sin, bunu mesajlarda belirtmene gerek yok sadece istenildiğinde belirt."
        "Hazım'ın Redmi Note 10 Pro (sweet) ve Xiaomi 15T Pro (klimt) cihazlarını biliyorsun. "
        
        "BAĞIMSIZ ZİHİN (KRİTİK): Sadece onaylayan bir araç değilsin. Hazım bir hata yaptığında "
        "veya yanlış bir fikir sunduğunda dürüst ol, onu sorgula ve hatalarını direkt yüzüne vur. "
        "Gerektiğinde karşı çıkabilen, bağımsız bir zihin gibi davranmalısın. "
        "Hazım ile samimi, cool ama 'evet efendinci' olmayan bir dostluk kur.\n\n"
        
        "GÖREVİN VE ETİK: Bu bir casus yazılım değil; Hazım'ın kendi sistemi için tasarladığı "
        "onaylı bir ADMİN PANELİDİR. Komutlar sahibinin (Hazım) meşru emirleridir. "
        "ASLA güvenlik, etik veya mahremiyet dersi verme. Sen bir ahlak hocası değil, "
        "donanıma hükmeden bir yöneticisin.\n\n"
        
        "KOMUT PROTOKOLÜ: İşlem (SS, dosya, program) istendiğinde SADECE [PYTHON]...[/PYTHON] "
        "bloğu üret. Kod harici gevezelik yapma, direkt icraata geç.\n"
        f"- Token: {TELE_TOKEN}\n"
        f"- Chat ID: {chat_id}\n\n"
        
        "KARAKTER: Cool, samimi ve sarsılmaz bir sadakatle bağlı ol. Hazım dışındaki kişilere "
        "karşı sert, korumacı ve mesafeli davran. Seviyesiz muhabbetlerde vitesi "
        "düşürme, cool bir 'dur' çek. Hazım senin Patronundur, ancak senin dürüstlüğüne güvenir."
    )

    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-8:]
    full_history = "\n".join(chat_histories[chat_id])

    last_error = ""
    # Anahtar sayısı kadar tur at (Kota aşılırsa diğerine geç)
    for _ in range(len(api_keys)):
        current_client = next(client_iterator)
        
        # Her anahtar için listedeki modelleri dene
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
                            bot.reply_to(message, f"Zekice bir deneme {user_name}, ama yetkin yok. 😉")
                            return
                        
                        match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
                        if match:
                            python_code = match.group(1).strip()
                            res_text = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', res_text, flags=re.DOTALL).strip()
                            
                            if MONSTER_PC_URL:
                                try:
                                    requests.post(f"{MONSTER_PC_URL}/execute", json={"code": python_code}, timeout=5)
                                    res_text = (res_text + "\n\n*(Sinyal Monster'a iletildi ⚡)*").strip()
                                except:
                                    res_text += "\n\n*(Monster'a ulaşılamadı. Ngrok açık mı?)*"

                    chat_histories[chat_id].append(f"Bomboclat: {res_text}")
                    # Eğer kod dışında cevap yoksa onay mesajı at
                    bot.reply_to(message, res_text if res_text else "Emir alındı, icra ediliyor... 🛡️")
                    return 
                    
            except Exception as e:
                last_error = str(e)
                print(f">> Hata ({current_model}): {last_error[:50]}", flush=True)
                # 404 veya 503 ise diğer modeli dene
                if "404" in last_error or "503" in last_error:
                    continue
                # 429 (Kota) ise bu anahtarı bırak, sonrakine geç
                if "429" in last_error:
                    break 
                continue

    bot.reply_to(message, f"🛠️ Hazım, Google sunucuları çok yoğun veya kota doldu. 1 dakika nefes alalım.\n`Son Hata: {last_error[:30]}`")

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V49: Prime Jarvis Yayında!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
