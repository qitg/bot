import telebot
from datetime import datetime, timedelta
import random
import re
import json
import os
import time
import threading
from flask import Flask, render_template_string, request

# ========== КОНФИГ ==========
TOKEN = "8307596159:AAES-a6TjEaAaP_j6LPogq2Eb9vsoBqtL4o"
ADMIN_ID = 7072265211

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

def get_time():
    return datetime.utcnow() + timedelta(hours=3)

PRET = 6
VALABILITATE_ORE = 1
VIP_PRICE = 25
VIP_DAYS = 7
NORMAL_DAILY_LIMIT = 3
NORMAL_COOLDOWN_MINUTES = 45

bilete_active = {}
user_access = {}
user_cooldown = {}
parole_active = []
user_stats = {}
user_vip = {}
user_daily_tickets = {}
user_register_date = {}

DATA_FILE = "bot_data.json"

def load_data():
    global bilete_active, user_access, user_cooldown, parole_active, user_stats, user_vip, user_daily_tickets, user_register_date
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            bilete_active = data.get('tickets', {})
            user_access = data.get('access', {})
            user_cooldown = data.get('cooldown', {})
            parole_active = data.get('passwords', [])
            user_stats = data.get('stats', {})
            user_vip = data.get('vip', {})
            user_daily_tickets = data.get('daily_tickets', {})
            user_register_date = data.get('register_date', {})

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'tickets': bilete_active,
            'access': user_access,
            'cooldown': user_cooldown,
            'passwords': parole_active,
            'stats': user_stats,
            'vip': user_vip,
            'daily_tickets': user_daily_tickets,
            'register_date': user_register_date
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
    bot.send_message(ADMIN_ID, f"✅ VIP выдан пользователю `{uid}` до {expiry.strftime('%d.%m.%Y %H:%M')}", parse_mode='Markdown')

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
            return False, "❌ У VIP лимит 10 билетов в день. Завтра будут новые!"
        return True, 0
    if str(user_id) == str(ADMIN_ID):
        return True, 0
    last = user_cooldown.get(str(user_id))
    if last:
        last_time = datetime.fromisoformat(last)
        now = get_time()
        passed = now - last_time
        if passed < timedelta(minutes=NORMAL_COOLDOWN_MINUTES):
            remaining = timedelta(minutes=NORMAL_COOLDOWN_MINUTES) - passed
            return False, int(remaining.total_seconds() // 60)
    daily_count = get_daily_tickets_count(user_id)
    if daily_count >= NORMAL_DAILY_LIMIT:
        return False, 0
    return True, 0

def set_cooldown(user_id):
    user_cooldown[str(user_id)] = get_time().isoformat()
    save_data()

def update_stats(user_id, name):
    uid = str(user_id)
    if uid not in user_stats:
        user_stats[uid] = {'name': name, 'tickets': 0}
    user_stats[uid]['tickets'] += 1
    save_data()

def register_new_user(user_id, name):
    uid = str(user_id)
    if uid not in user_register_date:
        user_register_date[uid] = get_time().isoformat()
        save_data()
        bot.send_message(ADMIN_ID, f"🆕 Новый пользователь: {name} (ID: `{uid}`)", parse_mode='Markdown')

# ========== ВЫДАЧА БИЛЕТА (ТАК КАК ТЫ ХОЧЕШЬ) ==========
def issue_ticket(chat_id, user_id, cod, name):
    try:
        msg = bot.send_message(chat_id, "🔄 Cererea dumneavoastră este în curs de procesare...")
        time.sleep(2)
        bot.delete_message(chat_id, msg.message_id)
        now = get_time()
        exp = now + timedelta(hours=VALABILITATE_ORE)
        nr = random.randint(10000000, 99999999)
        bilete_active[str(nr)] = {
            'bus': cod,
            'user_id': user_id,
            'user_name': name,
            'exp': exp.isoformat(),
            'date': now.strftime("%d.%m.%Y"),
            'time': now.strftime("%H:%M")
        }
        if str(user_id) != str(ADMIN_ID):
            set_cooldown(user_id)
            update_stats(user_id, name)
            increment_daily_tickets(user_id)
        save_data()
        
        # ТВОЙ ФОРМАТ БИЛЕТА
        ticket = f"{cod}\n{now.strftime('%I:%M %p').lstrip('0')}\n\nCererea dumneavoastră procesare.\n\nBiletul electronic nr. {nr}\n{now.strftime('%d.%m.%Y')}\nValabil {VALABILITATE_ORE} ora (de la {now.strftime('%H:%M')} Pret {PRET} MDL)\n\nNumarul de bord: {cod}"
        
        bot.send_message(chat_id, ticket, reply_markup=user_menu(user_id))
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {e}")

# ========== HTML ==========
HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Transport Moldova Admin</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            color: white;
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { margin-bottom: 20px; font-size: 2em; }
        h1 i { color: #00d4ff; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        .card .num { font-size: 2.5em; font-weight: bold; color: #00d4ff; }
        .card .label { margin-top: 10px; color: #aaa; }
        table {
            width: 100%;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            border-collapse: collapse;
            overflow: hidden;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th { background: rgba(0,212,255,0.2); color: #00d4ff; }
        tr:hover { background: rgba(255,255,255,0.05); }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .tab {
            background: rgba(255,255,255,0.1);
            padding: 10px 25px;
            border-radius: 10px;
            cursor: pointer;
            transition: 0.3s;
        }
        .tab.active { background: #00d4ff; color: #1a1a2e; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        button {
            background: #00d4ff;
            color: #1a1a2e;
            border: none;
            padding: 8px 20px;
            border-radius: 8px;
            cursor: pointer;
            margin: 10px 0;
            font-weight: bold;
        }
        .btn-red { background: #ff4757; color: white; }
        .vip-badge { background: gold; color: #1a1a2e; padding: 2px 8px; border-radius: 20px; font-size: 12px; }
        code { background: #000; padding: 2px 6px; border-radius: 5px; font-family: monospace; }
        .footer { margin-top: 30px; text-align: center; color: #555; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h1><i>🚌</i> TRANSPORT MOLDOVA — АДМИН ПАНЕЛЬ</h1>
        <div style="margin-bottom: 20px; color: #aaa;">{{ now }}</div>
        
        <div class="stats">
            <div class="card"><div class="num">{{ users_count }}</div><div class="label">Пользователей</div></div>
            <div class="card"><div class="num">{{ tickets_count }}</div><div class="label">Билетов продано</div></div>
            <div class="card"><div class="num">{{ revenue }}</div><div class="label">Выручка (MDL)</div></div>
            <div class="card"><div class="num">{{ vip_count }}</div><div class="label">VIP пользователей</div></div>
        </div>
        
        <div class="tabs">
            <div class="tab active" onclick="openTab('users')">👥 Пользователи</div>
            <div class="tab" onclick="openTab('tickets')">🎫 Билеты</div>
            <div class="tab" onclick="openTab('passwords')">🔑 Пароли</div>
        </div>
        
        <div id="users" class="tab-content active">
            <h3>Список пользователей</h3>
            <table>
                <tr><th>ID</th><th>Имя</th><th>Билетов</th><th>VIP</th><th>Регистрация</th><th>Статус</th></tr>
                {% for u in users %}
                <tr>
                    <td>{{ u.id }}</td>
                    <td>{{ u.name }} {% if u.vip %}<span class="vip-badge">💎 VIP</span>{% endif %}</td>
                    <td>{{ u.tickets }}</td>
                    <td>{% if u.vip_expiry %}до {{ u.vip_expiry }}{% else %}—{% endif %}</td>
                    <td>{{ u.reg_date }}</td>
                    <td>{% if u.access %}✅ Активен{% else %}❌ Блок{% endif %}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        <div id="tickets" class="tab-content">
            <h3>Последние билеты</h3>
            <table>
                <tr><th>№ билета</th><th>Автобус</th><th>Пользователь</th><th>Дата</th><th>Время</th></tr>
                {% for t in tickets %}
                <tr>
                    <td><code>{{ t.num }}</code></td>
                    <td>{{ t.bus }}</td>
                    <td>{{ t.user }}</td>
                    <td>{{ t.date }}</td>
                    <td>{{ t.time }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        <div id="passwords" class="tab-content">
            <h3>Активные пароли</h3>
            <button onclick="location.reload()">🔄 Обновить</button>
            <button onclick="genPass()">🆕 Создать пароль</button>
            <button class="btn-red" onclick="clearPass()">🗑 Удалить все</button>
            <table>
                <tr><th>Пароль</th><th>Действие</th></tr>
                {% for p in passwords %}
                <tr>
                    <td><code>{{ p }}</code></td>
                    <td><button class="btn-red" onclick="delPass('{{ p }}')">❌ Удалить</button></td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        <div class="footer">
            🎫 Обычные: 3 билета/день, кулдаун 45 мин | 💎 VIP: 10 билетов/день, без кулдауна
        </div>
    </div>
    
    <script>
        function openTab(name) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(name).classList.add('active');
        }
        function genPass() { fetch('/gen_pass').then(() => location.reload()); }
        function delPass(p) { fetch('/del_pass/' + p).then(() => location.reload()); }
        function clearPass() { if(confirm('Удалить все пароли?')) fetch('/clear_pass').then(() => location.reload()); }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    users = []
    for uid, access in user_access.items():
        if access:
            stats = user_stats.get(uid, {})
            reg_date = user_register_date.get(uid)
            vip_expiry = get_vip_expiry(int(uid))
            users.append({
                'id': uid,
                'name': stats.get('name', 'Unknown'),
                'tickets': stats.get('tickets', 0),
                'vip': vip_expiry is not None,
                'vip_expiry': vip_expiry.strftime('%d.%m') if vip_expiry else None,
                'reg_date': datetime.fromisoformat(reg_date).strftime('%d.%m.%Y') if reg_date else '?',
                'access': access
            })
    
    tickets = []
    for nr, b in list(bilete_active.items())[-30:]:
        tickets.append({
            'num': nr,
            'bus': b.get('bus'),
            'user': b.get('user_name', 'Unknown'),
            'date': b.get('date', ''),
            'time': b.get('time', '')
        })
    
    return render_template_string(HTML,
        now=get_time().strftime('%d.%m.%Y %H:%M:%S'),
        users_count=len([u for u in user_access if user_access[u]]),
        tickets_count=len(bilete_active),
        revenue=len(bilete_active) * PRET,
        vip_count=len([u for u in user_vip if datetime.fromisoformat(user_vip[u]) > get_time()]),
        users=users,
        tickets=tickets,
        passwords=parole_active
    )

@app.route('/gen_pass')
def gen_pass():
    p = gen_parola()
    parole_active.append(p)
    save_data()
    return 'ok'

@app.route('/del_pass/<p>')
def del_pass(p):
    if p in parole_active:
        parole_active.remove(p)
        save_data()
    return 'ok'

@app.route('/clear_pass')
def clear_pass():
    parole_active.clear()
    save_data()
    return 'ok'

def start_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ========== МЕНЮ ==========
def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("🆕 Создать пароль", "📋 Список паролей")
    mk.row("📊 Статистика", "👥 Пользователи")
    mk.row("💎 Выдать VIP", "📢 Рассылка")
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

# ========== КОМАНДЫ БОТА ==========

@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    register_new_user(uid, name)
    
    if str(uid) == str(ADMIN_ID):
        bot.send_message(uid, "🔐 Админ панель", reply_markup=admin_menu())
        return
    
    if user_access.get(str(uid), False):
        msg = f"✅ Привет, {name}!\n\n"
        if is_vip(uid):
            expiry = get_vip_expiry(uid)
            msg += f"💎 Ты VIP до {expiry.strftime('%d.%m.%Y')}\n"
            msg += f"🎫 Сегодня: {get_daily_tickets_count(uid)}/10 билетов"
        else:
            msg += f"⭐ Обычный: {NORMAL_DAILY_LIMIT} билетов/день, кулдаун {NORMAL_COOLDOWN_MINUTES} мин\n"
            msg += f"🎫 Сегодня: {get_daily_tickets_count(uid)}/{NORMAL_DAILY_LIMIT}\n\n"
            msg += "Купи VIP за 25 лей/неделя!"
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
            user_stats[str(uid)] = {'name': name, 'tickets': 0}
        save_data()
        bot.send_message(uid, f"✅ Доступ открыт!\n\nОбычный: {NORMAL_DAILY_LIMIT} билетов/день, кулдаун {NORMAL_COOLDOWN_MINUTES} мин\nКупи VIP за {VIP_PRICE} лей/неделя!", reply_markup=user_menu(uid))
        bot.send_message(ADMIN_ID, f"🔓 Новый пользователь: {name} (ID: `{uid}`)", parse_mode='Markdown')
    else:
        bot.send_message(uid, "❌ Неверный код!\nПопробуй ещё раз:")
        bot.register_next_step_handler(m, check_code)

@bot.message_handler(commands=['help'])
def help_cmd(m):
    uid = m.from_user.id
    if str(uid) == str(ADMIN_ID):
        text = """
🤖 **Команды админа:**

/start - Главное меню
/help - Этот список

👑 **Управление:**
/give_vip <ID> <дни> - Выдать VIP
/remove_vip <ID> - Снять VIP
/vip_list - Список VIP
/users - Список пользователей
/stats - Статистика
/ad <текст> - Рассылка

🔑 **Пароли:**
/gen_pass - Создать пароль
/list_pass - Список паролей
/clear_pass - Удалить все
"""
    else:
        daily = get_daily_tickets_count(uid)
        limit = NORMAL_DAILY_LIMIT if not is_vip(uid) else 10
        text = f"""
🤖 **Доступные команды:**

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
        text = f"💎 **VIP статус**\n📅 До: {expiry.strftime('%d.%m.%Y')}\n🎫 Осталось: {10-daily}/10\n⏰ Кулдаун: нет\n💰 Цена билета: {PRET} лей"
    else:
        can, mins = check_can_buy_ticket(uid)
        cd = f"✅ Готов" if can else f"⏰ Жди {mins} мин"
        text = f"⭐ **Обычный режим**\n📅 Сегодня: {daily}/{NORMAL_DAILY_LIMIT}\n{cd}\n💰 Цена: {PRET} лей\n\n💎 Купи VIP: /buy_vip"
    bot.send_message(uid, text, parse_mode='Markdown')

@bot.message_handler(commands=['buy_vip'])
def buy_vip_cmd(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала /start")
        return
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        bot.send_message(uid, f"💎 У тебя уже есть VIP до {expiry.strftime('%d.%m.%Y')}")
        return
    
    username = m.from_user.username or m.from_user.first_name
    user_link = f"@{username}" if username else f"{m.from_user.first_name}"
    
    bot.send_message(ADMIN_ID, f"🟢 Заявка на VIP от {user_link} (ID: `{uid}`)\nВыдать: `/give_vip {uid} {VIP_DAYS}`", parse_mode='Markdown')
    bot.send_message(uid, f"💎 **VIP статус**\n\n💰 Цена: {VIP_PRICE} лей\n📅 Длительность: {VIP_DAYS} дней\n🎫 10 билетов/день, без кулдауна\n\n📩 Свяжись с @RaskovskI для оплаты", parse_mode='Markdown')

# ========== АДМИН КОМАНДЫ ==========

@bot.message_handler(commands=['give_vip'])
def give_vip_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(ADMIN_ID, "❌ /give_vip ID дни\nПример: /give_vip 7072265211 7")
            return
        user_id = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else VIP_DAYS
        set_vip(user_id, days)
        bot.send_message(ADMIN_ID, f"✅ VIP выдан пользователю {user_id} на {days} дней")
        try:
            bot.send_message(user_id, f"💎 VIP активирован на {days} дней!\nДо: {(get_time() + timedelta(days=days)).strftime('%d.%m.%Y')}")
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
        user_id = int(parts[1])
        remove_vip(user_id)
        bot.send_message(ADMIN_ID, f"✅ VIP снят с {user_id}")
    except:
        bot.send_message(ADMIN_ID, "❌ /remove_vip ID")

@bot.message_handler(commands=['vip_list'])
def vip_list_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    text = "💎 VIP пользователи:\n"
    count = 0
    for uid, expiry_str in user_vip.items():
        expiry = datetime.fromisoformat(expiry_str)
        if expiry > get_time():
            name = user_stats.get(uid, {}).get('name', 'Unknown')
            days_left = (expiry - get_time()).days
            text += f"• {name} (ID:{uid}) - {days_left} дн.\n"
            count += 1
    bot.send_message(ADMIN_ID, text if count else "❌ Нет VIP")

@bot.message_handler(commands=['users'])
def users_list_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    text = "👥 Пользователи:\n"
    for uid, access in user_access.items():
        if access:
            stats = user_stats.get(uid, {})
            name = stats.get('name', 'Unknown')
            tickets = stats.get('tickets', 0)
            vip = "💎" if is_vip(int(uid)) else "⭐"
            text += f"{vip} {name} - {tickets} билетов (ID:{uid})\n"
    bot.send_message(ADMIN_ID, text if len(text) > 15 else "❌ Нет пользователей")

@bot.message_handler(commands=['stats'])
def stats_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    active = len([u for u in user_access if user_access[u]])
    vip = len([u for u in user_vip if datetime.fromisoformat(user_vip[u]) > get_time()])
    text = f"📊 Статистика\n👥 Пользователей: {active}\n💎 VIP: {vip}\n🎫 Билетов: {len(bilete_active)}\n💰 Выручка: {len(bilete_active) * PRET} MDL"
    bot.send_message(ADMIN_ID, text)

@bot.message_handler(commands=['ad'])
def ad_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    msg = bot.send_message(ADMIN_ID, "✏️ Введи текст рассылки:")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(m):
    sent = 0
    for uid, access in user_access.items():
        if access:
            try:
                bot.send_message(int(uid), f"📢 {m.text}")
                sent += 1
                time.sleep(0.05)
            except:
                pass
    bot.send_message(ADMIN_ID, f"✅ Отправлено {sent} пользователям")

@bot.message_handler(commands=['gen_pass'])
def gen_pass_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    p = gen_parola()
    parole_active.append(p)
    save_data()
    bot.send_message(ADMIN_ID, f"🆕 Пароль: `{p}`", parse_mode='Markdown')

@bot.message_handler(commands=['list_pass'])
def list_pass_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    if parole_active:
        bot.send_message(ADMIN_ID, f"📋 Пароли: {', '.join(parole_active)}")
    else:
        bot.send_message(ADMIN_ID, "❌ Нет паролей")

@bot.message_handler(commands=['clear_pass'])
def clear_pass_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    parole_active.clear()
    save_data()
    bot.send_message(ADMIN_ID, "✅ Все пароли удалены")

# ========== ОБРАБОТЧИК КНОПОК И СООБЩЕНИЙ ==========
@bot.message_handler(func=lambda m: m.text == "❓ Команды")
def commands_btn(m):
    help_cmd(m)

@bot.message_handler(func=lambda m: m.text == "⭐ Купить VIP")
def buy_vip_btn(m):
    buy_vip_cmd(m)

@bot.message_handler(func=lambda m: m.text == "💎 Мой VIP" or m.text == "⏰ Мой статус")
def status_btn(m):
    status_cmd(m)

@bot.message_handler(func=lambda m: m.text == "🎫 Купить билет")
def buy_ticket_btn(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала введи код доступа через /start")
        return
    bot.send_message(uid, "🚌 Введи номер автобуса (2000-2099):", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, process_ticket_number)

def process_ticket_number(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    text = m.text.strip()
    
    if not re.match(r'^\d{4}$', text):
        bot.send_message(uid, "❌ Нужно 4 цифры (2000-2099)!", reply_markup=user_menu(uid))
        return
    
    cod = int(text)
    if cod < 2000 or cod > 2099:
        bot.send_message(uid, f"❌ {cod} не в диапазоне 2000-2099", reply_markup=user_menu(uid))
        return
    
    can, mins = check_can_buy_ticket(uid)
    if not can:
        if mins > 0:
            bot.send_message(uid, f"⏰ Жди {mins} мин!", reply_markup=user_menu(uid))
        else:
            bot.send_message(uid, f"❌ Лимит {NORMAL_DAILY_LIMIT} билетов в день!", reply_markup=user_menu(uid))
        return
    
    threading.Thread(target=issue_ticket, args=(uid, uid, cod, name)).start()

# Обработка прямого ввода номера автобуса
@bot.message_handler(func=lambda m: m.text and m.text.isdigit() and len(m.text) == 4 and 2000 <= int(m.text) <= 2099)
def direct_ticket(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала введи код доступа через /start")
        return
    
    cod = int(m.text)
    name = m.from_user.first_name
    
    can, mins = check_can_buy_ticket(uid)
    if not can:
        if mins > 0:
            bot.send_message(uid, f"⏰ Жди {mins} мин!", reply_markup=user_menu(uid))
        else:
            bot.send_message(uid, f"❌ Лимит {NORMAL_DAILY_LIMIT} билетов в день!", reply_markup=user_menu(uid))
        return
    
    threading.Thread(target=issue_ticket, args=(uid, uid, cod, name)).start()

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    load_data()
    
    # Запускаем проверку VIP каждые 6 часов
    def vip_checker():
        while True:
            time.sleep(21600)
            check_expired_vip()
    threading.Thread(target=vip_checker, daemon=True).start()
    
    # Запускаем веб-сервер
    threading.Thread(target=start_web, daemon=True).start()
    
    # Удаляем вебхук на всякий случай
    try:
        bot.remove_webhook()
    except:
        pass
    
    print("=" * 50)
    print("✅ БОТ ЗАПУЩЕН")
   
