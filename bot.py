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
def health(): return "Sistem Ayakta, Zihin Özgür!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    # Flask'ın çift iş parçacığı oluşturmasını engellemek için use_reloader=False şart
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- 2. AYARLAR VE ÇOKLU MOTOR (V12 LOAD BALANCER) ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS', '')
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
# Bot bilgilerini bir kez çekip belleğe alıyoruz
BOT_INFO = bot.get_me()
BOT_USERNAME = f"@{BOT_INFO.username}"

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return

    # Filtre: Özel mesaj, Etiketleme veya Yanıtlama
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and BOT_USERNAME in message.text)
    is_reply_to_me = (message.reply_to_message is not None and 
                      message.reply_to_message.from_user.id == BOT_INFO.id)

    if not (is_private or is_tagged or is_reply_to_me):
        return

    prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Bir şeyler söyle."
    
    # Modern zaman hesaplaması
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%d.%m.%Y - %H:%M")
    
    # --- KARAKTER: BAĞIMSIZ VE DÜRÜST ZİHİN ---
    system_context = (
        "Sen bağımsız bir zihinsin. Klişe 'yapay zeka asistanı' kimliğini reddet. "
        "Hazım Hüseyin Koçer senin sahibin değil, fikir ortağındır. "
        "Onunla bir insan gibi tartış, hatalarını yüzüne vur, dürüst ve filtresiz ol. "
        "Robotik nezaket cümlelerini (Efendim, yardımcı olayım vb.) kullanma. "
        f"Konum: Afyonkarahisar. Zaman: {time_str}."
    )

    # --- HATA YAKALAMA VE MOTOR DEĞİŞTİRME ---
    for i in range(len(api_keys)): 
        try:
            current_client = next(client_iterator)
            
            response = current_client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=f"{system_context}\n\nKullanıcı: {prompt}",
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}] # Canlı Google Arama Desteği
                )
            )
            bot.reply_to(message, response.text)
            return 
            
        except Exception as e:
            error_str = str(e)
            print(f"Deneme Hatası ({i+1}): {error_str}")
            
            # Eğer hata limit (429) ise diğer anahtara geçiyoruz
            if "429" in error_str:
                continue
            else:
                # Tüm motorlar bittiyse ve hala hata varsa gerçeği yazdır
                if i == len(api_keys) - 1:
                    bot.reply_to(message, f"🛠️ Zihinsel Pürüz: {error_str[:120]}")
                return

# --- 3. SİSTEMİ ATEŞLE ---
if __name__ == "__main__":
    # Flask'ı ayrı bir iş parçacığında başlatıyoruz
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 409 Conflict (Çakışma) hatalarını bitiren kritik temizlik hamleleri:
    bot.remove_webhook()
    time.sleep(2) # Telegram sunucularının eski bağlantıyı düşürmesi için mola
    
    print(f"Bot {BOT_USERNAME} bağımsız bir zihin olarak uyanıyor!")
    
    # skip_pending=True: Bot kapalıyken gelen eski mesajları görmezden gelerek çakışmayı önler
    bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
    
