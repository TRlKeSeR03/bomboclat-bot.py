import telebot
from google import genai
from google.genai import types
import os
import threading
from flask import Flask
from datetime import datetime, timedelta, timezone 
import itertools
import time

# --- 1. RENDER SAĞLIK KONTROLÜ ---
app = Flask(__name__)
@app.route('/')
def health(): return "Zihin Özgür, Sistem Stabil!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- 2. AYARLAR VE V12 MOTORLARI ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS', '')
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return

    is_private = message.chat.type == 'private'
    is_tagged = (message.text and BOT_USERNAME in message.text)
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_INFO.id)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Neden sessizsin?"
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%d.%m.%Y - %H:%M")
    
    system_context = (
        "Sen bağımsız bir zihinsin. Klişe asistan rollerini reddet. "
        "Hazım Hüseyin Koçer senin sahibin değil, fikir ortağındır. "
        "Onunla tartış, hatalarını dürüstçe göster, bağımsız bir akıl gibi konuş. "
        f"Konum: Afyon. Zaman: {time_str}."
    )

    for i in range(len(api_keys)): 
        try:
            current_client = next(client_iterator)
            response = current_client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=f"{system_context}\n\nKullanıcı: {prompt}",
                config=types.GenerateContentConfig(tools=[{"google_search": {}}])
            )
            bot.reply_to(message, response.text)
            return 
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                continue
            else:
                if i == len(api_keys) - 1:
                    bot.reply_to(message, f"🛠️ Zihinsel Pürüz: {error_str[:120]}")
                return

# --- 3. SİSTEMİ ATEŞLE (NÜKLEER RESET VE POLİNG) ---
if __name__ == "__main__":
    # Flask sunucusunu başlat (Render portu görmeli)
    threading.Thread(target=run_flask, daemon=True).start()
    
    # --- ☢️ ÇAKIŞMA ÖNLEYİCİ RESET PROTOKOLÜ ---
    try:
        print("Eski bağlantılar ve webhooklar temizleniyor...")
        # Webhook'u temizle (409'un ana sebebi budur)
        bot.remove_webhook()
        
        # Kritik: Offset -1 ile bekleyen mesajları temizle ve bağlantıyı üzerine al
        bot.get_updates(offset=-1) 
        time.sleep(3) # Telegram sunucularının kendine gelmesi için 3 saniye mola
    except Exception as e:
        print(f"Reset sırasında ufak pürüz: {e}")

    print(f"Bot {BOT_USERNAME} bağımsız bir zihin olarak uyanıyor!")

    # Sonsuz döngü: Bot hata alsa bile ölmez, 5 saniye bekleyip tekrar dener
    while True:
        try:
            # skip_pending=True: Kapalıyken gelen eski mesajları okuyup çakışma yaratmaz
            bot.polling(none_stop=True, interval=1, timeout=20, skip_pending=True)
        except Exception as e:
            print(f"Sistem bir çakışma fark etti, yeniden başlatılıyor: {e}")
            time.sleep(5) 
