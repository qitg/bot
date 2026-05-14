import telebot
from flask import Flask
import threading
import os
import time
import random
import json
from datetime import datetime, timedelta

TOKEN = "8307596159:AAGkuxqO1WKToY_9k6nXegDqljFH45L-mmQ"
ADMIN_ID = 7072265211

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Данные
user_access = {}
parole_active = []
DATA_FILE = "bot_data.json"

def load_data():
    global user_access, parole_active
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            user_access = data.get('access', {})
            parole_active = data.get('passwords', [])

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({'access': user_access, 'passwords': parole_active}, f)

def gen_parola():
    return str(random.randint(100000, 999999))

# Веб сервер для Render
@app.route('/')
def health():
    return "Bot is running!", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Меню
def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("🆕 Создать пароль", "📋 Список паролей")
    mk.row("🗑 Сброс паролей", "❓ Команды")
    return mk

def user_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("🎫 Купить билет", "❓ Команды")
    return mk

# Команды
@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    
    if str(uid) == str(ADMIN_ID):
        bot.send_message(uid, "🔐 Админ панель", reply_markup=admin_menu())
        return
    
    if user_access.get(str(uid), False):
        bot.send_message(uid, f"✅ Привет, {name}!\nНапиши номер автобуса (2000-2099)", reply_markup=user_menu())
    else:
        bot.send_message(uid, "🔑 Введи код доступа")
        bot.register_next_step_handler(m, check_code)

def check_code(m):
    uid = m.from_user.id
    code = m.text.strip()
    if code in parole_active:
        user_access[str(uid)] = True
        save_data()
        bot.send_message(uid, "✅ Доступ открыт!\nПиши номер автобуса (2000-2099)", reply_markup=user_menu())
    else:
        bot.send_message(uid, "❌ Неверный код!\nПопробуй ещё раз:")
        bot.register_next_step_handler(m, check_code)

@bot.message_handler(commands=['help'])
def help_cmd(m):
    uid = m.from_user.id
    if str(uid) == str(ADMIN_ID):
        text = "👑 Админ команды:\n/gen_pass - создать пароль\n/list_pass - список паролей\n/clear_pass - удалить пароли\n/users - список пользователей"
    else:
        text = "🎫 Доступные команды:\n/start - меню\n/help - помощь\n\nПросто напиши номер автобуса (2000-2099) чтобы купить билет"
    bot.send_message(m.chat.id, text)

@bot.message_handler(commands=['gen_pass'])
def gen_pass_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        p = gen_parola()
        parole_active.append(p)
        save_data()
        bot.send_message(ADMIN_ID, f"🆕 Пароль: {p}")

@bot.message_handler(commands=['list_pass'])
def list_pass_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        if parole_active:
            bot.send_message(ADMIN_ID, f"📋 Пароли: {', '.join(parole_active)}")
        else:
            bot.send_message(ADMIN_ID, "❌ Нет паролей")

@bot.message_handler(commands=['clear_pass'])
def clear_pass_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        parole_active.clear()
        save_data()
        bot.send_message(ADMIN_ID, "✅ Все пароли удалены")

@bot.message_handler(commands=['users'])
def users_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        if not user_access:
            bot.send_message(ADMIN_ID, "❌ Нет пользователей")
            return
        text = "👥 Пользователи:\n"
        for uid, access in user_access.items():
            if access:
                text += f"• ID: {uid}\n"
        bot.send_message(ADMIN_ID, text)

# Покупка билета
def issue_ticket(chat_id, cod):
    try:
        msg = bot.send_message(chat_id, "🔄 Обработка...")
        time.sleep(2)
        bot.delete_message(chat_id, msg.message_id)
        now = datetime.now()
        nr = random.randint(10000000, 99999999)
        
        ticket = f"{cod}\n{now.strftime('%I:%M %p').lstrip('0')}\n\nCererea dumneavoastră procesare.\n\nBiletul electronic nr. {nr}\n{now.strftime('%d.%m.%Y')}\nValabil 1 ora (de la {now.strftime('%H:%M')} Pret 6 MDL)\n\nNumarul de bord: {cod}"
        
        bot.send_message(chat_id, ticket, reply_markup=user_menu())
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == "🎫 Купить билет")
def buy_ticket_btn(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала введи код доступа через /start")
        return
    bot.send_message(uid, "🚌 Введи номер автобуса (2000-2099):", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, process_ticket)

def process_ticket(m):
    uid = m.from_user.id
    text = m.text.strip()
    
    if not text.isdigit() or len(text) != 4:
        bot.send_message(uid, "❌ Нужно 4 цифры (2000-2099)!", reply_markup=user_menu())
        return
    
    cod = int(text)
    if cod < 2000 or cod > 2099:
        bot.send_message(uid, f"❌ {cod} не в диапазоне 2000-2099", reply_markup=user_menu())
        return
    
    threading.Thread(target=issue_ticket, args=(uid, cod)).start()

@bot.message_handler(func=lambda m: m.text and m.text.isdigit() and len(m.text) == 4)
def direct_ticket(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала введи код доступа через /start")
        return
    
    cod = int(m.text)
    if 2000 <= cod <= 2099:
        threading.Thread(target=issue_ticket, args=(uid, cod)).start()
    else:
        bot.send_message(uid, f"❌ {cod} не в диапазоне 2000-2099", reply_markup=user_menu())

# Кнопки
@bot.message_handler(func=lambda m: m.text == "❓ Команды")
def commands_btn(m):
    help_cmd(m)

@bot.message_handler(func=lambda m: m.text == "🆕 Создать пароль" and str(m.from_user.id) == str(ADMIN_ID))
def gen_pass_btn(m):
    gen_pass_cmd(m)

@bot.message_handler(func=lambda m: m.text == "📋 Список паролей" and str(m.from_user.id) == str(ADMIN_ID))
def list_pass_btn(m):
    list_pass_cmd(m)

@bot.message_handler(func=lambda m: m.text == "🗑 Сброс паролей" and str(m.from_user.id) == str(ADMIN_ID))
def clear_pass_btn(m):
    clear_pass_cmd(m)

# Запуск
if __name__ == "__main__":
    load_data()
    threading.Thread(target=run_web, daemon=True).start()
    try:
        bot.remove_webhook()
    except:
        pass
    print("=" * 50)
    print("✅ БОТ ЗАПУЩЕН")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print("=" * 50)
    bot.infinity_polling(timeout=10)
