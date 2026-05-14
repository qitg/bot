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

PRET = 6
VIP_PRICE = 25
VIP_DAYS = 7
NORMAL_DAILY_LIMIT = 3
NORMAL_COOLDOWN_HOURS = 3

user_access = {}
user_cooldown = {}
parole_active = []
user_stats = {}
user_vip = {}
user_daily_tickets = {}
user_names = {}
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
    name = user_names.get(uid, {}).get('name', f'ID:{uid}')
    bot.send_message(ADMIN_ID, f"✅ VIP выдан пользователю {name} до {expiry.strftime('%d.%m.%Y')}")

def remove_vip(user_id):
    uid = str(user_id)
    if uid in user_vip:
        del user_vip[uid]
        save_data()

def check_expired_vip():
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
    if is_vip(user_id):
        daily_count = get_daily_tickets_count(user_id)
        if daily_count >= 10:
            return False, 0, "VIP лимит 10 билетов в день"
        return True, 0, ""
    if str(user_id) == str(ADMIN_ID):
        return True, 0, ""
    last = user_cooldown.get(str(user_id))
    if last:
        last_time = datetime.fromisoformat(last)
        now = get_time()
        passed = now - last_time
        if passed < timedelta(hours=NORMAL_COOLDOWN_HOURS):
            remaining = timedelta(hours=NORMAL_COOLDOWN_HOURS) - passed
            minutes = int(remaining.total_seconds() // 60)
            return False, minutes, ""
    daily_count = get_daily_tickets_count(user_id)
    if daily_count >= NORMAL_DAILY_LIMIT:
        return False, 0, f"Лимит {NORMAL_DAILY_LIMIT} билетов в день"
    return True, 0, ""

def set_cooldown(user_id):
    user_cooldown[str(user_id)] = get_time().isoformat()
    save_data()

def update_stats(user_id):
    uid = str(user_id)
    if uid not in user_stats:
        user_stats[uid] = {'tickets': 0}
    user_stats[uid]['tickets'] += 1
    save_data()

@app.route('/')
def health():
    return "Bot is running!", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

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
        mk.row(f"🎫 Купить билет ({daily_count}/10)")
        mk.row("💎 Мой VIP", "⏰ Мой статус")
    else:
        daily_count = get_daily_tickets_count(uid)
        mk.row(f"🎫 Купить билет ({daily_count}/{NORMAL_DAILY_LIMIT})")
        mk.row("⭐ Купить VIP", "⏰ Мой статус")
    mk.row("❓ Команды")
    return mk

def back_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("🔙 Назад")
    return mk

@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    username = m.from_user.username
    user_names[str(uid)] = {'name': name, 'username': username}
    save_data()
    if str(uid) == str(ADMIN_ID):
        bot.send_message(uid, "Админ панель", reply_markup=admin_menu())
        return
    if user_access.get(str(uid), False):
        msg = f"Привет, {name}!\n\n"
        if is_vip(uid):
            expiry = get_vip_expiry(uid)
            msg += f"VIP до {expiry.strftime('%d.%m.%Y')}\n"
            msg += f"Сегодня: {get_daily_tickets_count(uid)}/10 билетов"
        else:
            msg += f"Обычный: {NORMAL_DAILY_LIMIT} билетов/день, кулдаун {NORMAL_COOLDOWN_HOURS} ч\n"
            msg += f"Сегодня: {get_daily_tickets_count(uid)}/{NORMAL_DAILY_LIMIT}\n\nКупи VIP: /buy_vip"
        bot.send_message(uid, msg, reply_markup=user_menu(uid))
    else:
        bot.send_message(uid, "Введи код доступа")
        bot.register_next_step_handler(m, check_code)

def check_code(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    code = m.text.strip()
    if code in parole_active:
        user_access[str(uid)] = True
        parole_active.remove(code)
        if str(uid) not in user_stats:
            user_stats[str(uid)] = {'tickets': 0}
        save_data()
        bot.send_message(uid, f"Доступ открыт!\n\nОбычный: {NORMAL_DAILY_LIMIT} билетов/день, кулдаун {NORMAL_COOLDOWN_HOURS} ч\nКупи VIP: /buy_vip", reply_markup=user_menu(uid))
        bot.send_message(ADMIN_ID, f"Новый пользователь: {name} (ID: {uid})")
    else:
        bot.send_message(uid, "Неверный код! Попробуй ещё:")
        bot.register_next_step_handler(m, check_code)

@bot.message_handler(commands=['help'])
def help_cmd(m):
    uid = m.from_user.id
    if str(uid) == str(ADMIN_ID):
        text = "Админ команды:\n/gen_pass - пароль\n/list_pass - список\n/clear_pass - удалить\n/users - список\n/stats - статистика\n/vip_list - список VIP\n/give_vip ID дни - выдать VIP\n/remove_vip ID - снять VIP\n/ad текст - рассылка"
    else:
        daily = get_daily_tickets_count(uid)
        limit = NORMAL_DAILY_LIMIT if not is_vip(uid) else 10
        text = f"Команды:\n/start - меню\n/help - помощь\n/status - статус\n/buy_vip - купить VIP\n\nБилет: напиши номер (2000-2099)\n\nСегодня: {daily}/{limit}"
    bot.send_message(uid, text)

@bot.message_handler(commands=['status'])
def status_cmd(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "Сначала /start", reply_markup=back_menu())
        return
    daily = get_daily_tickets_count(uid)
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        text = f"VIP статус\nДо: {expiry.strftime('%d.%m.%Y')}\nОсталось: {10-daily}/10\nКулдаун: нет\nЦена: {PRET} лей"
    else:
        last = user_cooldown.get(str(uid))
        cooldown_text = "Можешь купить"
        if last:
            last_time = datetime.fromisoformat(last)
            passed = get_time() - last_time
            if passed < timedelta(hours=NORMAL_COOLDOWN_HOURS):
                remaining = timedelta(hours=NORMAL_COOLDOWN_HOURS) - passed
                minutes = int(remaining.total_seconds() // 60)
                hours = minutes // 60
                mins = minutes % 60
                if hours > 0:
                    cooldown_text = f"Кулдаун: {hours}ч {mins}мин"
                else:
                    cooldown_text = f"Кулдаун: {mins}мин"
                available = last_time + timedelta(hours=NORMAL_COOLDOWN_HOURS)
                cooldown_text += f"\nДоступен в {available.strftime('%H:%M')}"
        text = f"Обычный режим\nСегодня: {daily}/{NORMAL_DAILY_LIMIT}\n{cooldown_text}\nЦена: {PRET} лей\n\nКупи VIP: /buy_vip"
    bot.send_message(uid, text, reply_markup=user_menu(uid))

@bot.message_handler(commands=['buy_vip'])
def buy_vip_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    username = m.from_user.username
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "Сначала /start", reply_markup=back_menu())
        return
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        bot.send_message(uid, f"У тебя уже есть VIP до {expiry.strftime('%d.%m.%Y')}", reply_markup=user_menu(uid))
        return
    bot.send_message(ADMIN_ID, f"Заявка на VIP\nПользователь: {name}\nID: {uid}\nUsername: @{username if username else 'нет'}\nВыдать: /give_vip {uid} {VIP_DAYS}")
    bot.send_message(uid, f"VIP статус\nЦена: {VIP_PRICE} лей\nДней: {VIP_DAYS}\n10 билетов/день, без кулдауна\n\nСвяжись с админом для оплаты", reply_markup=back_menu())

def find_user_id_by_username(username):
    clean = username.replace('@', '').lower()
    for uid, data in user_names.items():
        if data.get('username') and data.get('username').lower() == clean:
            return int(uid)
    return None

@bot.message_handler(commands=['give_vip'])
def give_vip_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(ADMIN_ID, "Используй: /give_vip ID дни или /give_vip @username дни")
            return
        user_input = parts[1]
        days = int(parts[2]) if len(parts) > 2 else VIP_DAYS
        if user_input.startswith('@'):
            user_id = find_user_id_by_username(user_input)
            if not user_id:
                bot.send_message(ADMIN_ID, f"Пользователь {user_input} не найден")
                return
        else:
            user_id = int(user_input)
        set_vip(user_id, days)
        name = user_names.get(str(user_id), {}).get('name', user_id)
        bot.send_message(ADMIN_ID, f"VIP выдан {name} на {days} дней")
        try:
            bot.send_message(user_id, f"VIP активирован на {days} дней!\nДо: {(get_time() + timedelta(days=days)).strftime('%d.%m.%Y')}", reply_markup=user_menu(user_id))
        except:
            pass
    except Exception as e:
        bot.send_message(ADMIN_ID, f"Ошибка: {e}")

@bot.message_handler(commands=['remove_vip'])
def remove_vip_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(ADMIN_ID, "Используй: /remove_vip ID или /remove_vip @username")
            return
        user_input = parts[1]
        if user_input.startswith('@'):
            user_id = find_user_id_by_username(user_input)
            if not user_id:
                bot.send_message(ADMIN_ID, f"Пользователь {user_input} не найден")
                return
        else:
            user_id = int(user_input)
        remove_vip(user_id)
        bot.send_message(ADMIN_ID, f"VIP снят с {user_input}")
        try:
            bot.send_message(user_id, "VIP статус снят администратором", reply_markup=user_menu(user_id))
        except:
            pass
    except Exception as e:
        bot.send_message(ADMIN_ID, f"Ошибка: {e}")

@bot.message_handler(commands=['gen_pass'])
def gen_pass_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        p = gen_parola()
        parole_active.append(p)
        save_data()
        bot.send_message(ADMIN_ID, f"Пароль: {p}")

@bot.message_handler(commands=['list_pass'])
def list_pass_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        if parole_active:
            bot.send_message(ADMIN_ID, f"Пароли: {', '.join(parole_active)}")
        else:
            bot.send_message(ADMIN_ID, "Нет паролей")

@bot.message_handler(commands=['clear_pass'])
def clear_pass_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        parole_active.clear()
        save_data()
        bot.send_message(ADMIN_ID, "Все пароли удалены")

@bot.message_handler(commands=['users'])
def users_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        if not user_access:
            bot.send_message(ADMIN_ID, "Нет пользователей")
            return
        text = "Пользователи:\n"
        for uid, access in user_access.items():
            if access:
                tickets = user_stats.get(uid, {}).get('tickets', 0)
                vip = "VIP" if is_vip(int(uid)) else "обычный"
                name = user_names.get(uid, {}).get('name', uid)
                text += f"{vip} {name} - {tickets} билетов\n"
        bot.send_message(ADMIN_ID, text)

@bot.message_handler(commands=['stats'])
def stats_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        active = len([u for u in user_access if user_access[u]])
        vip = len([u for u in user_vip if datetime.fromisoformat(user_vip[u]) > get_time()])
        total = sum([s.get('tickets', 0) for s in user_stats.values()])
        text = f"Статистика\nПользователей: {active}\nVIP: {vip}\nБилетов: {total}\nВыручка: {total * PRET} MDL"
        bot.send_message(ADMIN_ID, text)

@bot.message_handler(commands=['vip_list'])
def vip_list_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        text = "VIP пользователи:\n"
        count = 0
        for uid, expiry_str in user_vip.items():
            expiry = datetime.fromisoformat(expiry_str)
            if expiry > get_time():
                name = user_names.get(uid, {}).get('name', uid)
                days = (expiry - get_time()).days
                text += f"{name} - {days} дн\n"
                count += 1
        if count == 0:
            text = "Нет VIP"
        bot.send_message(ADMIN_ID, text)

@bot.message_handler(commands=['ad'])
def ad_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    msg = bot.send_message(ADMIN_ID, "Введи текст рассылки:")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(m):
    text = m.text
    sent = 0
    for uid, access in user_access.items():
        if access:
            try:
                bot.send_message(int(uid), f"РАССЫЛКА\n\n{text}")
                sent += 1
                time.sleep(0.05)
            except:
                pass
    bot.send_message(ADMIN_ID, f"Отправлено {sent} пользователям")

def issue_ticket(chat_id, user_id, cod):
    try:
        msg = bot.send_message(chat_id, "Обработка...")
        time.sleep(2)
        bot.delete_message(chat_id, msg.message_id)
        now = get_time()
        nr = random.randint(10000000, 99999999)
        update_stats(user_id)
        increment_daily_tickets(user_id)
        if not is_vip(user_id) and str(user_id) != str(ADMIN_ID):
            set_cooldown(user_id)
        ticket = f"{cod}\n{now.strftime('%I:%M %p').lstrip('0')}\n\nBiletul electronic nr. {nr}\n{now.strftime('%d.%m.%Y')}\nValabil 1 ora (Pret {PRET} MDL)\n\nNumarul de bord: {cod}"
        bot.send_message(chat_id, ticket, reply_markup=user_menu(user_id))
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == "🎫 Купить билет")
def buy_ticket_btn(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "Сначала /start", reply_markup=back_menu())
        return
    bot.send_message(uid, "Введи номер автобуса (2000-2099):", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, process_ticket)

def process_ticket(m):
    uid = m.from_user.id
    text = m.text.strip()
    if not text.isdigit() or len(text) != 4:
        bot.send_message(uid, "Нужно 4 цифры (2000-2099)!", reply_markup=user_menu(uid))
        return
    cod = int(text)
    if cod < 2000 or cod > 2099:
        bot.send_message(uid, f"{cod} не в диапазоне 2000-2099", reply_markup=user_menu(uid))
        return
    can, minutes, msg = check_can_buy_ticket(uid)
    if not can:
        if minutes > 0:
            hours = minutes // 60
            mins = minutes % 60
            if hours > 0:
                time_text = f"{hours}ч {mins}мин"
            else:
                time_text = f"{mins}мин"
            last = user_cooldown.get(str(uid))
            if last:
                last_time = datetime.fromisoformat(last)
                available = last_time + timedelta(hours=NORMAL_COOLDOWN_HOURS)
                bot.send_message(uid, f"Следующий билет через {time_text}\nДоступен в {available.strftime('%H:%M')}", reply_markup=user_menu(uid))
            else:
                bot.send_message(uid, f"Следующий билет через {time_text}", reply_markup=user_menu(uid))
        else:
            bot.send_message(uid, msg or f"Лимит {NORMAL_DAILY_LIMIT} билетов в день!", reply_markup=user_menu(uid))
        return
    threading.Thread(target=issue_ticket, args=(uid, uid, cod)).start()

@bot.message_handler(func=lambda m: m.text and m.text.isdigit() and len(m.text) == 4)
def direct_ticket(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "Сначала /start", reply_markup=back_menu())
        return
    cod = int(m.text)
    if 2000 <= cod <= 2099:
        can, minutes, msg = check_can_buy_ticket(uid)
        if not can:
            if minutes > 0:
                hours = minutes // 60
                mins = minutes % 60
                if hours > 0:
                    time_text = f"{hours}ч {mins}мин"
                else:
                    time_text = f"{mins}мин"
                last = user_cooldown.get(str(uid))
                if last:
                    last_time = datetime.fromisoformat(last)
                    available = last_time + timedelta(hours=NORMAL_COOLDOWN_HOURS)
                    bot.send_message(uid, f"Следующий билет через {time_text}\nДоступен в {available.strftime('%H:%M')}", reply_markup=user_menu(uid))
                else:
                    bot.send_message(uid, f"Следующий билет через {time_text}", reply_markup=user_menu(uid))
            else:
                bot.send_message(uid, msg or f"Лимит {NORMAL_DAILY_LIMIT} билетов в день!", reply_markup=user_menu(uid))
            return
        threading.Thread(target=issue_ticket, args=(uid, uid, cod)).start()
    else:
        bot.send_message(uid, f"{cod} не в диапазоне 2000-2099", reply_markup=user_menu(uid))

@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def back_btn(m):
    uid = m.from_user.id
    if str(uid) == str(ADMIN_ID):
        bot.send_message(uid, "Админ панель", reply_markup=admin_menu())
    else:
        if user_access.get(str(uid), False):
            msg = "Главное меню\n\n"
            if is_vip(uid):
                expiry = get_vip_expiry(uid)
                msg += f"VIP до {expiry.strftime('%d.%m.%Y')}\n"
                msg += f"Сегодня: {get_daily_tickets_count(uid)}/10 билетов"
            else:
                msg += f"Обычный: {NORMAL_DAILY_LIMIT} билетов/день\n"
                msg += f"Сегодня: {get_daily_tickets_count(uid)}/{NORMAL_DAILY_LIMIT}"
            bot.send_message(uid, msg, reply_markup=user_menu(uid))
        else:
            bot.send_message(uid, "Введи код доступа")

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
    bot.send_message(ADMIN_ID, "Используй: /give_vip @username дни или /give_vip ID дни")

@bot.message_handler(func=lambda m: m.text == "📢 Рассылка" and str(m.from_user.id) == str(ADMIN_ID))
def ad_btn(m):
    ad_cmd(m)

@bot.message_handler(func=lambda m: m.text == "📊 Статистика" and str(m.from_user.id) == str(ADMIN_ID))
def stats_btn(m):
    stats_cmd(m)

@bot.message_handler(func=lambda m: m.text == "👥 Пользователи" and str(m.from_user.id) == str(ADMIN_ID))
def users_btn(m):
    users_cmd(m)

@bot.message_handler(func=lambda m: m.text == "⭐ Купить VIP")
def buy_vip_btn(m):
    buy_vip_cmd(m)

@bot.message_handler(func=lambda m: m.text == "💎 Мой VIP" or m.text == "⏰ Мой статус")
def status_btn(m):
    status_cmd(m)

if __name__ == "__main__":
    load_data()
    check_expired_vip()
    def vip_checker():
        while True:
            time.sleep(21600)
            check_expired_vip()
    threading.Thread(target=vip_checker, daemon=True).start()
    threading.Thread(target=run_web, daemon=True).start()
    try:
        bot.remove_webhook()
    except:
        pass
    print("=" * 50)
    print("БОТ ЗАПУЩЕН")
    print(f"Admin ID: {ADMIN_ID}")
    print("=" * 50)
    bot.infinity_polling(timeout=10)
