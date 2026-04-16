import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask

# --- 1. RENDER CANLI TUTMA (PORT FIX) ---
app = Flask(__name__)
@app.route('/')
def health(): return "Bot %100 Çevrimiçi!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. AYARLAR VE GEMINI ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
bot = telebot.TeleBot(TELE_TOKEN)

# Botun kendi kimlik bilgilerini alalım
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"
BOT_ID = BOT_INFO.id

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    # Komutlara karışma
    if message.text and message.text.startswith('/'):
        return

    # MANTIKSAL KONTROL:
    # 1. Mesajda botun etiketi var mı?
    is_tagged = message.text and BOT_USERNAME in message.text
    
    # 2. Mesaj, botun bir mesajına yanıt mı?
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_ID)

    # Eğer ikisi de değilse, bot sessiz kalır
    if not (is_tagged or is_reply_to_me):
        return

    try:
        # Mesajdan etiketi temizle ki Gemini'a temiz gitsin
        prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Bir şeyler söyle..."
        
        # Eğer kullanıcı sadece tag attıysa ve yazı yazmadıysa boş gitmesin
        if not prompt: prompt = "Efendim?"

        # Gemini'dan cevabı al
        response = model.generate_content(f"Sen Hazım'ın dürüst asistanısın. Kısa ve öz konuş. Soru: {prompt}")
        bot.reply_to(message, response.text)
        
    except Exception as e:
        print(f"Hata: {e}")
        bot.reply_to(message, f"🛠️ Sistem Pürüzü: {str(e)[:50]}...")

# --- 3. SİSTEMİ ATEŞLE ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 409 hatasını (çakışmayı) engellemek için eski kuyruğu temizle
    print("Geçmiş mesajlar temizleniyor ve bağlantı tazeleniyor...")
    bot.delete_webhook(drop_pending_updates=True)
    
    print(f"Bot {BOT_USERNAME} olarak hazır!")
    bot.infinity_polling()
    
