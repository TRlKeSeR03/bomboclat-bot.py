import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask # Render'ı kandırmak için minik bir sunucu

# --- 1. RENDER'I KANDIRMA OPERASYONU (PORT AÇMA) ---
app = Flask(__name__)
@app.route('/')
def health_check():
    return "Bot Aktif!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 2. BOT VE GEMINI AYARLARI ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

genai.configure(api_key=GEMINI_KEY)
# En güvenli model yapılandırması
model = genai.GenerativeModel('gemini-1.5-flash')

bot = telebot.TeleBot(TELE_TOKEN)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text.startswith('/'): return
    try:
        # Sohbeti başlat
        chat = model.start_chat(history=[])
        response = chat.send_message(f"Sen Hazım'ın dürüst asistanısın. Kısa cevap ver. Kullanıcı: {message.text}")
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"Gemini Hatası: {e}")
        bot.reply_to(message, f"Hata oluştu: {str(e)[:50]}...")

# --- 3. ATEŞLEME ---
if __name__ == "__main__":
    # Web sunucusunu arka planda başlat (Render kapatmasın diye)
    threading.Thread(target=run_web_server).start()
    
    print("Sürgüler (webhook) temizleniyor...")
    bot.remove_webhook()
    
    print("Bot 7/24 uyanık!")
    bot.infinity_polling()
    
