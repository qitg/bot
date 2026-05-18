import telebot
from flask import Flask, request
import threading
import os
import time
import random
import json
from datetime import datetime, timedelta, timezone

TOKEN = "8307596159:AAGkuxqO1WKToY_9k6nXegDqljFH45L-mmQ"
ADMIN_ID = 7072265211

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ========== ЦЕНЫ И ЛИМИТЫ ==========
PRET = 6
VIP_WEEK_PRICE = 15
VIP_WEEK_DAYS = 7
VIP_MONTH_PRICE = 60
VIP_MONTH_DAYS = 30
NORMAL_DAILY_LIMIT = 3
NORMAL_COOLDOWN_HOURS = 3

# ========== ДАННЫЕ ==========
user_access = {}
user_cooldown = {}
parole_active = []
user_stats = {}
user_vip = {}
user_daily_tickets = {}
user_names = {}
user_referrals = {}
user_referred_by = {}
promocodes = {}  # {код: {'uses_left': int, 'discount_percent': int, 'created_by': int}}
DATA_FILE = "bot_data.json"

def get_time():
    return datetime.now(timezone(timedelta(hours=3)))  # Молдова UTC+3

def load_data():
    global user_access, user_cooldown, parole_active, user_stats, user_vip, user_daily_tickets, user_names, user_referrals, user_referred_by, promocodes
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
            user_referrals = data.get('referrals', {})
            user_referred_by = data.get('referred_by', {})
            promocodes = data.get('promocodes', {})

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'access': user_access,
            'cooldown': user_cooldown,
            'passwords': parole_active,
            'stats': user_stats,
            'vip': user_vip,
            'daily_tickets': user_daily_tickets,
            'names': user_names,
            'referrals': user_referrals,
            'referred_by': user_referred_by,
            'promocodes': promocodes
        }, f)

# ========== РЕФЕРАЛЫ ==========
def add_referral(user_id, referrer_id):
    uid = str(user_id)
    rid = str(referrer_id)
    if uid == rid:
        return False
    if uid in user_referred_by:
        return False
    user_referred_by[uid] = rid
    if rid not in user_referrals:
        user_referrals[rid] = []
    if uid not in user_referrals[rid]:
        user_referrals[rid].append(uid)
    save_data()
    
    if len(user_referrals[rid]) >= 5 and not is_vip(int(rid)):
        set_vip(int(rid), 30)
        try:
            bot.send_message(int(rid), "🎉 ПОЗДРАВЛЯЮ! 🎉\n\nТы пригласил 5 друзей и получил VIP на месяц БЕСПЛАТНО!")
        except:
            pass
    return True

def get_referral_count(user_id):
    uid = str(user_id)
    return len(user_referrals.get(uid, []))

def get_referral_link(user_id):
    return f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"

# ========== ПРОМОКОДЫ ==========
def create_promocode(code, uses, discount_percent):
    promocodes[code] = {
        'uses_left': uses,
        'discount_percent': discount_percent,
        'created_by': ADMIN_ID
    }
    save_data()
    return True

def use_promocode(user_id, code):
    if code not in promocodes:
        return False, "Промокод не найден", 0
    if promocodes[code]['uses_left'] <= 0:
        del promocodes[code]
        save_data()
        return False, "Промокод уже использован", 0
    
    discount = promocodes[code]['discount_percent']
    promocodes[code]['uses_left'] -= 1
    
    if promocodes[code]['uses_left'] <= 0:
        del promocodes[code]
    save_data()
    
    return True, f"Промокод активирован! Скидка {discount}%", discount

# ========== VIP И БИЛЕТЫ ==========
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

def set_vip(user_id, days):
    uid = str(user_id)
    expiry = get_time() + timedelta(days=days)
    user_vip[uid] = expiry.isoformat()
    save_data()

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
        try:
            bot.send_message(ADMIN_ID, f"⏰ VIP истёк у {len(expired)} пользователей")
        except:
            pass
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
    if str(user_id) == str(ADMIN_ID):
        return True, 0, ""
    
    if is_vip(user_id):
        daily_count = get_daily_tickets_count(user_id)
        if daily_count >= 10:
            return False, 0, "VIP лимит 10 билетов в день"
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
    if str(user_id) == str(ADMIN_ID):
        return
    user_cooldown[str(user_id)] = get_time().isoformat()
    save_data()

