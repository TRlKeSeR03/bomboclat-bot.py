import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask

# --- 1. RENDER SAĞLIK KONTROLÜ ---
app = Flask(__name__)
@app.route('/')
def health(): return "Bot 7/24 Aktif!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. AYARLAR VE GEMINI ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

genai.configure(api_key=GEMINI_KEY)

# MÜHENDİS DOKUNUŞU: Mevcut tüm modelleri loglara yazdır (Doğru ismi oradan teyit edebilirsin)
print("--- MEVCUT MODELLER LİSTESİ ---")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"Model Adı: {m.name}")
print("-------------------------------")

# 404 hatasını önlemek için en temel ismi kullanıyoruz
model = genai.GenerativeModel('gemini-1.5-flash')

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"
BOT_ID = BOT_INFO.id

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return

    # MANTIKSAL KONTROL:
    is_private = message.chat.type == 'private' # Özel mesaj mı?
    is_tagged = (message.text and BOT_USERNAME in message.text) # Grupta etiketlendi mi?
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_ID) # Grupta yanıt mı?

    # ÖZELDE direkt çalışır, GRUPTA etiket veya yanıt bekler
    if not (is_private or is_tagged or is_reply_to_me):
        return

    try:
        # Mesajı temizle (Grupta etiket varsa siler, özelde aynen bırakır)
        prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Efendim?"
        
        # Mason dürüstlüğüyle bir prompt
        system_context = "Sen Hazım'ın dürüst ve zeki asistanısın. Kısa cevap ver."
        
        response = model.generate_content(f"{system_context}\n\nSoru: {prompt}")
        bot.reply_to(message, response.text)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Kritik Hata: {error_msg}")
        bot.reply_to(message, f"🛠️ Sistem Pürüzü: {error_msg[:60]}...")

# --- 3. ATEŞLEME ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.delete_webhook(drop_pending_updates=True)
    print(f"Bot {BOT_USERNAME} olarak uyanık!")
    bot.infinity_polling()
    
