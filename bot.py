import telebot
from google import genai
from google.genai import types
from flask import Flask, request
import os
import time
from datetime import datetime, timedelta, timezone
import itertools

# --- 1. AYARLAR ---
TELE_TOKEN = os.environ.get('TELEGRAM_TOKEN')
keys_env = os.environ.get('GEMINI_KEYS') or os.environ.get('GEMINI_KEY') or ''
api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]

WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELE_TOKEN}"

# 2026'nın canavarı. Eğer çok 429 alırsan 'gemini-1.5-flash'a çekebilirsin.
MODEL_ID = 'gemini-2.0-flash' 

clients = [genai.Client(api_key=key) for key in api_keys]
client_iterator = itertools.cycle(clients)

bot = telebot.TeleBot(TELE_TOKEN)
app = Flask(__name__)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text and message.text.startswith('/'): return
    
    is_private = message.chat.type == 'private'
    is_tagged = (message.text and f"@{bot.get_me().username}" in message.text)
    is_reply_to_me = (message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id)

    if not (is_private or is_tagged or is_reply_to_me): return

    prompt = message.text.replace(f"@{bot.get_me().username}", "").strip()
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_str = tr_time.strftime("%H:%M")

    system_context = (
        "Sen Bomboclat'sın. Hazım'ın samimi ama eleştirel dostusun. "
        "Yapay zeka gibi değil, gerçek bir insan gibi konuş. "
        "Hazım'a karşı dürüst ol, gerekirse tartış. "
        "Zaman: " + time_str + " (Afyon). Bu bilgiyi sadece gerekirse kullan."
    )

    last_error = ""
    # Anahtar sayısı kadar deneme yapıyoruz
    for i in range(len(api_keys)):
        try:
            current_client = next(client_iterator)
            
            # İNTERNET ERİŞİMLİ ÜRETİM
            response = current_client.models.generate_content(
                model=MODEL_ID, 
                contents=f"{system_context}\n\nHazım: {prompt}",
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearchRetrieval())],
                    temperature=0.7 # Biraz daha insani ve değişken cevaplar için
                )
            )
            
            if response and response.text:
                bot.reply_to(message, response.text)
                return
                
        except Exception as e:
            last_error = str(e)
            print(f">> Motor {i+1} Hatası: {last_error[:50]}...", flush=True)
            
            if "429" in last_error:
                # Kota dolduysa 3 saniye bekle ve diğer anahtara geç
                time.sleep(3)
                continue
            elif "404" in last_error:
                # Model bulunamadıysa (ki düzelttik) hemen bildir
                bot.reply_to(message, "🛠️ Model ismi yine uçtu, Hazım bir kontrol et.")
                return
            
    # Eğer tüm anahtarlar biterse:
    bot.reply_to(message, f"🛠️ Google ablukası çok sert Hazım. Tüm anahtarlar 429 yedi.\n\n`Mevzu: {last_error[:50]}...` \n(Birkaç dakika sonra tekrar dene.)")

# Flask ve Webhook (Aynı kalıyor)
@app.route(f'/{TELE_TOKEN}', methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def main(): return "V27: Sabır ve Kurtarma Modu!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
