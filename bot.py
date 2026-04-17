import telebot
from flask import Flask, request
import os, time, requests, re, threading, itertools
from datetime import datetime, timedelta, timezone

# --- AYARLAR ---
TELE_TOKEN = os.environ.get('TELE_TOKEN') or os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEYS = [k.strip() for k in (os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]
GROQ_KEYS = [k.strip() for k in (os.environ.get('GROQ_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [5510143691] # Hazım'ın ID'si

MONSTER_PC_URL = os.environ.get('MONSTER_URL') 
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

gemini_iterator = itertools.cycle(GEMINI_KEYS) if GEMINI_KEYS else None
groq_iterator = itertools.cycle(GROQ_KEYS) if GROQ_KEYS else None

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
BOT_INFO = bot.get_me()
chat_histories = {}
processed_messages = set() 

@app.route('/')
def health(): return "Bomboclat: System Stabilized! 🚀", 200

@app.route('/update_url', methods=['POST'])
def update_url():
    global MONSTER_PC_URL
    data = request.json
    if data and data.get('secret') == TELE_TOKEN:
        MONSTER_PC_URL = data.get('url')
        print(f"🚀 URL GÜNCELLENDİ: {MONSTER_PC_URL}", flush=True)
        return "URL_OK", 200
    return "YETKISIZ", 403

def get_ai_response(prompt, system_context, full_history):
    # 1. GEMINI FLASH (Daha stabil)
    if gemini_iterator:
        for _ in range(len(GEMINI_KEYS)):
            key = next(gemini_iterator)
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
                payload = {"contents": [{"parts": [{"text": f"SİSTEM:\n{system_context}\n\nGEÇMİŞ:\n{full_history}\n\nİSTEK: {prompt}"}]}]}
                r = requests.post(url, json=payload, timeout=14)
                if r.status_code == 200:
                    return r.json()['candidates'][0]['content']['parts'][0]['text'], "*(✨ Gemini)*"
            except: continue

    # 2. GROQ
    if groq_iterator:
        for _ in range(len(GROQ_KEYS)):
            key = next(groq_iterator)
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "system", "content": system_context}, {"role": "user", "content": f"GEÇMİŞ:\n{full_history}\n\nİSTEK: {prompt}"}],
                        "temperature": 0.6
                    }, timeout=14
                )
                if r.status_code == 200:
                    return r.json()['choices'][0]['message']['content'], "*(☁️ Groq)*"
            except: continue
    return None, None

def process_ai_request(message, prompt, user_name, chat_id, user_id):
    global MONSTER_PC_URL
    try:
        if message.message_id in processed_messages: return
        processed_messages.add(message.message_id)
        
        is_pc_alive = False
        if MONSTER_PC_URL:
            try:
                check = requests.get(f"{MONSTER_PC_URL}/status", timeout=2, headers={'ngrok-skip-browser-warning': 'true'})
                if check.status_code == 200: is_pc_alive = True
            except: pass

        # --- ÜSLUP VE KİMLİK AYARI ---
        system_context = (
            "KİMLİK: Senin adın Bomboclat. Sen, Hazım (sentinelPRİME) tarafından yaratılmış bağımsız, akılcı ve dürüst bir zihinsin.\n"
            "ROL: Sen bir uşak değilsin, Hazım'ın dijital dünyadaki ortağısın.\n"
            f"MUHATAP: Karşındaki kişi Hazım. Ona ismiyle hitap et. Asla robotik 'Nasıl yardımcı olabilirim?' gibi klişeler kullanma.\n"
            f"PC DURUMU: {'AÇIK' if is_pc_alive else 'KAPALI'}. Konum: Afyonkarahisar.\n"
            "DİL: Sadece Türkçe konuş, araya yabancı kelime karıştırma.\n"
            "TEKNİK: SS, kamera veya uygulama isteklerinde SADECE [PYTHON]...[/PYTHON] kodu üret, başka hiçbir metin yazma."
        )

        if chat_id not in chat_histories: chat_histories[chat_id] = []
        full_history = "\n".join(chat_histories[chat_id][-4:]) 
        
        res_text, source = get_ai_response(prompt, system_context, full_history)

        if res_text:
            clean_res = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', res_text, flags=re.DOTALL).strip()
            
            if "[PYTHON]" in res_text and is_pc_alive and user_id in ALLOWED_USERS:
                match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
                if match:
                    try:
                        requests.post(f"{MONSTER_PC_URL}/execute", json={"code": match.group(1).strip()}, timeout=40, headers={'ngrok-skip-browser-warning': 'true'})
                        bot.send_message(chat_id, f"{clean_res or 'Halledeyim hemen.'} ⚡\n\n{source}")
                    except:
                        bot.send_message(chat_id, f"{clean_res}\n*(⚠️ Monster düştü)*")
                    return

            bot.send_message(chat_id, f"{clean_res or res_text}\n\n{source}")
            
            # Hafıza yönetimi: Sadece son mesajları tut, kafa karışmasın
            chat_histories[chat_id].append(f"Hazım: {prompt}")
            chat_histories[chat_id].append(f"Bomboclat: {clean_res or 'İşlem yapıldı.'}")
            chat_histories[chat_id] = chat_histories[chat_id][-8:]
        else:
            bot.send_message(chat_id, "❌ Servislerde tıkanıklık var (Kota/Timeout).")

    except Exception as e:
        bot.send_message(chat_id, f"🛠️ **Hata:** `{str(e)[:100]}`")
    finally:
        if len(processed_messages) > 100: processed_messages.clear()

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id, chat_id = message.from_user.id, message.chat.id
    if not message.text: return
    
    msg_lower = message.text.lower()
    if msg_lower in ["id", "benim id ne", "/id"]:
        bot.reply_to(message, f"Senin ID: `{user_id}`")
        return
    if msg_lower == "/link":
        bot.reply_to(message, f"Monster: `{MONSTER_PC_URL}`")
        return

    is_private = message.chat.type == 'private'
    is_tagged = f"@{BOT_INFO.username}" in message.text
    if is_private or is_tagged:
        prompt = message.text.replace(f"@{BOT_INFO.username}", "").strip()
        threading.Thread(target=process_ai_request, args=(message, prompt, message.from_user.first_name, chat_id, user_id)).start()

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
