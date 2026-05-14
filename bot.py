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

# Константы
PRET = 6
VIP_PRICE = 25
VIP_DAYS = 7
NORMAL_DAILY_LIMIT = 3
NORMAL_COOLDOWN_HOURS = 3

# Данные
user_access = {}
user_cooldown = {}
parole_active = []
user_stats = {}
user_vip = {}
user_daily_tickets = {}
user_names = {}  # Сохраняем username или имя пользователя
DATA_FILE = "bot_data.json"

def get_time():
    return datetime.now()

def load_data():
    global user_access, user_cooldown, parole_active, user_stats, user_vip, user_daily_tickets, user_names
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            user_access = data.get('access', {})
            user_cooldown = data.get('cooldown', {})
            parole_active = data.get('passwords', [])
            user_stats = data.get('stats', {})
            user_vip = data.get('vip', {})
            user_daily_tickets = data.get('daily_tickets', {})
            user_names = data.get('names', {})

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'access': user_access,
            'cooldown': user_cooldown,
            'passwords': parole_active,
            'stats': user_stats,
            'vip': user_vip,
            'daily_tickets': user_daily_tickets,
            'names': user_names
        }, f)

def gen_parola():
    return str(random.randint(100000, 999999))

def is_vip(user_id):
    uid = str(user_id)
    if uid not in user_vip:
        return False
    expiry = datetime.fromisoformat(user_vip[uid])
    return get_time() < expiry

def get_vip_expiry(user_id):
    uid = str(user_id)
    if uid not in user_vip:
        return None
    return datetime.fromisoformat(user_vip[uid])

def set_vip(user_id, days=VIP_DAYS):
    uid = str(user_id)
    expiry = get_time() + timedelta(days=days)
    user_vip[uid] = expiry.isoformat()
    save_data()
    # Получаем имя пользователя для уведомления
    name = user_names.get(uid, {}).get('name', f'ID:{uid}')
    bot.send_message(ADMIN_ID, f"✅ VIP выдан пользователю {name} до {expiry.strftime('%d.%m.%Y')}")

def remove_vip(user_id):
    uid = str(user_id)
    if uid in user_vip:
        del user_vip[uid]
        save_data()

def check_expired_vip():
    """Проверяет и удаляет просроченный VIP"""
    now = get_time()
    expired = []
    for uid, expiry_str in user_vip.items():
        expiry = datetime.fromisoformat(expiry_str)
        if expiry <= now:
            expired.append(uid)
    for uid in expired:
        del user_vip[uid]
        try:
            bot.send_message(int(uid), "⏰ Ваш VIP статус истёк. Купите новый через /buy_vip")
        except:
            pass
    if expired:
        save_data()
        bot.send_message(ADMIN_ID, f"⏰ VIP истёк у {len(expired)} пользователей")
    return len(expired)

def get_daily_tickets_count(user_id):
    uid = str(user_id)
    today = get_time().strftime('%Y-%m-%d')
    if uid not in user_daily_tickets:
        return 0
    if user_daily_tickets[uid].get('date') != today:
        return 0
    return user_daily_tickets[uid].get('count', 0)

def increment_daily_tickets(user_id):
    uid = str(user_id)
    today = get_time().strftime('%Y-%m-%d')
    if uid not in user_daily_tickets:
        user_daily_tickets[uid] = {'count': 0, 'date': today}
    if user_daily_tickets[uid]['date'] != today:
        user_daily_tickets[uid] = {'count': 0, 'date': today}
    user_daily_tickets[uid]['count'] += 1
    save_data()

