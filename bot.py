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

# Anahtar Döngüleri
gemini_iterator = itertools.cycle(GEMINI_KEYS) if GEMINI_KEYS else None
groq_iterator = itertools.cycle(GROQ_KEYS) if GROQ_KEYS else None

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)
BOT_INFO = bot.get_me()
chat_histories = {}
processed_messages = set() 

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
    # 1. ÖNCE GEMINI FLASH
    if gemini_iterator:
        for _ in range(len(GEMINI_KEYS)):
            current_key = next(gemini_iterator)
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={current_key}"
                payload = {
                    "contents": [{"parts": [{"text": f"SİSTEM TALİMATI:\n{system_context}\n\nGEÇMİŞ SOHBET:\n{full_history}\n\nKULLANICI: {prompt}"}]}],
                    "generationConfig": {"temperature": 0.8}
                }
                r = requests.post(url, json=payload, timeout=12)
                if r.status_code == 200:
                    return r.json()['candidates'][0]['content']['parts'][0]['text']
            except: continue

    # 2. YEDEK: GROQ
    if groq_iterator:
        for _ in range(len(GROQ_KEYS)):
            current_key = next(groq_iterator)
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {current_key}"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "system", "content": system_context}, {"role": "user", "content": prompt}],
                        "temperature": 0.7
                    }, timeout=12
                )
                if r.status_code == 200:
                    return r.json()['choices'][0]['message']['content']
            except: continue
    return None

def process_ai_request(message, prompt, user_name, chat_id, user_id):
    global MONSTER_PC_URL
    if message.message_id in processed_messages: return
    processed_messages.add(message.message_id)
    
    is_pc_alive = False
    if MONSTER_PC_URL:
        try:
            check = requests.get(f"{MONSTER_PC_URL}/status", timeout=2, headers={'ngrok-skip-browser-warning': 'true'})
            if check.status_code == 200: is_pc_alive = True
        except: is_pc_alive = False

    now = datetime.now(timezone.utc) + timedelta(hours=3)
    
    # --- PROMPT VE KURALLAR ---
    system_context = (
        f"KİMLİK: Sen Bomboclat'sın. sentinelPRİME (Hazım) asistanısın. Konum: Afyonkarahisar.\n"
        f"PC DURUMU: {'AÇIK' if is_pc_alive else 'KAPALI'}.\n\n"
        "TALİMATLAR:\n"
        "1. Her mesajda saat söyleme. Sadece kullanıcı açıkça saat kaç diye sorarsa söyle.\n"
        "2. Doğal ve akılcı konuş. Gereksiz robotik girişlerden kaçın.\n"
        "3. PC açıksa ve bir işlem (ss, kamera, site açma, uygulama çalıştırma vb.) istenirse SADECE [PYTHON]...[/PYTHON] bloğu üret.\n"
        "4. Kod yazarken 'requests.post' ile Telegram'a dosya göndermeyi unutma.\n"
        f"Teknik Bilgi: Token={TELE_TOKEN}, ChatID={chat_id}"
    )

    full_history = "\n".join(chat_histories.get(chat_id, [])[-5:])
    res_text = get_ai_response(prompt, system_context, full_history)

    if res_text:
        # Kod bloğunu Telegram mesajından temizle (Görünmez yap)
        clean_res = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', res_text, flags=re.DOTALL).strip()
        
        # Kod çalıştırma (Sadece yetkili kullanıcı ve açık PC)
        if "[PYTHON]" in res_text and is_pc_alive and user_id in ALLOWED_USERS:
            match = re.search(r'\[PYTHON\](.*?)\[/PYTHON\]', res_text, re.DOTALL)
            if match:
                try:
                    # Kodu gizlice Monster'a gönder
                    requests.post(f"{MONSTER_PC_URL}/execute", json={"code": match.group(1).strip()}, timeout=40, headers={'ngrok-skip-browser-warning': 'true'})
                    
                    # Kullanıcıya sadece temizlenmiş mesajı ve onay sembolünü gönder
                    status_text = f"{clean_res}\n\n⚡" if clean_res else "İstediğin işlemi hallediyorum Hazım. ⚡"
                    bot.send_message(chat_id, status_text)
                except:
                    bot.send_message(chat_id, f"{clean_res}\n*(⚠️ PC Bağlantı Hatası)*")
                return

        # Kod yoksa veya PC kapalıysa sadece temiz mesajı gönder
        if clean_res or res_text:
            bot.send_message(chat_id, clean_res or res_text)
        
    if len(processed_messages) > 100: processed_messages.clear()

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id, chat_id = message.from_user.id, message.chat.id
    if message.text and not message.text.startswith('/'):
        threading.Thread(target=process_ai_request, args=(message, message.text, message.from_user.first_name, chat_id, user_id)).start()

@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@app.route('/')
def main(): return "Bomboclat Hybrid AI: Silent & Efficient! 🚀", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
