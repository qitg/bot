import telebot
from flask import Flask
import threading
import os
import time
import random

TOKEN = "8307596159:AAGkuxqO1WKToY_9k6nXegDqljFH45L-mmQ"
ADMIN_ID = 7072265211

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running!", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.send_message(m.chat.id, "✅ Bot is working!")

@bot.message_handler(commands=['help'])
def help_cmd(m):
    bot.send_message(m.chat.id, "Commands: /start, /help")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    try:
        bot.remove_webhook()
    except:
        pass
    print("Bot started")
    bot.infinity_polling(timeout=10)
