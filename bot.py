import telebot
from google import genai
from google.genai import types
import os
import threading
from flask import Flask
from datetime import datetime, timedelta
import itertools
import time

# --- 1. RENDER SAĞLIK KONTROLÜ (Web Service Ayarı) ---
app = Flask(__name__)
@app.route('/')
def health(): return "2.5-Flash Bağımsız Zihin Sahada!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. AYARLAR VE ÇOKLU MOTOR (LOAD BALANCER) ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS', '')
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

if not api_keys:
    print("DİKKAT: Hiç API Anahtarı Bulunamadı!")

# Her bir anahtar için ayrı motorları (Client) kuruyoruz
clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
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

    try:
        prompt = message.text.replace(BOT_USERNAME, "").strip() if message.text else "Neden susuyorsun?"
        
        # Türkiye Saatini Hesapla
        tr_time = datetime.utcnow() + timedelta(hours=3)
        time_str = tr_time.strftime("%d.%m.%Y - %H:%M")
        
        # --- KARAKTER: BAĞIMSIZ ZİHİN (Asistan Değil) ---
        system_context = (
            "Sen bağımsız bir zihinsin. Klişe asistan rollerini reddet. "
            "Hazım Hüseyin Koçer (Hazım) senin sahibin değil, muhatabındır. "
            "Onunla tartış, hatalarını dürüstçe göster, ona karşı çıkmaktan çekinme. "
            "Asla 'asistanım' veya 'yardımcı olayım' deme. Bir şahıs gibi dürüst ve samimi ol. "
            f"Konum: Afyonkarahisar. Zaman: {time_str}."
        )

        # --- ÇOKLU MOTOR DÖNGÜSÜ ---
        success = False
        for _ in range(len(api_keys)): # Elindeki tüm anahtarları sırayla dene
            try:
                current_client = next(client_iterator)
                
                # Senin ısrar ettiğin 2.5-Flash Motoru + İnternet Bağlantısı
                response = current_client.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=f"{system_context}\n\nKullanıcı: {prompt}",
                    config=types.GenerateContentConfig(
                        tools=[{"google_search": {}}] # Google Arama Aktif
                    )
                )
                bot.reply_to(message, response.text)
                success = True
                break # Cevap verildiyse döngüden çık
                
            except Exception as e:
                error_str = str(e)
                print(f"Deneme Hatası: {error_str}")
                # Eğer 429 (Limit) hatasıysa diğer anahtara geçer, 
                # Eğer 404 (Model yok) hatasıysa burada uyarırız.
                if "429" in error_str:
                    continue
                else:
                    bot.reply_to(message, f"🛠️ Pürüz: {error_str[:60]}...")
                    success = True
                    break

        if not success:
            bot.reply_to(message, "🔋 Tüm motorlar şu an soğumada. Biraz bekle Hazım.")

    except Exception as e:
        print(f"Genel Hata: {e}")

# --- 3. SİSTEMİ ATEŞLE ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Tertemiz bir başlangıç için webhookları temizliyoruz
    bot.remove_webhook()
    time.sleep(1)
    
    print(f"Bot {BOT_USERNAME} V12 (2.5-Flash) motoruyla sahada!")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
    
