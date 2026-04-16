import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask

# --- 1. RENDER CANLI TUTMA ---
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

# 404 hatasını önlemek için model ismini en stabil haline çektik
model = genai.GenerativeModel('gemini-1.5-flash')

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"
BOT_ID = BOT_INFO.id

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    # Komutlara karışma
    if message.text and message.text.startswith('/'): return

    # --- KRİTİK MANTIK GÜNCELLEMESİ ---
    is_private = message.chat.type == 'private' # Özel mesaj mı?
    is_tagged = message.text and BOT_USERNAME in message.text # Etiketlendi mi?
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_ID) # Yanıtlandı mı?

    # ÖZELDE direkt cevap ver, GRUPTA ise etiket veya yanıt bekle
    if not (is_private or is_tagged or is_reply_to_me):
        return

    try:
        # Mesajdan botun ismini temizle
        clean_prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Efendim?"
        
        # Hazım'ın donanımlarını ve konumunu hatırlatıyoruz (Opsiyonel ama Mason dokunuşu)
        system_instruction = "Sen Hazım'ın asistanısın. Hazım Afyonkarahisar'da yaşıyor ve Monster Abra A7 laptopu var. Kısa ve dürüst cevap ver."
        
        response = model.generate_content(f"{system_instruction}\n\nKullanıcı: {clean_prompt}")
        bot.reply_to(message, response.text)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Gemini Hatası: {error_msg}")
        bot.reply_to(message, f"🛠️ Sistem Pürüzü: {error_msg[:60]}...")

# --- 3. SİSTEMİ ATEŞLE ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Bağlantıyı tertemiz açıyoruz
    bot.delete_webhook(drop_pending_updates=True)
    
    print(f"Bot {BOT_USERNAME} olarak hem özelde hem grupta hazır!")
    bot.infinity_polling()
    