def check_can_buy_ticket(user_id):
    # VIP может 10 билетов в день без кулдауна
    if is_vip(user_id):
        daily_count = get_daily_tickets_count(user_id)
        if daily_count >= 10:
            return False, "❌ У VIP лимит 10 билетов в день. Завтра будут новые!"
        return True, 0
    
    # Админ без ограничений
    if str(user_id) == str(ADMIN_ID):
        return True, 0
    
    # Проверка кулдауна (3 часа)
    last = user_cooldown.get(str(user_id))
    if last:
        last_time = datetime.fromisoformat(last)
        now = get_time()
        passed = now - last_time
        if passed < timedelta(hours=NORMAL_COOLDOWN_HOURS):
            remaining = timedelta(hours=NORMAL_COOLDOWN_HOURS) - passed
            return False, int(remaining.total_seconds() // 60)
    
    # Проверка дневного лимита (3 билета)
    daily_count = get_daily_tickets_count(user_id)
    if daily_count >= NORMAL_DAILY_LIMIT:
        return False, 0
    
    return True, 0

def set_cooldown(user_id):
    user_cooldown[str(user_id)] = get_time().isoformat()
    save_data()

def update_stats(user_id):
    uid = str(user_id)
    if uid not in user_stats:
        user_stats[uid] = {'tickets': 0}
    user_stats[uid]['tickets'] += 1
    save_data()

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
    mk.row("💎 Выдать VIP", "📢 Рассылка")
    mk.row("📊 Статистика", "👥 Пользователи")
    mk.row("🗑 Сброс паролей", "❓ Команды")
    return mk

def user_menu(uid):
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    if is_vip(uid):
        daily_count = get_daily_tickets_count(uid)
        mk.row(f"🎫 Купить билет ({daily_count}/10 сегодня)")
        mk.row("💎 Мой VIP", "⏰ Мой статус")
    else:
        daily_count = get_daily_tickets_count(uid)
        mk.row(f"🎫 Купить билет ({daily_count}/{NORMAL_DAILY_LIMIT} сегодня)")
        mk.row("⭐ Купить VIP", "⏰ Мой статус")
    mk.row("❓ Команды")
    return mk

# Команды
@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    username = m.from_user.username
    
    # Сохраняем имя пользователя
    user_names[str(uid)] = {'name': name, 'username': username}
    save_data()
    
    if str(uid) == str(ADMIN_ID):
        bot.send_message(uid, "🔐 Админ панель", reply_markup=admin_menu())
        return
    
    if user_access.get(str(uid), False):
        msg = f"✅ Привет, {name}!\n\n"
        if is_vip(uid):
            expiry = get_vip_expiry(uid)
            msg += f"💎 Ты VIP до {expiry.strftime('%d.%m.%Y')}\n"
            msg += f"🎫 Сегодня использовано: {get_daily_tickets_count(uid)}/10 билетов"
        else:
            msg += f"⭐ Обычный режим: {NORMAL_DAILY_LIMIT} билетов в день, кулдаун {NORMAL_COOLDOWN_HOURS} часа\n"
            msg += f"🎫 Сегодня использовано: {get_daily_tickets_count(uid)}/{NORMAL_DAILY_LIMIT}\n\n"
            msg += "Купи VIP за 25 лей/неделя!\nНапиши /buy_vip"
        bot.send_message(uid, msg, reply_markup=user_menu(uid))
    else:
        bot.send_message(uid, "🔑 Введи код доступа\n\nКод у @RaskovskI")
        bot.register_next_step_handler(m, check_code)

def check_code(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    code = m.text.strip()
    if code in parole_active:
        user_access[str(uid)] = True
        if str(uid) not in user_stats:
            user_stats[str(uid)] = {'tickets': 0}
        save_data()
        bot.send_message(uid, f"✅ Доступ открыт!\n\n⭐ Обычный режим: {NORMAL_DAILY_LIMIT} билетов/день, кулдаун {NORMAL_COOLDOWN_HOURS} часа\n\nКупи VIP за {VIP_PRICE} лей/неделя!\nНапиши /buy_vip", reply_markup=user_menu(uid))
        bot.send_message(ADMIN_ID, f"🔓 Новый пользователь: {name} (ID: {uid})")
    else:
        bot.send_message(uid, "❌ Неверный код!\nПопробуй ещё раз:")
        bot.register_next_step_handler(m, check_code)

@bot.message_handler(commands=['help'])
def help_cmd(m):
    uid = m.from_user.id
    if str(uid) == str(ADMIN_ID):
        text = """
👑 **АДМИН КОМАНДЫ:**

/gen_pass - Создать пароль
/list_pass - Список паролей
/clear_pass - Удалить все пароли
/users - Список пользователей
/stats - Статистика
/vip_list - Список VIP

💎 **Управление VIP:**
/give_vip <ID или @username> <дни> - Выдать VIP
/remove_vip <ID или @username> - Снять VIP

📢 **Рассылка:**
/ad <текст> - Рассылка всем пользователям

📌 Примеры:
/give_vip 7072265211 7
/give_vip @username 7
/remove_vip @username
"""
    else:
        daily = get_daily_tickets_count(uid)
        limit = NORMAL_DAILY_LIMIT if not is_vip(uid) else 10
        text = f"""
🤖 **ДОСТУПНЫЕ КОМАНДЫ:**

/start - Главное меню
/help - Этот список
/status - Мой статус
/buy_vip - Купить VIP

🎫 **Как купить билет:**
Просто напиши номер автобуса (2000-2099)

📊 **Твой статус:**
Сегодня использовано: {daily}/{limit}

💎 VIP: 10 билетов/день, без кулдауна - 25 лей/неделя
"""
    bot.send_message(uid, text, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status_cmd(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала введи код доступа через /start")
        return
    
    daily = get_daily_tickets_count(uid)
    
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        text = f"""
💎 **VIP СТАТУС**

📅 Действует до: {expiry.strftime('%d.%m.%Y')}
🎫 Осталось билетов сегодня: {10 - daily}
⏰ Кулдаун: отсутствует
💰 Цена билета: {PRET} лей
"""
    else:
        last = user_cooldown.get(str(uid))
        cooldown_text = "✅ Можешь купить билет"
        if last:
            last_time = datetime.fromisoformat(last)
            now = get_time()
            passed = now - last_time
            if passed < timedelta(hours=NORMAL_COOLDOWN_HOURS):
                remaining = timedelta(hours=NORMAL_COOLDOWN_HOURS) - passed
                hours = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                cooldown_text = f"⏰ Кулдаун: {hours}ч {mins}мин"
        
        text = f"""
⭐ **ОБЫЧНЫЙ РЕЖИМ**

📅 Сегодня использовано: {daily}/{NORMAL_DAILY_LIMIT}
{cooldown_text}
💰 Цена билета: {PRET} лей

💎 Купи VIP за {VIP_PRICE} лей/неделя!
Напиши /buy_vip
"""
    bot.send_message(uid, text, parse_mode='Markdown')

@bot.message_handler(commands=['buy_vip'])
def buy_vip_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    username = m.from_user.username
    
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала введи код доступа через /start")
        return
    
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        bot.send_message(uid, f"💎 У тебя уже есть VIP до {expiry.strftime('%d.%m.%Y')}")
        return
    
    # Отправляем админу заявку
    bot.send_message(ADMIN_ID, 
        f"🟢 **НОВАЯ ЗАЯВКА НА VIP**\n\n"
        f"👤 Пользователь: {name}\n"
        f"🆔 ID: {uid}\n"
        f"📝 Username: @{username if username else 'нет'}\n"
        f"💰 Сумма: {VIP_PRICE} лей\n"
        f"📅 Дней: {VIP_DAYS}\n\n"
        f"✅ Чтобы выдать VIP:\n/give_vip {uid} {VIP_DAYS}\nили\n/give_vip @{username} {VIP_DAYS}",
        parse_mode='Markdown')
    
    # Отправляем пользователю
    bot.send_message(uid, 
        f"💎 **VIP СТАТУС**\n\n"
        f"💰 Цена: {VIP_PRICE} лей\n"
        f"📅 Длительность: {VIP_DAYS} дней\n"
        f"🎫 Преимущества:\n"
        f"• 10 билетов в день\n"
        f"• Без кулдауна\n"
        f"• Приоритетная поддержка\n\n"
        f"📩 **Свяжись с админом:** @RaskovskI\n\n"
        f"После оплаты админ активирует VIP:\n/give_vip {uid} {VIP_DAYS}",
        parse_mode='Markdown')

# ========== АДМИН КОМАНДЫ ==========

def find_user_id_by_username(username):
    """Находит ID пользователя по username"""
    clean_username = username.replace('@', '').lower()
    for uid, data in user_names.items():
        if data.get('username') and data.get('username').lower() == clean_username:
            return int(uid)
    return None

@bot.message_handler(commands=['give_vip'])
def give_vip_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(ADMIN_ID, "❌ Используй:\n/give_vip ID дни\n/give_vip @username дни\n\nПримеры:\n/give_vip 7072265211 7\n/give_vip @BotFather 7")
            return
        
        user_input = parts[1]
        days = int(parts[2]) if len(parts) > 2 else VIP_DAYS
        
        # Определяем ID пользователя
        if user_input.startswith('@'):
            # Это username
            user_id = find_user_id_by_username(user_input)
            if not user_id:
                bot.send_message(ADMIN_ID, f"❌ Пользователь {user_input} не найден в базе.\nПользователь должен хотя бы раз написать /start")
                return
        else:
            # Это ID
            user_id = int(user_input)
        
        set_vip(user_id, days)
        
        # Получаем имя пользователя
        user_info = user_names.get(str(user_id), {})
        name = user_info.get('name', f'ID:{user_id}')
        
        bot.send_message(ADMIN_ID, f"✅ VIP выдан пользователю {name} на {days} дней\nДо: {(get_time() + timedelta(days=days)).strftime('%d.%m.%Y')}")
        
        try:
            bot.send_message(user_id, 
                f"💎 **VIP СТАТУС АКТИВИРОВАН!**\n\n"
                f"📅 Действует до: {(get_time() + timedelta(days=days)).strftime('%d.%m.%Y')}\n"
                f"🎫 Теперь у тебя: 10 билетов в день\n"
                f"⏰ Без кулдауна!\n\n"
                f"Напиши /start чтобы увидеть изменения",
                parse_mode='Markdown')
        except:
            pass
            
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['remove_vip'])
def remove_vip_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(ADMIN_ID, "❌ Используй: /remove_vip ID или /remove_vip @username")
            return
        
        user_input = parts[1]
        
        # Определяем ID пользователя
        if user_input.startswith('@'):
            user_id = find_user_id_by_username(user_input)
            if not user_id:
                bot.send_message(ADMIN_ID, f"❌ Пользователь {user_input} не найден")
                return
        else:
            user_id = int(user_input)
        
        remove_vip(user_id)
        bot.send_message(ADMIN_ID, f"✅ VIP снят с пользователя {user_input}")
        try:
            bot.send_message(user_id, "⏰ Ваш VIP статус был снят администратором")
        except:
            pass
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка: {e}")

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
        text = "👥 **СПИСОК ПОЛЬЗОВАТЕЛЕЙ:**\n\n"
        for uid, access in user_access.items():
            if access:
                stats = user_stats.get(uid, {})
                tickets = stats.get('tickets', 0)
                vip = "💎" if is_vip(int(uid)) else "⭐"
                name = user_names.get(uid, {}).get('name', 'Unknown')
                text += f"{vip} {name} - {tickets} билетов (ID: {uid})\n"
        bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def stats_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        active_users = len([u for u in user_access if user_access[u]])
        vip_count = len([u for u in user_vip if datetime.fromisoformat(user_vip[u]) > get_time()])
        total_tickets = sum([stats.get('tickets', 0) for stats in user_stats.values()])
        
        text = f"""
📊 **СТАТИСТИКА**

👥 Пользователей: {active_users}
💎 VIP: {vip_count}
🎫 Всего билетов: {total_tickets}
💰 Выручка: {total_tickets * PRET} MDL

⭐ Обычный лимит: {NORMAL_DAILY_LIMIT} билетов/день
⏰ Обычный кулдаун: {NORMAL_COOLDOWN_HOURS} часа
💎 VIP: 10 билетов/день, без кулдауна
💎 VIP цена: {VIP_PRICE} лей/{VIP_DAYS} дней
"""
        bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

@bot.message_handler(commands=['vip_list'])
def vip_list_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        text = "💎 **VIP ПОЛЬЗОВАТЕЛИ:**\n\n"
        count = 0
        for uid, expiry_str in user_vip.items():
            expiry = datetime.fromisoformat(expiry_str)
            if expiry > get_time():
                name = user_names.get(uid, {}).get('name', f'ID:{uid}')
                days_left = (expiry - get_time()).days
                hours_left = (expiry - get_time()).seconds // 3600
                text += f"• {name} - осталось {days_left} дн {hours_left} ч\n"
                count += 1
        if count == 0:
            text = "❌ Нет активных VIP пользователей"
        bot.send_message(ADMIN_ID, text)

@bot.message_handler(commands=['ad'])
def ad_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    msg = bot.send_message(ADMIN_ID, "✏️ Введи текст для рассылки:")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(m):
    ad_text = m.text
    sent = 0
    for uid, access in user_access.items():
        if access:
            try:
                bot.send_message(int(uid), f"📢 **РАССЫЛКА**\n\n{ad_text}", parse_mode='Markdown')
                sent += 1
                time.sleep(0.05)
            except:
                pass
    bot.send_message(ADMIN_ID, f"✅ Рассылка отправлена {sent} пользователям")

# Покупка билета
def issue_ticket(chat_id, user_id, cod):
    try:
        msg = bot.send_message(chat_id, "🔄 Cererea dumneavoastră este în curs de procesare...")
        time.sleep(2)
        bot.delete_message(chat_id, msg.message_id)
        now = get_time()
        nr = random.randint(10000000, 99999999)
        
        # Сохраняем билет
        update_stats(user_id)
        increment_daily_tickets(user_id)
        if not is_vip(user_id) and str(user_id) != str(ADMIN_ID):
            set_cooldown(user_id)
        
        ticket = f"{cod}\n{now.strftime('%I:%M %p').lstrip('0')}\n\nCererea dumneavoastră procesare.\n\nBiletul electronic nr. {nr}\n{now.strftime('%d.%m.%Y')}\nValabil 1 ora (de la {now.strftime('%H:%M')} Pret {PRET} MDL)\n\nNumarul de bord: {cod}"
        
        bot.send_message(chat_id, ticket, reply_markup=user_menu(user_id))
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
        bot.send_message(uid, "❌ Нужно 4 цифры (2000-2099)!", reply_markup=user_menu(uid))
        return
    
    cod = int(text)
    if cod < 2000 or cod > 2099:
        bot.send_message(uid, f"❌ {cod} не в диапазоне 2000-2099", reply_markup=user_menu(uid))
        return
    
    can, msg = check_can_buy_ticket(uid)
    if not can:
        bot.send_message(uid, msg, reply_markup=user_menu(uid))
        return
    
    threading.Thread(target=issue_ticket, args=(uid, uid, cod)).start()

@bot.message_handler(func=lambda m: m.text and m.text.isdigit() and len(m.text) == 4)
def direct_ticket(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала введи код доступа через /start")
        return
    
    cod = int(m.text)
    if 2000 <= cod <= 2099:
        can, msg = check_can_buy_ticket(uid)
        if not can:
            bot.send_message(uid, msg, reply_markup=user_menu(uid))
            return
        threading.Thread(target=issue_ticket, args=(uid, uid, cod)).start()
    else:
        bot.send_message(uid, f"❌ {cod} не в диапазоне 2000-2099", reply_markup=user_menu(uid))

# Кнопки админа
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

@bot.message_handler(func=lambda m: m.text == "💎 Выдать VIP" and str(m.from_user.id) == str(ADMIN_ID))
def give_vip_btn(m):
    bot.send_message(ADMIN_ID, "💎 Используй команду:\n/give_vip @username дни\n\nПример: /give_vip @username 7\n\nИли по ID:\n/give_vip 7072265211 7")

@bot.message_handler(func=lambda m: m.text == "📢 Рассылка" and str(m.from_user.id) == str(ADMIN_ID))
def ad_btn(m):
    ad_cmd(m)

@bot.message_handler(func=lambda m: m.text == "📊 Статистика" and str(m.from_user.id) == str(ADMIN_ID))
def stats_btn(m):
    stats_cmd(m)

@bot.message_handler(func=lambda m: m.text == "👥 Пользователи" and str(m.from_user.id) == str(ADMIN_ID))
def users_btn(m):
    users_cmd(m)

# Кнопки пользователя
@bot.message_handler(func=lambda m: m.text == "⭐ Купить VIP")
def buy_vip_btn(m):
    buy_vip_cmd(m)

@bot.message_handler(func=lambda m: m.text == "💎 Мой VIP" or m.text == "⏰ Мой статус")
def status_btn(m):
    status_cmd(m)

# Запуск
if __name__ == "__main__":
    load_data()
    
    # Проверяем просроченный VIP при запуске
    expired_count = check_expired_vip()
    if expired_count > 0:
        print(f"Удалено просроченных VIP: {expired_count}")
    
    # Запускаем фоновую проверку VIP каждые 6 часов
    def vip_checker():
        while True:
            time.sleep(21600)  # 6 часов
            check_expired_vip()
    threading.Thread(target=vip_checker, daemon=True).start()
    
    # Запускаем веб-сервер
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