def update_stats(user_id):
    uid = str(user_id)
    if uid not in user_stats:
        user_stats[uid] = {'tickets': 0}
    user_stats[uid]['tickets'] += 1
    save_data()

# ========== FLASK WEBHOOK ==========
@app.route('/')
def health():
    return "Bot is running!", 200

@app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '!', 200

# ========== КЛАВИАТУРЫ ==========
def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("🆕 Создать пароль", "📋 Список паролей")
    mk.row("💎 Выдать VIP", "🎫 Создать промокод")
    mk.row("📢 Рассылка", "📊 Статистика")
    mk.row("👥 Пользователи", "🗑 Сброс паролей")
    mk.row("❓ Команды")
    return mk

def user_menu(uid):
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    if is_vip(uid):
        daily_count = get_daily_tickets_count(uid)
        mk.row(f"🎫 Купить билет ({daily_count}/10)")
        mk.row("💎 Мой VIP", "👥 Рефералы")
    else:
        daily_count = get_daily_tickets_count(uid)
        mk.row(f"🎫 Купить билет ({daily_count}/{NORMAL_DAILY_LIMIT})")
        mk.row("⭐ Купить VIP", "👥 Рефералы")
    mk.row("🎟 Промокод", "❓ Команды")
    return mk

def back_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("🔙 Назад")
    return mk

# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========
@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    username = m.from_user.username
    
    user_names[str(uid)] = {'name': name, 'username': username}
    
    text = m.text.split()
    if len(text) > 1 and text[1].startswith('ref_'):
        referrer_id = int(text[1].replace('ref_', ''))
        if referrer_id != uid:
            add_referral(uid, referrer_id)
    
    save_data()
    
    if str(uid) == str(ADMIN_ID):
        user_access[str(uid)] = True
        save_data()
        bot.send_message(uid, "🔐 Админ панель\n\n✅ Теперь ты можешь покупать билеты как обычный пользователь", reply_markup=admin_menu())
        return
    
    if user_access.get(str(uid), False):
        msg = f"✅ Привет, {name}!\n\n"
        if is_vip(uid):
            expiry = get_vip_expiry(uid)
            msg += f"💎 Ты VIP до {expiry.strftime('%d.%m.%Y')}\n"
            msg += f"🎫 Сегодня: {get_daily_tickets_count(uid)}/10 билетов"
        else:
            msg += f"⭐ Обычный: {NORMAL_DAILY_LIMIT} билетов/день, кулдаун {NORMAL_COOLDOWN_HOURS} ч\n"
            msg += f"🎫 Сегодня: {get_daily_tickets_count(uid)}/{NORMAL_DAILY_LIMIT}\n\n"
            msg += "🔥 Купи VIP:\n• Неделя: 15 лей\n• Месяц: 60 лей\n/buy_vip"
        bot.send_message(uid, msg, reply_markup=user_menu(uid))
    else:
        bot.send_message(uid, "🔑 Введи код доступа")
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
        bot.send_message(uid, f"✅ Доступ открыт!\n\n⭐ Обычный: {NORMAL_DAILY_LIMIT} билетов/день, кулдаун {NORMAL_COOLDOWN_HOURS} ч\n\n🔥 Купи VIP:\n• Неделя: 15 лей\n• Месяц: 60 лей\n/buy_vip", reply_markup=user_menu(uid))
        bot.send_message(ADMIN_ID, f"🔓 Новый пользователь: {name} (ID: {uid})")
    else:
        bot.send_message(uid, "❌ Неверный код!\nПопробуй ещё:")
        bot.register_next_step_handler(m, check_code)

@bot.message_handler(commands=['help'])
def help_cmd(m):
    uid = m.from_user.id
    if str(uid) == str(ADMIN_ID):
        text = """
👑 АДМИН КОМАНДЫ:

/gen_pass - создать пароль
/list_pass - список паролей
/clear_pass - удалить все пароли
/create_promo код количество скидка% - создать промокод
/users - список пользователей
/stats - статистика
/vip_list - список VIP

💎 ВЫДАТЬ VIP:
/give_vip ID week - неделя
/give_vip ID month - месяц
/give_vip @username week - по юзернейму

/remove_vip ID - снять VIP
/ad текст - рассылка
"""
    else:
        daily = get_daily_tickets_count(uid)
        limit = NORMAL_DAILY_LIMIT if not is_vip(uid) else 10
        text = f"""
🤖 ДОСТУПНЫЕ КОМАНДЫ:

/start - главное меню
/help - этот список
/status - мой статус
/buy_vip - купить VIP
/referral - моя реферальная ссылка
/referrals - сколько друзей пригласил

🎫 КУПИТЬ БИЛЕТ:
Просто напиши номер (2000-2099)

🎟 ПРОМОКОД:
Используй кнопку "Промокод"

📊 ТВОЙ СТАТУС:
Сегодня: {daily}/{limit}

💎 VIP ПАКЕТЫ:
• НЕДЕЛЯ: 15 лей
• МЕСЯЦ: 60 лей
"""
    bot.send_message(uid, text)

