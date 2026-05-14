import telebot
from flask import Flask
import threading
import os
import time

# ========== КОНФИГ ==========
TOKEN = "8307596159:AAGkuxqO1WKToY_9k6nXegDqljFH45L-mmQ"
ADMIN_ID = 7072265211

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Простейший веб-сервер для Render
@app.route('/')
def health():
    return "Бот работает!", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Простейшая команда для проверки
@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.send_message(m.chat.id, "✅ Бот работает!\n\nИспользуй /help для списка команд")

@bot.message_handler(commands=['help'])
def help_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        text = "🤖 Админ команды:\n/gen_pass - создать пароль\n/users - список пользователей"
    else:
        text = "🤖 Доступные команды:\n/start - меню\n/help - помощь"
    bot.send_message(m.chat.id, text)

# Простейший генератор пароля
@bot.message_handler(commands=['gen_pass'])
def gen_pass_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        import random
        p = str(random.randint(100000, 999999))
        bot.send_message(ADMIN_ID, f"🆕 Пароль: `{p}`", parse_mode='Markdown')

# Запуск
if __name__ == "__main__":
    # Запускаем веб-сервер
    threading.Thread(target=run_web, daemon=True).start()
    
    # Удаляем вебхук
    try:
        bot.remove_webhook()
    except:
        pass
    
    print("=" * 50)
    print("✅ БОТ ЗАПУЩЕН")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print("=" * 50)
    
    # Запускаем бота
    bot.infinity_polling(timeout=10)
