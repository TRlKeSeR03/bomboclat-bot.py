import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask
from google.generativeai.types import SafetySettingDict, HarmCategory, HarmBlockThreshold

# --- 1. RENDER CANLI TUTMA ---
app = Flask(__name__)
@app.route('/')
def health(): return "Sistemler Online", 200

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 2. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

genai.configure(api_key=GEMINI_KEY)

# Filtreleri gevşetiyoruz (Mason dürüstlüğü için bazen sert konuşması gerekebilir)
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    safety_settings=safety_settings
)

bot = telebot.TeleBot(TELE_TOKEN)
BOT_USERNAME = f"@{bot.get_me().username}"

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text.startswith('/') or BOT_USERNAME not in message.text:
        return

    try:
        clean_prompt = message.text.replace(BOT_USERNAME, "").strip()
        chat = model.start_chat(history=[])
        response = chat.send_message(f"Sen Hazım'ın zeki asistanısın. Kullanıcı: {clean_prompt}")
        bot.reply_to(message, response.text)
        
    except Exception as e:
        # HATAYI BURADAN GÖRECEĞİZ:
        error_text = str(e)
        print(f"Gemini Hatası: {error_text}")
        bot.reply_to(message, f"🛠️ Gemini Hatası: {error_text[:100]}")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.remove_webhook()
    print(f"{BOT_USERNAME} aktif!")
    bot.infinity_polling()
    
