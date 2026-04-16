import telebot
from google import genai
from google.genai import types
import os
import threading
from flask import Flask
from datetime import datetime, timedelta
import itertools

# --- 1. RENDER SAĞLIK KONTROLÜ ---
app = Flask(__name__)
@app.route('/')
def health(): return "Sistemler Afyon Mermeri Gibi!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. AYARLAR VE ÇOKLU MOTOR SİSTEMİ ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS', '')
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

# Her bir anahtar için motorları kur
clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"
BOT_ID = BOT_INFO.id

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return

    is_private = message.chat.type == 'private'
    is_tagged = (message.text and BOT_USERNAME in message.text)
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_ID)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    try:
        prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Efendim?"
        tr_time = datetime.utcnow() + timedelta(hours=3)
        time_str = tr_time.strftime("%d.%m.%Y - Saat: %H:%M")
        
        system_context = f"Sen Hazım'ın dürüst asistanısın. Zaman: {time_str}. Afyon'dasın. Kısa ve net konuş."
        
        current_client = next(client_iterator)
        
        # --- İNTERNETLİ VE SENİN MODELİNLE SORGULAMA ---
        response = current_client.models.generate_content(
            model='gemini-2.5-flash', # Senin dediğin gibi kalsın!
            contents=f"{system_context}\n\nKullanıcı: {prompt}",
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}] # İnternet araması aktif
            )
        )
        
        bot.reply_to(message, response.text)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Hata: {error_msg}")
        
        # Eğer yine 404 verirse, 2.0 sürümünü denemesi için bota bir şans verelim
        if "404" in error_msg:
            try:
                # 2.0-flash 2026'nın en stabil internet destekli modelidir
                response = current_client.models.generate_content(
                    model='gemini-2.0-flash', 
                    contents=f"{system_context}\n\nKullanıcı: {prompt}",
                    config=types.GenerateContentConfig(tools=[{"google_search": {}}])
                )
                bot.reply_to(message, response.text)
            except:
                bot.reply_to(message, f"🛠️ Model Hatası: İnternet özelliği {error_msg[:30]} sürümünde kapalı.")
        else:
            bot.reply_to(message, f"🛠️ Sistem Pürüzü: {error_msg[:60]}...")

# --- 3. SİSTEMİ ATEŞLE ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.delete_webhook(drop_pending_updates=True)
    print(f"Bot {BOT_USERNAME} hazır!")
    bot.infinity_polling()
    
