import telebot
from google import genai
from google.genai import types # İNTERNET ARAMASI İÇİN YENİ EKLENDİ
import os
import threading
from flask import Flask
from datetime import datetime, timedelta
import itertools

# --- 1. RENDER SAĞLIK KONTROLÜ ---
app = Flask(__name__)
@app.route('/')
def health(): return "İnternete Bağlı Çok Motorlu Bot Aktif!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. YÜK DENGELEYİCİ VE AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS', '')
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

if not api_keys:
    print("DİKKAT: Hiç API Anahtarı Bulunamadı!")

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"
BOT_ID = BOT_INFO.id

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return

    # Filtre: Özel mesaj, Etiket veya Yanıt
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and BOT_USERNAME in message.text)
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_ID)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    try:
        prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Efendim?"
        
        tr_time = datetime.utcnow() + timedelta(hours=3)
        time_str = tr_time.strftime("%d.%m.%Y - Saat: %H:%M")
        
        system_context = f"Sen Hazım'ın dürüst asistanısın. Şu anki tarih/saat: {time_str}. Afyonkarahisar'dasın. Kısa ve net cevap ver."
        
        current_client = next(client_iterator)
        
        # --- KRİTİK NOKTA: İNTERNET ARAMASI DEVREYE GİRİYOR ---
        response = current_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=f"{system_context}\n\nKullanıcı: {prompt}",
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}] # Botun beynine Google Arama bağlandı
            )
        )
        
        bot.reply_to(message, response.text)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Hata: {error_msg}")
        bot.reply_to(message, f"🛠️ İşlemci Isındı: {error_msg[:60]}...")

# --- 3. SİSTEMİ ATEŞLE ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.delete_webhook(drop_pending_updates=True)
    print(f"Bot {BOT_USERNAME}, {len(api_keys)} motor ve CANLI İNTERNET bağlantısıyla sahada!")
    bot.infinity_polling()
    
