import telebot
import google.generativeai as genai
import os

# --- GÜVENLİ AYARLAR ---
# Kodun içine anahtar yazmıyoruz, sistemden çekiyoruz
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

# Gemini Yapılandırması
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    tools=[{"google_search": {}}]
)

bot = telebot.TeleBot(TELE_TOKEN)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    if message.text.startswith('/'):
        return

    try:
        instruction = "Sen Hazım'ın grubunun zeki asistanısın."
        chat = model.start_chat()
        full_prompt = f"{instruction}\n\nKullanıcı: {message.text}"
        response = chat.send_message(full_prompt)
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"Hata: {e}")

bot.infinity_polling()
