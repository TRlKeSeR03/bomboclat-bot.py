import telebot
from flask import Flask, request
import os, time, requests, re, threading, itertools
from datetime import datetime, timedelta, timezone

# --- AYARLAR ---
TELE_TOKEN = os.environ.get('TELE_TOKEN') or os.environ.get('TELEGRAM_TOKEN')
# Birden fazla anahtarı virgülle ayırarak (KEY1, KEY2) ekleyebilirsin
GEMINI_KEYS = [k.strip() for k in (os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]
GROQ_KEYS = [k.strip() for k in (os.environ.get('GROQ_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [5510143691] # Senin ID'n sabitlendi

MONSTER_PC_URL = os.environ.get('MONSTER_URL') 
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# Anahtar döngüleri (Kota aşımında bir sonrakine geçer)
gemini_iterator = itertools.cycle(GEMINI_KEYS) if GEMINI_KEYS else None
groq_iterator = itertools.cycle(GROQ_KEYS) if GROQ_KEYS else None

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

def get_ai_response(prompt, system_context, full_history):
    # 1. ÖNCE GEMINI FLASH DENE (Hızlı ve zeki)
    if gemini_iterator:
        for _ in range(len(GEMINI_KEYS)):
            current_key = next(gemini_iterator)
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={current_key}"
                payload = {
                    "contents": [{"parts": [{"text": f"SİSTEM: {system_context}\n\nGEÇMİŞ:\n{full_history}\n\nKULLANICI: {prompt}"}]}],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1000}
                }
                r = requests.post(url, json=payload, timeout=15)
                if r.status_code == 200:
                    return r.json()['candidates'][0]['content']['parts'][0]['text'], "*(✨ Gemini Flash)*"
            except: continue

    # 2. GEMINI PATLARSA VEYA YOKSA GROQ DENE
    if groq_iterator:
        for _ in range(len(GROQ_KEYS)):
            current_key = next(groq_iterator)
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {current_key}"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [
                            {"role": "system", "content": system_context},
                            {"role": "user", "content": f"GEÇMİŞ:\n{full_history}\n\nİSTEK: {prompt}"}
                        ],
                        "temperature": 0.6
                    }, timeout=15
                )
                if r.status_code == 200:
                    return r.json()['choices'][0]['message']['content'], "*(☁️ Groq Cloud)*"
            except: continue
            
    return None, None

def process_ai_request(message, prompt, user_name, chat_id, user_id):
    global MONSTER_PC_URL
    if chat_id not in chat_histories: chat_histories[chat_id] = []
    
    # PC Online mı kontrolü
    is_pc_alive = False
    if MONSTER_PC_URL:
        try:
            check = requests.get(f"{MONSTER_PC_URL}/status", timeout=2, headers={'ngrok-skip-browser-warning': 'true'})
            if check.status_code == 200: is_pc_alive = True
        except: is_pc_alive = False

    now = datetime.now(timezone.utc) + timedelta(hours=3)
    
    # --- PROMPT HAZIRLIĞI ---
    system_context = (
        f"KİMLİK: Sen Bomboclat'sın. Hazım'ın (sentinelPRİME) asistanısın. Konum: Afyonkarahisar.\n"
        f"Zaman: {now.strftime('%H:%M:%S')}. PC DURUMU: {'AÇIK' if is_pc_alive else 'KAPALI'}.\n\n"
        "ÜSLUP: Bağımsız, akılcı ve dürüst bir ortak ol. Gereksiz kibarlıktan kaçın.\n"
    )

    if is_pc_alive:
        system_context += (
            "GÖREV: PC şu an açık. Kullanıcı işlem isterse SADECE [PYTHON]...[/PYTHON] bloğu üret.\n"
            "Dosya gönderme/SS/Kamera için requests.post kullanarak Telegram API'sine yükleme yap.\n"
            f"Bot Token: {TELE_TOKEN} | Chat ID: {chat_id}"
        )
    else:
        system_context += "GÖREV: PC kapalı. Sadece sohbet et, asla kod yazma. PC kapalı olduğu için işlem yapamadığını belirt."

    full_history = "\n".join(chat_histories[chat_id][-10:])
    res_text, brain_source = get_ai_response(prompt, system_context, full_history)

    if res_text:
        # Kod çalıştırma (Sadece PC açıksa ve yetkiliysen)
        if "[PYTHON]" in res_text and is_pc_alive and user_id in ALLOWED_USERS:
            match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
            if match:
                try:
                    requests.post(f"{MONSTER_PC_URL}/execute", json={"code": match.group(1).strip()}, timeout=40, headers={'ngrok-skip-browser-warning': 'true'})
                    bot.send_message(chat_id, f"{res_text}\n\n{brain_source} | *(İşlem İletildi ⚡)*")
                except:
                    bot.send_message(chat_id, f"{res_text}\n\n{brain_source} | *(⚠️ PC Bağlantı Hatası)*")
                chat_histories[chat_id].append(f"Bomboclat: {res_text}")
                return

        bot.send_message(chat_id, f"{res_text}\n\n{brain_source}")
        chat_histories[chat_id].append(f"Hazım: {prompt}")
        chat_histories[chat_id].append(f"Bomboclat: {res_text}")
    else:
        bot.send_message(chat_id, "❌ Maalesef şu an ne Gemini'ye ne de Groq'a ulaşılamıyor. Kotalar dolmuş olabilir.")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id, chat_id = message.from_user.id, message.chat.id
    user_name = message.from_user.first_name or "Hazım"
    
    if message.text:
        if message.text.lower() == "/link":
            bot.reply_to(message, f"Elimdeki Monster URL: `{MONSTER_PC_URL}`")
            return
        if message.text.lower() == "id":
            bot.reply_to(message, f"ID: `{user_id}`")
            return

    if message.text and message.text.startswith('/'): return
    
    # Sadece özel mesajlar veya etiketlemeler
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{BOT_INFO.username}" in message.text)
    if not (is_private or is_tagged): return

    prompt = (message.text or "").replace(f"@{BOT_INFO.username}", "").strip()
    threading.Thread(target=process_ai_request, args=(message, prompt, user_name, chat_id, user_id)).start()

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@app.route('/')
def main(): return "Bomboclat Hybrid AI: Cloud Brain Active! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
