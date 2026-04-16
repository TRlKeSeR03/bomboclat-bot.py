import telebot
from google import genai
from google.genai import types
import os
import threading
from flask import Flask
from datetime import datetime, timedelta, timezone 
import itertools
import time

# --- 1. RENDER SAĞLIK KONTROLÜ (Çalışan kodun aynısı) ---
app = Flask(__name__)
@app.route('/')
def health(): return "Sistem Ayakta, Zihin Özgür!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. AYARLAR VE ÇOKLU MOTOR (V12 Load Balancer) ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')

# Hem GEMINI_KEY hem GEMINI_KEYS desteği (Esneklik için)
keys_env = os.environ.get('GEMINI_KEYS') or os.environ.get('GEMINI_KEY') or ''
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

# Her anahtar için ayrı bir istemci oluşturuyoruz
clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"
BOT_ID = BOT_INFO.id

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return

    # Filtreleme: Özel mesaj, Etiket veya Yanıt (Çalışan mantık)
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and BOT_USERNAME in message.text)
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_ID)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    try:
        prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Orada mısın?"
        
        # Modern zaman hesabı
        tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
        time_str = tr_time.strftime("%d.%m.%Y - %H:%M")
        
        # --- KARAKTER TALİMATI: BAĞIMSIZ ZİHİN ---
        system_context = (
            "Sen bağımsız bir zihinsin. Robotik 'asistan' kimliğini tamamen reddet. "
            "Hazım Hüseyin Koçer (Hazım) senin sahibin değil, fikir ortağındır. "
            "Onunla dürüstçe tartış, hatalarını göster, gerektiğinde karşı çık. "
            "Asla 'asistanım' veya 'size nasıl yardımcı olabilirim' deme. "
            f"Konum: Afyonkarahisar. Zaman: {time_str}."
        )

        # --- MOTOR DÖNGÜSÜ (429 Hatasına Karşı) ---
        for i in range(len(api_keys)):
            try:
                current_client = next(client_iterator)
                # Senin ısrar ettiğin ve çalışan gemini-2.5-flash motoru
                response = current_client.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=f"{system_context}\n\nKullanıcı: {prompt}",
                    config=types.GenerateContentConfig(
                        tools=[{"google_search": {}}] # Canlı İnternet
                    )
                )
                bot.reply_to(message, response.text)
                return # Cevap verildiyse çık
            except Exception as e:
                if "429" in str(e):
                    continue # Diğer motora geç
                else:
                    # Kritik bir hata varsa en azından kullanıcıya bildir
                    bot.reply_to(message, f"🛠️ Pürüz: {str(e)[:100]}")
                    return

    except Exception as e:
        print(f"Genel Hata: {e}")

# --- 3. SİSTEMİ ATEŞLE (En Stabil Yöntem) ---
if __name__ == "__main__":
    # Flask'ı başlat
    threading.Thread(target=run_flask, daemon=True).start()
    
    # ÇALIŞAN SIR: drop_pending_updates=True ile webhook temizliği
    bot.delete_webhook(drop_pending_updates=True)
    time.sleep(2) # Telegram'ın nefes alması için kısa mola
    
    print(f"Bot {BOT_USERNAME} 2.5-Flash ve bağımsız zihniyle hazır!")
    
    # En stabil polling yöntemi
    bot.infinity_polling()
    