@bot.message_handler(commands=['referral'])
def referral_cmd(m):
    uid = m.from_user.id
    link = get_referral_link(uid)
    count = get_referral_count(uid)
    text = f"🔗 Твоя реферальная ссылка:\n{link}\n\n👥 Приглашено друзей: {count}\n\nЗа 5 друзей → VIP на месяц БЕСПЛАТНО!"
    bot.send_message(uid, text, reply_markup=user_menu(uid))

@bot.message_handler(commands=['referrals'])
def referrals_count_cmd(m):
    uid = m.from_user.id
    count = get_referral_count(uid)
    bot.send_message(uid, f"👥 Ты пригласил {count} человек(а).\nОсталось {5 - count if count < 5 else 0} до VIP.", reply_markup=user_menu(uid))

@bot.message_handler(commands=['create_promo'])
def create_promo_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    try:
        parts = m.text.split()
        if len(parts) != 4:
            bot.send_message(ADMIN_ID, "❌ Используй: /create_promo КОД КОЛИЧЕСТВО СКИДКА%\nПример: /create_promo SUPER10 100 20\n\nСкидка будет вычитаться из цены билета (6 лей)")
            return
        code = parts[1].upper()
        uses = int(parts[2])
        discount = int(parts[3])
        if discount < 0 or discount > 100:
            bot.send_message(ADMIN_ID, "❌ Скидка должна быть от 0 до 100%")
            return
        create_promocode(code, uses, discount)
        bot.send_message(ADMIN_ID, f"✅ Промокод {code} создан на {uses} использований со скидкой {discount}%")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == "🎟 Промокод")
