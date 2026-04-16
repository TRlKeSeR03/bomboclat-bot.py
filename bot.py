import telebot
import google.generativeai as genai
import os
import sys

# --- GÜVENLİ ANAHTAR KONTROLÜ ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

# Anahtarlar eksikse botu çalıştırma, hatayı loglara yaz
if not TELE_TOKEN or not GEMINI_KEY:
    print("HATA: TELEGRAM_TOKEN veya GEMINI_KEY ortam değişkenleri bulunamadı!")
    sys.exit(1)

try:
    genai.configure(api_key=GEMINI_KEY)
    
    # En uyumlu arama modunu deniyoruz
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        tools=[{'google_search_retrieval': {}}] # 0.8.6 sürümü için en garanti format
    )
    
    bot = telebot.TeleBot(TELE_TOKEN)
    print("Sistemler aktif, bot uyanıyor...")

except Exception as e:
    print(f"Başlatma sırasında kritik hata: {e}")
    sys.exit(1)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text.startswith('/'):
        return

    try:
        chat = model.start_chat()
        # Basit ve etkili bir prompt
        response = chat.send_message(f"Sen Hazım'ın grubunun asistanısın. Kısa ve öz cevap ver.\n\nKullanıcı: {message.text}")
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"Mesaj işleme hatası: {e}")
        bot.reply_to(message, "Şu an cevap veremiyorum, sistemlerimi kontrol ediyorum.")

# Botu sonsuz döngüye sok
bot.infinity_polling()
