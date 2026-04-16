import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask

# --- 1. RENDER CANLI TUTMA ---
app = Flask(__name__)
@app.route('/')
def health(): return "Sistemler %100 Aktif!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. AYARLAR VE GEMINI ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

genai.configure(api_key=GEMINI_KEY)

# KRİTİK DEĞİŞİKLİK: Model ismine 'models/' ön eki eklendi
model = genai.GenerativeModel('models/gemini-1.5-flash')

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"
BOT_ID = BOT_INFO.id

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return

    # Etiket veya Yanıtlama kontrolü
    is_tagged = message.text and BOT_USERNAME in message.text
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_ID)

    if not (is_tagged or is_reply_to_me): return

    try:
        prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Efendim?"
        
        # Daha sağlam bir yanıt alma yöntemi
        response = model.generate_content(f"Sen Hazım'ın dürüst asistanısın. Kısa ve öz konuş. Soru: {prompt}")
        
        if response.text:
            bot.reply_to(message, response.text)
        else:
            bot.reply_to(message, "Gemini boş bir yanıt döndürdü, tekrar dener misin?")
            
    except Exception as e:
        error_msg = str(e)
        print(f"Gemini Hatası: {error_msg}")
        # Hatayı tam anlamak için grupta kısa bir özet geçiyoruz
        bot.reply_to(message, f"🛠️ Sistem Pürüzü: {error_msg[:60]}...")

# --- 3. SİSTEMİ BAŞLAT ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 409 hatasını önlemek için bağlantıyı sıfırla
    bot.delete_webhook(drop_pending_updates=True)
    
    print(f"Bot {BOT_USERNAME} olarak uyanık ve hazır!")
    bot.infinity_polling()
    
