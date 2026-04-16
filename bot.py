import telebot
from google import genai
import os
import threading
from flask import Flask

# --- RENDER SAĞLIK KONTROLÜ ---
app = Flask(__name__)
@app.route('/')
def health(): return "Yeni Nesil Bot Aktif!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- AYARLAR VE YENİ GEMINI KÜTÜPHANESİ ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

# Yeni nesil client oluşturma
client = genai.Client(api_key=GEMINI_KEY)

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"
BOT_ID = BOT_INFO.id

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return

    # Mantık: Özel mesaj, Etiket veya Yanıt
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and BOT_USERNAME in message.text)
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_ID)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    try:
        # Prompt'u temizle
        prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Efendim?"
        
        system_context = "Sen Hazım'ın asistanısın. Kısa ve net konuş."
        
        # Yeni nesil kütüphane ile mesaj gönderme
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Yeni kütüphane bu ismi sorunsuz tanır
            contents=f"{system_context}\n\nKullanıcı: {prompt}"
        )
        
        bot.reply_to(message, response.text)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Hata: {error_msg}")
        bot.reply_to(message, f"🛠️ Sistem Pürüzü: {error_msg[:60]}...")

# --- SİSTEMİ ATEŞLE ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.delete_webhook(drop_pending_updates=True)
    print(f"Bot {BOT_USERNAME} yeni kütüphaneyle hazır!")
    bot.infinity_polling()
    
