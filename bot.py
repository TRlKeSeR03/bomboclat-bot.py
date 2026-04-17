import telebot, os, time, requests, re, threading, itertools
from flask import Flask, request
from datetime import datetime, timedelta, timezone

# --- AYARLAR ---
TELE_TOKEN = os.environ.get('TELE_TOKEN')
GEMINI_KEYS = [k.strip() for k in (os.environ.get('GEMINI_KEYS') or '').split(',') if k.strip()]
GROQ_KEYS = [k.strip() for k in (os.environ.get('GROQ_KEYS') or '').split(',') if k.strip()]
ALLOWED_USERS = [5510143691]

MONSTER_PC_URL = os.environ.get('MONSTER_URL') 
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

gemini_iterator = itertools.cycle(GEMINI_KEYS) if GEMINI_KEYS else None
groq_iterator = itertools.cycle(GROQ_KEYS) if GROQ_KEYS else None

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
chat_histories = {}
processed_messages = set()

@app.route('/')
def health(): return "Bomboclat: Optimization Active! 🚀", 200

@app.route('/update_url', methods=['POST'])
def update_url():
    global MONSTER_PC_URL
    data = request.json
    if data and data.get('secret') == TELE_TOKEN:
        MONSTER_PC_URL = data.get('url')
        return "URL_OK", 200
    return "YETKISIZ", 403

def get_ai_response(prompt, system_context, full_history):
    # GEMINI (Öncelikli - Kotası daha geniş)
    if gemini_iterator:
        for _ in range(len(GEMINI_KEYS)):
            key = next(gemini_iterator)
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
                # Mesajı iyice küçülttük
                payload = {"contents": [{"parts": [{"text": f"Sistem: {system_context}\nGeçmiş: {full_history}\nİstek: {prompt}"}]}]}
                r = requests.post(url, json=payload, timeout=10)
                if r.status_code == 200:
                    return r.json()['candidates'][0]['content']['parts'][0]['text'], "*(✨ Gemini)*"
                elif r.status_code == 429: time.sleep(2) # Kotaya takılırsa bekle
            except: continue

    # GROQ (Yedek - RPM sınırı dar)
    if groq_iterator:
        for _ in range(len(GROQ_KEYS)):
            key = next(groq_iterator)
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "system", "content": system_context}, {"role": "user", "content": prompt}],
                        "temperature": 0.6
                    }, timeout=10
                )
                if r.status_code == 200:
                    return r.json()['choices'][0]['message']['content'], "*(☁️ Groq)*"
            except: continue
    return None, None

def process_ai_request(message, prompt, user_name, chat_id, user_id):
    global MONSTER_PC_URL
    if message.message_id in processed_messages: return
    processed_messages.add(message.message_id)
    
    is_pc_alive = False
    if MONSTER_PC_URL:
        try:
            if requests.get(f"{MONSTER_PC_URL}/status", timeout=2, headers={'ngrok-skip-browser-warning': 'true'}).status_code == 200:
                is_pc_alive = True
        except: pass

    # En kısa ve öz sistem talimatı
    system_context = f"Adın Bomboclat. Hazım'ın (sentinelPRİME) ortağısın. PC: {'AÇIK' if is_pc_alive else 'KAPALI'}. Sadece SS/Kamera/Uygulama için [PYTHON]...[/PYTHON] kodu yaz."

    if chat_id not in chat_histories: chat_histories[chat_id] = []
    full_history = "\n".join(chat_histories[chat_id][-4:]) # Sadece son 4 mesaj
    
    res_text, source = get_ai_response(prompt, system_context, full_history)

    if res_text:
        clean_res = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', res_text, flags=re.DOTALL).strip()
        
        if "[PYTHON]" in res_text and is_pc_alive and user_id in ALLOWED_USERS:
            match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
            if match:
                try:
                    requests.post(f"{MONSTER_PC_URL}/execute", json={"code": match.group(1).strip()}, timeout=40, headers={'ngrok-skip-browser-warning': 'true'})
                    bot.send_message(chat_id, f"{clean_res or 'Hemen hallediyorum.'} ⚡\n\n{source}")
                    return
                except: pass

        bot.send_message(chat_id, f"{clean_res or res_text}\n\n{source}")
        chat_histories[chat_id].append(f"H: {prompt}")
        chat_histories[chat_id].append(f"B: {clean_res or 'Kod'}")
        chat_histories[chat_id] = chat_histories[chat_id][-6:]
    else:
        bot.send_message(chat_id, "⚠️ Kotalar anlık dolu, 10 sn bekleyip tekrar dene Hazım.")
    
    if len(processed_messages) > 100: processed_messages.clear()

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id, chat_id = message.from_user.id, message.chat.id
    if not message.text: return
    msg = message.text.lower()
    if msg in ["id", "/id"]:
        bot.reply_to(message, f"ID: `{user_id}`")
        return
    if (message.chat.type == 'private' or f"@{bot.get_me().username}" in message.text):
        p = message.text.replace(f"@{bot.get_me().username}", "").strip()
        threading.Thread(target=process_ai_request, args=(message, p, message.from_user.first_name, chat_id, user_id)).start()

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