def promo_btn(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала /start", reply_markup=back_menu())
        return
    bot.send_message(uid, "🎟 Введи промокод:")
    bot.register_next_step_handler(m, apply_promo)

def apply_promo(m):
    uid = m.from_user.id
    code = m.text.strip().upper()
    success, msg, discount = use_promocode(uid, code)
    if success:
        # Сохраняем скидку для пользователя
        user_discount[str(uid)] = discount
        save_data()
        bot.send_message(uid, f"✅ {msg}\nТвоя скидка {discount}% на следующую покупку билета!")
    else:
        bot.send_message(uid, f"❌ {msg}")
    bot.send_message(uid, "Вернулся в меню", reply_markup=user_menu(uid))

# Добавляем словарь для хранения активных скидок пользователей
user_discount = {}

# Обновляем функцию issue_ticket с учётом скидки
def issue_ticket(chat_id, user_id, cod):
    try:
        msg = bot.send_message(chat_id, "🔄 Обработка запроса...")
        time.sleep(2)
        bot.delete_message(chat_id, msg.message_id)
        
        now = get_time()
        nr = random.randint(10000000, 99999999)
        
        # Проверяем скидку
        discount = user_discount.get(str(user_id), 0)
        price_after_discount = PRET
        discount_text = ""
        if discount > 0:
            price_after_discount = PRET - int(PRET * discount / 100)
            discount_text = f"\n💰 Скидка {discount}%: {price_after_discount} лей (было {PRET})"
            # Скидка одноразовая, удаляем после использования
            del user_discount[str(user_id)]
            save_data()
        else:
            price_after_discount = PRET
        
        update_stats(user_id)
        increment_daily_tickets(user_id)
        if not is_vip(user_id) and str(user_id) != str(ADMIN_ID):
            set_cooldown(user_id)
        
        ticket = f"""{cod}
{now.strftime('%I:%M %p').lstrip('0')}

Biletul electronic nr. {nr}
{now.strftime('%d.%m.%Y')}
Valabil 1 ora (de la {now.strftime('%H:%M')} Pret {price_after_discount} MDL{discount_text})

Numarul de bord: {cod}"""
        
        bot.send_message(chat_id, ticket, reply_markup=user_menu(user_id))
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {e}")

@bot.message_handler(commands=['status'])
def status_cmd(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала /start", reply_markup=back_menu())
        return
    daily = get_daily_tickets_count(uid)
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        text = f"""
💎 VIP СТАТУС

📅 Действует до: {expiry.strftime('%d.%m.%Y')}
🎫 Осталось сегодня: {10-daily}/10
⏰ Кулдаун: отсутствует
💰 Цена билета: {PRET} лей
👥 Приглашено друзей: {get_referral_count(uid)}
"""
    else:
        last = user_cooldown.get(str(uid))
        cooldown_text = "✅ Можешь купить билет"
        if last:
            last_time = datetime.fromisoformat(last)
            passed = get_time() - last_time
            if passed < timedelta(hours=NORMAL_COOLDOWN_HOURS):
                remaining = timedelta(hours=NORMAL_COOLDOWN_HOURS) - passed
                minutes = int(remaining.total_seconds() // 60)
                hours = minutes // 60
                mins = minutes % 60
                if hours > 0:
                    cooldown_text = f"⏰ Кулдаун: {hours}ч {mins}мин"
                else:
                    cooldown_text = f"⏰ Кулдаун: {mins}мин"
                available = last_time + timedelta(hours=NORMAL_COOLDOWN_HOURS)
                cooldown_text += f"\n📅 Доступен в {available.strftime('%H:%M')}"
        text = f"""
⭐ ОБЫЧНЫЙ РЕЖИМ

📅 Сегодня: {daily}/{NORMAL_DAILY_LIMIT}
{cooldown_text}
💰 Цена билета: {PRET} лей
👥 Приглашено друзей: {get_referral_count(uid)}

💎 КУПИ VIP:
• Неделя: 15 лей
• Месяц: 60 лей
Напиши /buy_vip
"""
    bot.send_message(uid, text, reply_markup=user_menu(uid))

@bot.message_handler(commands=['buy_vip'])
def buy_vip_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    username = m.from_user.username
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала /start", reply_markup=back_menu())
        return
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        bot.send_message(uid, f"💎 У тебя уже есть VIP до {expiry.strftime('%d.%m.%Y')}", reply_markup=user_menu(uid))
        return
    
    bot.send_message(ADMIN_ID, 
        f"🟢 НОВАЯ ЗАЯВКА НА VIP\n\n"
        f"👤 Пользователь: {name}\n"
        f"🆔 ID: {uid}\n"
        f"📝 Username: @{username if username else 'нет'}\n\n"
        f"💎 ПАКЕТЫ:\n"
        f"• НЕДЕЛЯ: {VIP_WEEK_PRICE} лей\n"
        f"• МЕСЯЦ: {VIP_MONTH_PRICE} лей\n\n"
        f"✅ ВЫДАТЬ VIP:\n/give_vip {uid} week\n/give_vip {uid} month")
    
    bot.send_message(uid, 
        f"💎 **VIP СТАТУС**\n\n"
        f"🔥 **СПЕЦИАЛЬНОЕ ПРЕДЛОЖЕНИЕ!** 🔥\n\n"
        f"📦 **ПАКЕТЫ:**\n"
        f"• 🟢 НЕДЕЛЯ: {VIP_WEEK_PRICE} лей\n"
        f"• 🔥 МЕСЯЦ: {VIP_MONTH_PRICE} лей (экономия 40 лей!)\n\n"
        f"🎫 **ПРЕИМУЩЕСТВА VIP:**\n"
        f"• 10 билетов в день\n"
        f"• Без кулдауна\n"
        f"• Приоритетная поддержка\n\n"
        f"📩 **Свяжись с админом:** @RaskovskI\n\n"
        f"💬 Напиши какой пакет хочешь (неделя или месяц)",
        parse_mode='Markdown', reply_markup=back_menu())

# ========== АДМИН КОМАНДЫ ==========
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
        if len(parts) < 3:
            bot.send_message(ADMIN_ID, "❌ Используй:\n/give_vip ID week\n/give_vip ID month\n/give_vip @username week\n/give_vip @username month")
            return
        
        user_input = parts[1]
        package = parts[2].lower()
        
        if user_input.startswith('@'):
            user_id = find_user_id_by_username(user_input)
            if not user_id:
                bot.send_message(ADMIN_ID, f"❌ Пользователь {user_input} не найден")
                return
        else:
            user_id = int(user_input)
        
        if package == "week":
            days = VIP_WEEK_DAYS
            price = VIP_WEEK_PRICE
            package_name = "неделю"
        elif package == "month":
            days = VIP_MONTH_DAYS
            price = VIP_MONTH_PRICE
            package_name = "месяц"
        else:
            bot.send_message(ADMIN_ID, "❌ Пакет: week или month")
            return
        
        set_vip(user_id, days)
        name = user_names.get(str(user_id), {}).get('name', user_id)
        
        bot.send_message(ADMIN_ID, f"✅ VIP ({package_name}) выдан {name} за {price} лей\nДо: {(get_time() + timedelta(days=days)).strftime('%d.%m.%Y')}")
        
        try:
            bot.send_message(user_id, 
                f"💎 **VIP СТАТУС АКТИВИРОВАН!**\n\n"
                f"📦 Пакет: {package_name}\n"
                f"💰 Оплачено: {price} лей\n"
                f"📅 Действует до: {(get_time() + timedelta(days=days)).strftime('%d.%m.%Y')}\n"
                f"🎫 10 билетов в день, без кулдауна!\n\n"
                f"Напиши /start чтобы увидеть изменения", reply_markup=user_menu(user_id))
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
            bot.send_message(ADMIN_ID, "❌ /remove_vip ID или /remove_vip @username")
            return
        user_input = parts[1]
        if user_input.startswith('@'):
            user_id = find_user_id_by_username(user_input)
            if not user_id:
                bot.send_message(ADMIN_ID, f"❌ Пользователь {user_input} не найден")
                return
        else:
            user_id = int(user_input)
        remove_vip(user_id)
        bot.send_message(ADMIN_ID, f"✅ VIP снят с {user_input}")
        try:
            bot.send_message(user_id, "⏰ VIP статус снят администратором", reply_markup=user_menu(user_id))
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
        text = "👥 ПОЛЬЗОВАТЕЛИ:\n\n"
        for uid, access in user_access.items():
            if access:
                tickets = user_stats.get(uid, {}).get('tickets', 0)
                vip = "💎" if is_vip(int(uid)) else "⭐"
                name = user_names.get(uid, {}).get('name', uid)
                refs = get_referral_count(int(uid))
                text += f"{vip} {name} - {tickets} билетов, {refs} рефералов\n"
        bot.send_message(ADMIN_ID, text)

@bot.message_handler(commands=['stats'])
def stats_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        active = len([u for u in user_access if user_access[u]])
        vip = len([u for u in user_vip if datetime.fromisoformat(user_vip[u]) > get_time()])
        total = sum([s.get('tickets', 0) for s in user_stats.values()])
        total_refs = sum([len(user_referrals.get(uid, [])) for uid in user_referrals])
        text = f"""
📊 СТАТИСТИКА

👥 Пользователей: {active}
💎 VIP: {vip}
🎫 Всего билетов: {total}
💰 Выручка: {total * PRET} MDL
👥 Всего рефералов: {total_refs}

⭐ Обычный лимит: {NORMAL_DAILY_LIMIT}/день
⏰ Обычный кулдаун: {NORMAL_COOLDOWN_HOURS} ч
💎 VIP: 10 билетов/день, без кулдауна
"""
        bot.send_message(ADMIN_ID, text)

@bot.message_handler(commands=['vip_list'])
def vip_list_cmd(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        text = "💎 VIP ПОЛЬЗОВАТЕЛИ:\n\n"
        count = 0
        for uid, expiry_str in user_vip.items():
            expiry = datetime.fromisoformat(expiry_str)
            if expiry > get_time():
                name = user_names.get(uid, {}).get('name', uid)
                days = (expiry - get_time()).days
                text += f"• {name} - осталось {days} дн\n"
                count += 1
        if count == 0:
            text = "❌ Нет VIP"
        bot.send_message(ADMIN_ID, text)

@bot.message_handler(commands=['ad'])
def ad_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    msg = bot.send_message(ADMIN_ID, "✏️ Введи текст рассылки:")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(m):
    text = m.text
    sent = 0
    for uid, access in user_access.items():
        if access:
            try:
                bot.send_message(int(uid), f"📢 РАССЫЛКА\n\n{text}")
                sent += 1
                time.sleep(0.05)
            except:
                pass
    bot.send_message(ADMIN_ID, f"✅ Отправлено {sent} пользователям")

# ========== ПОКУПКА БИЛЕТА ==========
# Функция issue_ticket уже определена выше (с учётом скидки)

@bot.message_handler(func=lambda m: m.text == "🎫 Купить билет")
def buy_ticket_btn(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала /start", reply_markup=back_menu())
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
                bot.send_message(uid, f"⏰ Следующий билет через {time_text}\n📅 Доступен в {available.strftime('%H:%M')}", reply_markup=user_menu(uid))
            else:
                bot.send_message(uid, f"⏰ Следующий билет через {time_text}", reply_markup=user_menu(uid))
        else:
            bot.send_message(uid, msg or f"❌ Лимит {NORMAL_DAILY_LIMIT} билетов в день!", reply_markup=user_menu(uid))
        return
    threading.Thread(target=issue_ticket, args=(uid, uid, cod)).start()

@bot.message_handler(func=lambda m: m.text and m.text.isdigit() and len(m.text) == 4)
def direct_ticket(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала /start", reply_markup=back_menu())
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
                    bot.send_message(uid, f"⏰ Следующий билет через {time_text}\n📅 Доступен в {available.strftime('%H:%M')}", reply_markup=user_menu(uid))
                else:
                    bot.send_message(uid, f"⏰ Следующий билет через {time_text}", reply_markup=user_menu(uid))
            else:
                bot.send_message(uid, msg or f"❌ Лимит {NORMAL_DAILY_LIMIT} билетов в день!", reply_markup=user_menu(uid))
            return
        threading.Thread(target=issue_ticket, args=(uid, uid, cod)).start()
    else:
        bot.send_message(uid, f"❌ {cod} не в диапазоне 2000-2099", reply_markup=user_menu(uid))

# ========== НАВИГАЦИЯ ==========
@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def back_btn(m):
    uid = m.from_user.id
    if str(uid) == str(ADMIN_ID):
        bot.send_message(uid, "🔐 Админ панель", reply_markup=admin_menu())
    else:
        if user_access.get(str(uid), False):
            msg = "✅ Главное меню\n\n"
            if is_vip(uid):
                expiry = get_vip_expiry(uid)
                msg += f"💎 VIP до {expiry.strftime('%d.%m.%Y')}\n"
                msg += f"🎫 Сегодня: {get_daily_tickets_count(uid)}/10 билетов"
            else:
                msg += f"⭐ Обычный: {NORMAL_DAILY_LIMIT} билетов/день\n"
                msg += f"🎫 Сегодня: {get_daily_tickets_count(uid)}/{NORMAL_DAILY_LIMIT}\n\n"
                msg += "Купи VIP: /buy_vip"
            msg += f"\n\n👥 Приглашено друзей: {get_referral_count(uid)}"
            bot.send_message(uid, msg, reply_markup=user_menu(uid))
        else:
            bot.send_message(uid, "🔑 Введи код доступа")

@bot.message_handler(func=lambda m: m.text == "❓ Команды")
def commands_btn(m):
    help_cmd(m)

@bot.message_handler(func=lambda m: m.text == "👥 Рефералы")
def referrals_btn(m):
    referral_cmd(m)

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
    bot.send_message(ADMIN_ID, "💎 Используй:\n/give_vip @username week\n/give_vip @username month\n/give_vip ID week\n/give_vip ID month")

@bot.message_handler(func=lambda m: m.text == "🎫 Создать промокод" and str(m.from_user.id) == str(ADMIN_ID))
def create_promo_btn(m):
    bot.send_message(ADMIN_ID, "🎫 Используй: /create_promo КОД КОЛИЧЕСТВО СКИДКА%\nПример: /create_promo SUPER10 100 20\n\nСкидка будет вычитаться из цены билета (6 лей)")

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

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    load_data()
    check_expired_vip()
    
    def vip_checker():
        while True:
            time.sleep(21600)
            check_expired_vip()
    threading.Thread(target=vip_checker, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')}/webhook/{TOKEN}"
    
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    
    print("=" * 50)
    print("✅ БОТ ЗАПУЩЕН")
    print(f"👑 ADMIN ID: {ADMIN_ID}")
    print(f"🌐 Webhook: {webhook_url}")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=port)
