import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask

# --- 1. RENDER'I KANDIRMA (PORT AÇMA) ---
app = Flask(__name__)
@app.route('/')
def health_check():
    return "Bot Aktif ve Etiket Bekliyor!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 2. BOT VE GEMINI AYARLARI ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
bot = telebot.TeleBot(TELE_TOKEN)

# Botun kendi kullanıcı adını öğrenelim
BOT_USERNAME = f"@{bot.get_me().username}"

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    # 1. Komutlara cevap verme
    if message.text.startswith('/'): 
        return
    
    # 2. KRİTİK FİLTRE: Mesajda botun etiketi var mı?
    # Eğer botun @kullanıcıadı mesajın içinde yoksa, hiçbir şey yapma
    if BOT_USERNAME not in message.text:
        return

    try:
        # Mesajdan botun ismini temizle (Gemini'a tertemiz gitsin)
        clean_prompt = message.text.replace(BOT_USERNAME, "").strip()
        
        chat = model.start_chat(history=[])
        response = chat.send_message(f"Sen Hazım'ın dürüst asistanısın. Kısa ve öz cevap ver.\n\nKullanıcı: {clean_prompt}")
        
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"Gemini Hatası: {e}")
        bot.reply_to(message, "Sistemlerimde küçük bir pürüz oluştu...")

# --- 3. ATEŞLEME ---
if __name__ == "__main__":
    threading.Thread(target=run_web_server).start()
    
    bot.remove_webhook()
    print(f"Bot {BOT_USERNAME} olarak uyanık ve etiket bekliyor!")
    bot.infinity_polling()
    
