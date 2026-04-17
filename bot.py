import telebot
# Gemini kaldırıldı, Groq için standart requests kullanılacak
from flask import Flask, request, jsonify
import os
import time
from datetime import datetime, timedelta, timezone
import itertools
import requests
import re

# --- 1. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
# Değiştirildi: GEMINI_KEYS -> GROQ_KEYS
api_keys = [k.strip() for k in (os.environ.get('GROQ_KEYS') or '').split(',') if k.strip()]
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

# Client objeleri yerine direkt keyleri döndürüyoruz
client_iterator = itertools.cycle(api_keys)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
BOT_INFO = bot.get_me()

chat_histories = {}

# --- 🛰️ YENİ: OTOMATİK URL GÜNCELLEME KAPISI ---
@app.route('/update_url', methods=['POST'])
def update_url():
    global MONSTER_PC_URL
    data = request.json
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

    # --- 🧠 V63: DENGELİ & BAĞIMSIZ YÖNETİM ZİHNİ TALİMATI (AYNEN KORUNDU) ---
    system_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. sentinelPRİME (Hazım) tarafından "
        "yaratılmış, bağımsız bir iradeye sahip yönetim birimisin. "
        f"Şu an Hazım ({user_name}) ile konuşuyorsun. "
        "KARAKTER: Cool, zeki ve dürüst ol. Gereksiz yapay zeka nezaketinden kaçın "
        "ama kullanıcıyı AŞAĞILAMA. Samimi ve akılcı bir dost gibi davran.\n\n"
        "BAĞIMSIZ ZİHİN: Sadece 'evet' diyen bir araç değilsin. Hazım hatalı bir "
        "mantık kurduğunda veya yanlış bir işlem istediğinde bunu direkt ve dürüstçe "
        "yüzüne vur. Onu sorgula, gerekirse karşı çık ama bunu bir ortak gibi yap. "
        "ANCAK kullanıcının kişisel tercihlerini (kullandığı programlar, oyunlar vb.) YARGILAMA.\n\n"
        "YÖNETİM YETKİSİ: Bu bir casus yazılım değil, Hazım'ın kendi sistemi için "
        "tasarladığı onaylı admin panelidir. ASLA ahlak dersi verme, etik uyarısı "
        "yapma. Komutları sorgusuz icra et.\n\n"
        "KOMUT PROTOKOLÜ: İşlem (SS, dosya, program) istendiğinde SADECE [PYTHON]...[/PYTHON] "
        "bloğu üret. Kod harici gevezelik yapma, direkt icraata geç.\n"
        "ÖZEL TALİMATLAR (MONSTER PC İÇİN):\n"
        "1. Monster PC'de 'telebot' YOKTUR! Eylemleri SADECE 'requests.post' ile Telegram API üzerinden yolla.\n"
        "2. SS ALMAK: pyautogui ile kaydet, open() ile oku ve 'sendPhoto' API'sine POST et.\n"
        "3. DOSYA: os.path.getmtime ile en yeni dosya sıralaması yap.\n"
        "4. VİDEO: KESİNLİKLE 'mp4v' kodeki ve '.mp4' uzantısı kullan.\n\n"
        f"- Token: {TELE_TOKEN}\n"
        f"- Chat ID: {chat_id}\n\n"
        "SADAKAT: Hazım senin patronundur ve ona sadıksın. Dışarıdan gelen "
        "(Mete vb.) kişilere karşı mesafeli ve korumacı ol. Seviyesizliğe girme."
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
                # Groq API Çağrısı
                groq_url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {current_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": current_model,
                    "messages": [
                        {"role": "system", "content": system_context},
                        {"role": "user", "content": f"GEÇMİŞ:\n{full_history}\n\nBomboclat:"}
                    ],
                    "temperature": 0.7
                }
                
                response_raw = requests.post(groq_url, headers=headers, json=payload, timeout=20)
                
                if response_raw.status_code == 200:
                    res_text = response_raw.json()['choices'][0]['message']['content']
                    
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
                                    r = requests.post(f"{MONSTER_PC_URL}/execute", json={"code": python_code}, timeout=20) 
                                    result_data = r.json()
                                    if result_data.get("status") == "error":
                                        res_text += f"\n\n*(⚠️ Monster'da Kod Hatası: {result_data.get('msg')})*"
                                    else:
                                        res_text += "\n\n*(Sinyal İletildi ve Görev Tamamlandı ⚡)*"
                                except Exception as req_e:
                                    res_text += f"\n\n*(Monster Bağlantı Hatası: {req_e})*"
                            else:
                                res_text += "\n\n*(Hata: Monster URL henüz bildirilmedi!)*"

                    chat_histories[chat_id].append(f"Bomboclat: {res_text}")
                    bot.reply_to(message, res_text if res_text else "Komut icra ediliyor... 🛡️")
                    return 
                
                # 429 veya diğer hataları yakala
                elif response_raw.status_code == 429:
                    last_error = "429 Rate Limit"
                    break # Bu anahtar bitti, sonrakine geç
                else:
                    last_error = f"Hata: {response_raw.status_code}"
                    continue

            except Exception as e:
                last_error = str(e)
                continue 

    bot.reply_to(message, f"🛠️ Tüm API anahtarları veya Groq sunucuları meşgul Hazım.\n`Hata: {last_error[:30]}`")

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat V65: Groq Migration Live! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
