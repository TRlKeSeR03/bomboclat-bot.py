import telebot
from flask import Flask, request
import os, time, requests, re, threading, itertools
from datetime import datetime, timedelta, timezone

# --- AYARLAR ---
TELE_TOKEN = os.environ.get('TELE_TOKEN') or os.environ.get('TELEGRAM_TOKEN')
api_keys = [k.strip() for k in (os.environ.get('GROQ_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [int(i.strip()) for i in (os.environ.get('ALLOWED_USERS') or '').split(',') if i.strip()]

OWNER_ID = 5510143691 
if OWNER_ID not in ALLOWED_USERS: 
    ALLOWED_USERS.append(OWNER_ID)

# MONSTER_PC_URL başlangıçta None olabilir, jarvis.py güncelleyecektir.
MONSTER_PC_URL = os.environ.get('MONSTER_URL') 
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"
MODELS_TO_TRY = ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile']
client_iterator = itertools.cycle(api_keys)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
BOT_INFO = bot.get_me()
chat_histories = {}

@app.route('/update_url', methods=['POST'])
def update_url():
    global MONSTER_PC_URL
    data = request.json
    if data and data.get('secret') == TELE_TOKEN:
        MONSTER_PC_URL = data.get('url')
        print(f"🚀 MONSTER URL GÜNCELLENDİ: {MONSTER_PC_URL}", flush=True)
        return "URL_OK", 200
    return "YETKISIZ", 403

def process_ai_request(message, prompt, user_name, chat_id, user_id):
    global MONSTER_PC_URL
    if chat_id not in chat_histories: chat_histories[chat_id] = []
    
    now = datetime.now(timezone.utc) + timedelta(hours=3)
    res_text, brain_source, error_log = "", "", ""

    # --- 1. ADIM: PC DURUM KONTROLÜ (PING) ---
    is_pc_alive = False
    if MONSTER_PC_URL:
        try:
            # Ngrok tünelleri bazen browser uyarısı verebilir, bu yüzden headers ekliyoruz
            check = requests.get(f"{MONSTER_PC_URL}/status", timeout=3, headers={'ngrok-skip-browser-warning': 'true'})
            if check.status_code == 200:
                is_pc_alive = True
            else:
                error_log = f"Ollama Durum Hatası: {check.status_code}"
        except Exception as e:
            is_pc_alive = False
            error_log = f"Ollama Ping Hatası: {str(e)[:50]}"

    # --- 2. ADIM: PROMPT HAZIRLIĞI ---
    base_context = (
        f"SENİN KİMLİĞİN: Sen 'Bomboclat'sın. Hazım tarafından yaratılmış bağımsız bir zihinsin.\n"
        f"Konuştuğun kişi: {user_name} | Zaman: {now.strftime('%H:%M:%S')}\n"
        f"Lokasyon: Afyonkarahisar (Monster RTX 5050 Laptop)\n\n"
    )

    if is_pc_alive:
        system_context = base_context + "MONSTER PC AÇIK. İşlemler için [PYTHON]...[/PYTHON] bloğu kullanabilirsin."
    else:
        system_context = base_context + "MONSTER PC KAPALI. Sadece sohbet et, kod yazma."

    chat_histories[chat_id].append(f"{user_name}: {prompt}")
    chat_histories[chat_id] = chat_histories[chat_id][-10:] # Hafızayı taze tutalım
    full_history = "\n".join(chat_histories[chat_id])

    # --- 3. ADIM: ZEKA SEÇİMİ (OLLAMA -> GROQ) ---
    # Öncelik Ollama (Cihaz açıksa)
    if is_pc_alive:
        try:
            m_resp = requests.post(
                f"{MONSTER_PC_URL}/generate", 
                json={"prompt": prompt, "system": system_context, "history": full_history},
                timeout=45,
                headers={'ngrok-skip-browser-warning': 'true'}
            )
            if m_resp.status_code == 200:
                res_text = m_resp.json().get("response", "")
                brain_source = "*(⚡ Monster RTX 5050)*"
        except: pass

    # Yedek Zeka (Groq) - Ollama kapalıysa veya hata verdiyse
    if not res_text and api_keys:
        current_key = next(client_iterator)
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"},
                json={
                    "model": MODELS_TO_TRY[0],
                    "messages": [
                        {"role": "system", "content": system_context},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.6 
                }, timeout=15
            )
            if resp.status_code == 200:
                res_text = resp.json()['choices'][0]['message']['content']
                brain_source = "*(☁️ Groq Cloud)*"
        except Exception as e:
            error_log += f" | Groq Hatası: {str(e)[:30]}"

    # --- 4. ADIM: YANIT VE İCRAAT ---
    if res_text:
        # Kod çalıştırma mantığı
        if "[PYTHON]" in res_text and is_pc_alive and user_id in ALLOWED_USERS:
            match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
            if match:
                try:
                    requests.post(f"{MONSTER_PC_URL}/execute", json={"code": match.group(1).strip()}, timeout=40, headers={'ngrok-skip-browser-warning': 'true'})
                    bot.send_message(chat_id, f"{res_text}\n\n{brain_source} | *(İşlem İletildi ⚡)*")
                    return
                except: pass
        
        bot.send_message(chat_id, f"{res_text}\n\n{brain_source}")
    else:
        # Her iki zeka da başarısızsa detaylı hata ver
        bot.send_message(chat_id, f"🛠️ **Beyinlere ulaşılamıyor Hazım!**\n\n⚠️ Hata: {error_log}\n🔗 URL: {str(MONSTER_PC_URL)[:25]}...")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id, chat_id = message.from_user.id, message.chat.id
    user_name = message.from_user.first_name or "Hazım"
    
    if message.text:
        # Debug komutu: Botun elindeki URL'yi görmek için
        if message.text.lower() == "/link":
            bot.reply_to(message, f"Elimdeki Monster URL: `{MONSTER_PC_URL}`")
            return
        if message.text.lower() == "id":
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
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@app.route('/')
def main(): return f"Bomboclat Active! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
