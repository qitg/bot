import telebot
import json
import os
import time
from datetime import datetime

# ========== КОНФИГ ВТОРОГО БОТА ==========
TOKEN2 = "8772267615:AAGSnmI663HSVIteA3I3v9HuuUm2zUBaVVA"
ADMIN_IDS = [7072265211]  # Твой ID

bot2 = telebot.TeleBot(TOKEN2)
DATA_FILE = "bot_data.json"  # Общий файл с основным ботом

def load_data():
    """Загружает данные из общего файла"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    """Сохраняет данные в общий файл"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def is_vip(user_id):
    """Проверяет есть ли у пользователя VIP"""
    data = load_data()
    user_vip = data.get('vip', {})
    uid = str(user_id)
    if uid not in user_vip:
        return False
    expiry = datetime.fromisoformat(user_vip[uid])
    return datetime.now() < expiry

def get_vip_expiry(user_id):
    """Возвращает дату окончания VIP"""
    data = load_data()
    user_vip = data.get('vip', {})
    uid = str(user_id)
    if uid not in user_vip:
        return None
    return datetime.fromisoformat(user_vip[uid])

@bot2.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        text = f"💎 Привет, {name}!\n\n✅ У тебя есть VIP статус\n📅 Действует до: {expiry.strftime('%d.%m.%Y')}\n\n🎫 Основной бот: @transport_moldova_bot"
    else:
        text = f"⭐ Привет, {name}!\n\n❌ У тебя нет VIP статуса\n\n💰 Купи VIP за 25 лей/неделя:\n/buy_vip\n\n🎫 Основной бот: @transport_moldova_bot"
    
    bot2.reply_to(m, text)

@bot2.message_handler(commands=['buy_vip'])
def buy_vip_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    username = m.from_user.username
    
    # Проверяем нет ли уже VIP
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        bot2.reply_to(m, f"💎 У тебя уже есть VIP до {expiry.strftime('%d.%m.%Y')}")
        return
    
    # Отправляем заявку админам
    for admin_id in ADMIN_IDS:
        try:
            bot2.send_message(admin_id, 
                f"🟢 **НОВАЯ ЗАЯВКА НА VIP**\n\n"
                f"👤 Пользователь: {name}\n"
                f"🆔 ID: `{uid}`\n"
                f"📝 Username: @{username if username else 'нет'}\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                f"✅ Чтобы выдать VIP в основном боте:\n`/give_vip {uid} 7`",
                parse_mode='Markdown')
        except Exception as e:
            print(f"Ошибка отправки админу: {e}")
    
    # Отправляем ответ пользователю
    bot2.reply_to(m, 
        f"💎 **ЗАЯВКА ОТПРАВЛЕНА!**\n\n"
        f"💰 Цена: 25 лей\n"
        f"📅 Длительность: 7 дней\n"
        f"🎫 Преимущества:\n"
        f"• 10 билетов в день\n"
        f"• Без кулдауна\n\n"
        f"📩 Админ свяжется с тобой\n\n"
        f"🎫 Основной бот: @transport_moldova_bot",
        parse_mode='Markdown')

@bot2.message_handler(commands=['status'])
def status_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        days_left = (expiry - datetime.now()).days
        text = f"💎 **VIP СТАТУС**\n\n👤 {name}\n📅 Действует до: {expiry.strftime('%d.%m.%Y')}\n⏰ Осталось дней: {days_left}\n✅ Статус: АКТИВЕН"
    else:
        text = f"⭐ **ОБЫЧНЫЙ СТАТУС**\n\n👤 {name}\n❌ VIP: НЕТ\n💰 Купи VIP: /buy_vip"
    
    bot2.reply_to(m, text, parse_mode='Markdown')

@bot2.message_handler(commands=['help'])
def help_cmd(m):
    text = """
🤖 **БОТ-ПОМОЩНИК VIP**

📋 **Доступные команды:**

/start - Главное меню
/help - Этот список
/status - Проверить статус VIP
/buy_vip - Купить VIP

💎 **VIP даёт:**
• 10 билетов в день
• Без кулдауна
• Приоритетная поддержка

💰 **Цена:** 25 лей/неделя

🎫 **Основной бот:** @transport_moldova_bot
"""
    bot2.reply_to(m, text)

@bot2.message_handler(func=lambda m: True)
def echo_all(m):
    bot2.reply_to(m, "❓ Неизвестная команда\n\nИспользуй /help для списка команд")

# Запуск
if __name__ == "__main__":
    print("=" * 50)
    print("✅ ВТОРОЙ БОТ ЗАПУЩЕН")
    print(f"👑 Уведомления будут отправляться админам: {ADMIN_IDS}")
    print(f"🤖 Имя бота: @transport_helper_bot")
    print("=" * 50)
    
    try:
        bot2.remove_webhook()
    except:
        pass
    
    bot2.infinity_polling(timeout=10)
