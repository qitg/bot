import telebot
from datetime import datetime, timedelta
import random
import re
import json
import os
import timimport telebot
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

# Цены и лимиты
PRET = 6  # цена обычного билета
VIP_PRICE = 25  # цена VIP на неделю
VIP_DAYS = 7  # сколько дней действует VIP

# Лимиты для обычных пользователей
NORMAL_DAILY_LIMIT = 3  # 3 билета в день
NORMAL_COOLDOWN_MINUTES = 45  # кулдаун 45 минут

bilete_active = {}
user_access = {}
user_cooldown = {}
parole_active = []
user_stats = {}
user_vip = {}  # {user_id: expiry_date_iso}
user_daily_tickets = {}  # {user_id: {'count': 0, 'date': '2024-01-01'}}

DATA_FILE = "bot_data.json"

def load_data():
    global bilete_active, user_access, user_cooldown, parole_active, user_stats, user_vip, user_daily_tickets
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

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'tickets': bilete_active,
            'access': user_access,
            'cooldown': user_cooldown,
            'passwords': parole_active,
            'stats': user_stats,
            'vip': user_vip,
            'daily_tickets': user_daily_tickets
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

def remove_vip(user_id):
    uid = str(user_id)
    if uid in user_vip:
        del user_vip[uid]
        save_data()

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
    uid = str(user_id)
    
    if is_vip(user_id):
        daily_count = get_daily_tickets_count(user_id)
        if daily_count >= 10:
            return False, "❌ У VIP лимит 10 билетов в день. Завтра будут новые!"
        return True, 0, "vip"
    
    if str(user_id) == str(ADMIN_ID):
        return True, 0, "admin"
    
    last = user_cooldown.get(uid)
    if last:
        last_time = datetime.fromisoformat(last)
        now = get_time()
        passed = now - last_time
        if passed < timedelta(minutes=NORMAL_COOLDOWN_MINUTES):
            remaining = timedelta(minutes=NORMAL_COOLDOWN_MINUTES) - passed
            return False, int(remaining.total_seconds() // 60), "normal"
    
    daily_count = get_daily_tickets_count(user_id)
    if daily_count >= NORMAL_DAILY_LIMIT:
        return False, 0, "limit"
    
    return True, 0, "normal"

def set_cooldown(user_id):
    user_cooldown[str(user_id)] = get_time().isoformat()
    save_data()

def update_stats(user_id, name):
    uid = str(user_id)
    if uid not in user_stats:
        user_stats[uid] = {'name': name, 'tickets': 0, 'vip_bought': False}
    user_stats[uid]['tickets'] += 1
    save_data()

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
                <tr><th>ID</th><th>Имя</th><th>Билетов</th><th>VIP</th><th>Статус</th><th>Кулдаун</th></tr>
                {% for u in users %}
                <tr>
                    <td>{{ u.id }}</td>
                    <td>{{ u.name }} {% if u.vip %}<span class="vip-badge">💎 VIP</span>{% endif %}</td>
                    <td>{{ u.tickets }}</td>
                    <td>{% if u.vip_expiry %}до {{ u.vip_expiry }}{% else %}—{% endif %}</td>
                    <td>{% if u.access %}✅ Активен{% else %}❌ Блок{% endif %}</td>
                    <td>{% if u.cooldown > 0 %}{{ u.cooldown }} мин{% else %}✅ Готов{% endif %}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        <div id="tickets" class="tab-content">
            <h3>Последние билеты</h3>
            <tr>
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
            cd = user_cooldown.get(uid)
            remaining = 0
            if cd and not is_vip(int(uid)):
                last = datetime.fromisoformat(cd)
                passed = (get_time() - last).total_seconds() / 60
                remaining = max(0, int(NORMAL_COOLDOWN_MINUTES - passed))
            
            vip_expiry = get_vip_expiry(int(uid))
            users.append({
                'id': uid,
                'name': stats.get('name', 'Unknown'),
                'tickets': stats.get('tickets', 0),
                'vip': vip_expiry is not None,
                'vip_expiry': vip_expiry.strftime('%d.%m') if vip_expiry else None,
                'access': access,
                'cooldown': remaining
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
    mk.row("🗑 Сброс паролей", "🌐 Открыть сайт")
    mk.row("❓ Команды")
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

# ========== КОМАНДЫ БОТА ==========

# Команда /help - список всех команд
@bot.message_handler(commands=['help', 'start'])
def send_help(m):
    uid = m.from_user.id
    
    if str(uid) == str(ADMIN_ID):
        help_text = """
🤖 **Команды бота (Админ)**

📌 **Основные:**
/start - Главное меню
/help - Список команд

👑 **Админ команды:**
/admin - Открыть админ меню
/give_vip [ID] [дни] - Выдать VIP (пример: /give_vip 7072265211 7)
/users - Список всех пользователей
/stats - Статистика бота
/ad [текст] - Сделать рассылку
/site - Ссылка на админ панель

🎫 **Управление паролями:**
/gen_pass - Создать пароль
/list_pass - Список паролей
/clear_pass - Удалить все пароли

💎 **VIP:**
/vip_list - Список VIP пользователей
/remove_vip [ID] - Снять VIP

📊 **Статистика:**
/tickets - Последние билеты
"""
    else:
        daily = get_daily_tickets_count(uid)
        limit = NORMAL_DAILY_LIMIT if not is_vip(uid) else 10
        
        help_text = f"""
🤖 **Доступные команды**

/start - Главное меню
/help - Этот список команд
/buy_vip - Купить VIP статус

🎫 **Покупка билетов:**
• Напиши номер автобуса (2000-2099)
• Или нажми кнопку "Купить билет"

📊 **Статус:**
/status - Проверить лимиты и кулдаун

💰 **Тарифы:**
⭐ Обычный: {NORMAL_DAILY_LIMIT} билетов/день, кулдаун {NORMAL_COOLDOWN_MINUTES} мин
💎 VIP: 10 билетов/день, без кулдауна - {VIP_PRICE} лей/неделя

📅 **Сегодня использовано:** {daily}/{limit} билетов

❓ Есть вопросы? @RaskovskI
"""
    bot.send_message(uid, help_text, parse_mode='Markdown')

# Команда /status
@bot.message_handler(commands=['status'])
def status_command(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала введи код доступа через /start")
        return
    
    daily_count = get_daily_tickets_count(uid)
    
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        text = f"""
💎 **Твой VIP статус**

📅 Действует до: {expiry.strftime('%d.%m.%Y %H:%M')}
🎫 Осталось билетов сегодня: {10 - daily_count}
⏰ Кулдаун: отсутствует
💰 Цена билета: {PRET} лей
"""
    else:
        can, mins, _ = check_can_buy_ticket(uid)
        cooldown_text = "✅ Можешь купить билет" if can else f"⏰ Кулдаун: {mins} мин"
        text = f"""
⭐ **Обычный режим**

📅 Сегодня использовано: {daily_count}/{NORMAL_DAILY_LIMIT} билетов
{cooldown_text}
💰 Цена билета: {PRET} лей

💎 Купи VIP за {VIP_PRICE} лей/неделя:
• 10 билетов в день
• Без кулдауна
• Приоритетная поддержка

Напиши /buy_vip
"""
    bot.send_message(uid, text, parse_mode='Markdown')

# Команда /buy_vip
@bot.message_handler(commands=['buy_vip'])
def buy_vip(m):
    uid = m.from_user.id
    username = m.from_user.username or m.from_user.first_name
    user_link = f"@{username}" if username else f"[{m.from_user.first_name}](tg://user?id={uid})"
    
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала введи код доступа через /start")
        return
    
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        bot.send_message(uid, f"💎 У тебя уже есть VIP до {expiry.strftime('%d.%m.%Y')}")
        return
    
    bot.send_message(ADMIN_ID, 
        f"🟢 **НОВАЯ ЗАЯВКА НА VIP**\n\n"
        f"👤 Пользователь: {user_link}\n"
        f"🆔 ID: `{uid}`\n"
        f"📝 Имя: {m.from_user.first_name}\n"
        f"💰 Сумма: {VIP_PRICE} лей\n"
        f"📅 Дней: {VIP_DAYS}\n\n"
        f"✅ Чтобы выдать VIP, отправь:\n`/give_vip {uid} {VIP_DAYS}`",
        parse_mode='Markdown')
    
    bot.send_message(uid, 
        f"💎 **VIP статус**\n\n"
        f"💰 Цена: {VIP_PRICE} лей\n"
        f"📅 Длительность: {VIP_DAYS} дней\n"
        f"🎫 Преимущества: 10 билетов в день, без кулдауна\n\n"
        f"📩 **Свяжись с админом:** @RaskovskI\n\n"
        f"После оплаты админ активирует VIP статус командой /give_vip",
        parse_mode='Markdown')

# Команда /users (админ)
@bot.message_handler(commands=['users'])
def list_users_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    if not user_access:
        bot.send_message(ADMIN_ID, "❌ Нет пользователей")
        return
    
    text = "👥 **Список пользователей:**\n\n"
    for uid, access in user_access.items():
        if access:
            stats = user_stats.get(uid, {})
            name = stats.get('name', 'Unknown')
            tickets = stats.get('tickets', 0)
            vip = "💎" if is_vip(int(uid)) else "⭐"
            text += f"{vip} `{uid}` - {name} - {tickets} билетов\n"
    
    if len(text) > 4000:
        text = text[:4000]
    
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

# Команда /give_vip (админ)
@bot.message_handler(commands=['give_vip'])
def give_vip_command(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(ADMIN_ID, "❌ Используй: `/give_vip ID дни`\nПример: `/give_vip 7072265211 7`", parse_mode='Markdown')
            return
        
        user_id = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else VIP_DAYS
        
        set_vip(user_id, days)
        
        bot.send_message(ADMIN_ID, f"✅ VIP выдан пользователю `{user_id}` на {days} дней", parse_mode='Markdown')
        
        try:
            bot.send_message(user_id, 
                f"💎 **VIP статус активирован!**\n\n"
                f"📅 Действует до: {(get_time() + timedelta(days=days)).strftime('%d.%m.%Y %H:%M')}\n"
                f"🎫 Теперь у тебя: 10 билетов в день\n"
                f"⏰ Без кулдауна!\n\n"
                f"Напиши /start чтобы увидеть изменения",
                parse_mode='Markdown')
        except:
            bot.send_message(ADMIN_ID, f"⚠️ Не удалось отправить уведомление пользователю {user_id}")
            
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка: {e}")

# Команда /remove_vip (админ)
@bot.message_handler(commands=['remove_vip'])
def remove_vip_command(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(ADMIN_ID, "❌ Используй: `/remove_vip ID`", parse_mode='Markdown')
            return
        
        user_id = int(parts[1])
        remove_vip(user_id)
        
        bot.send_message(ADMIN_ID, f"✅ VIP снят с пользователя `{user_id}`", parse_mode='Markdown')
        
        try:
            bot.send_message(user_id, "💎 Ваш VIP статус был снят администратором")
        except:
            pass
            
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка: {e}")

# Команда /vip_list (админ)
@bot.message_handler(commands=['vip_list'])
def vip_list_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    text = "💎 **VIP пользователи:**\n\n"
    count = 0
    for uid, expiry_str in user_vip.items():
        expiry = datetime.fromisoformat(expiry_str)
        if expiry > get_time():
            stats = user_stats.get(uid, {})
            name = stats.get('name', 'Unknown')
            days_left = (expiry - get_time()).days
            text += f"• `{uid}` - {name} - осталось {days_left} дн.\n"
            count += 1
    
    if count == 0:
        text = "❌ Нет активных VIP пользователей"
    
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

# Команда /stats (админ)
@bot.message_handler(commands=['stats'])
def stats_command(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    active_users = len([u for u in user_access if user_access[u]])
    vip_count = len([u for u in user_vip if datetime.fromisoformat(user_vip[u]) > get_time()])
    today_tickets = len([b for b in bilete_active.values() if b.get('date') == get_time().strftime('%d.%m.%Y')])
    
    text = f"""
📊 **Статистика бота**

👥 Всего пользователей: {active_users}
💎 VIP пользователей: {vip_count}
🎫 Всего билетов: {len(bilete_active)}
📅 Билетов сегодня: {today_tickets}
💰 Выручка: {len(bilete_active) * PRET} MDL
⭐ Обычный лимит: {NORMAL_DAILY_LIMIT} билетов/день
⏰ Обычный кулдаун: {NORMAL_COOLDOWN_MINUTES} мин
💎 VIP лимит: 10 билетов/день
💎 VIP цена: {VIP_PRICE} лей/{VIP_DAYS} дней
"""
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

# Команда /tickets (админ)
@bot.message_handler(commands=['tickets'])
def tickets_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    if not bilete_active:
        bot.send_message(ADMIN_ID, "❌ Нет билетов")
        return
    
    text = "🎫 **Последние 20 билетов:**\n\n"
    for nr, b in list(bilete_active.items())[-20:]:
        text += f"• Билет `{nr}` - Автобус {b.get('bus')} - {b.get('user_name')} - {b.get('date')} {b.get('time')}\n"
    
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

# Команда /ad (админ - рассылка)
@bot.message_handler(commands=['ad'])
def ad_command(m):
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

# Команда /gen_pass (админ)
@bot.message_handler(commands=['gen_pass'])
def gen_pass_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    p = gen_parola()
    parole_active.append(p)
    save_data()
    bot.send_message(ADMIN_ID, f"🆕 Пароль: `{p}`", parse_mode='Markdown')

# Команда /list_pass (админ)
@bot.message_handler(commands=['list_pass'])
def list_pass_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    if parole_active:
        bot.send_message(ADMIN_ID, "📋 Пароли:\n" + "\n".join(parole_active))
    else:
        bot.send_message(ADMIN_ID, "❌ Нет паролей")

# Команда /clear_pass (админ)
@bot.message_handler(commands=['clear_pass'])
def clear_pass_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    parole_active.clear()
    save_data()
    bot.send_message(ADMIN_ID, "✅ Все пароли удалены")

# Команда /site (админ)
@bot.message_handler(commands=['site'])
def site_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    bot.send_message(ADMIN_ID, "🌐 Админ сайт доступен по ссылке от Render/Railway")

# Команда /admin (админ меню)
@bot.message_handler(commands=['admin'])
def admin_panel(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        bot.send_message(ADMIN_ID, "🔐 Админ панель", reply_markup=admin_menu())
    else:
        bot.send_message(m.chat.id, "❌ Нет доступа")

# ========== ОБРАБОТЧИКИ КНОПОК ==========

@bot.message_handler(func=lambda m: m.text == "💎 Выдать VIP" and str(m.from_user.id) == str(ADMIN_ID))
def give_vip_button(m):
    bot.send_message(ADMIN_ID, 
        "💎 **Выдать VIP**\n\n"
        "Используй команду:\n"
        "`/give_vip ID дни`\n\n"
        "Пример: `/give_vip 7072265211 7`\n\n"
        "Список пользователей: /users\n"
        "Список VIP: /vip_list", 
        parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📢 Рассылка" and str(m.from_user.id) == str(ADMIN_ID))
def ad_button(m):
    ad_command(m)

@bot.message_handler(func=lambda m: m.text == "❓ Команды")
def commands_button(m):
    send_help(m)

@bot.message_handler(func=lambda m: m.text == "⭐ Купить VIP")
def buy_vip_button(m):
    buy_vip(m)

@bot.message_handler(func=lambda m: m.text == "💎 Мой VIP")
def my_vip_button(m):
    status_command(m)

@bot.message_handler(func=lambda m: m.text == "⏰ Мой статус")
def status_button(m):
    status_command(m)

@bot.message_handler(func=lambda m: m.text == "🆕 Создать пароль" and str(m.from_user.id) == str(ADMIN_ID))
def cp(m):
    p = gen_parola()
    parole_active.append(p)
    save_data()
    bot.send_message(ADMIN_ID, f"🆕 Пароль: `{p}`", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📋 Список паролей" and str(m.from_user.id) == str(ADMIN_ID))
def lp(m):
    if parole_active:
        bot.send_message(ADMIN_ID, "📋 Пароли:\n" + "\n".join(parole_active))
    else:
        bot.send_message(ADMIN_ID, "❌ Нет паролей")

@bot.message_handler(func=lambda m: m.text == "📊 Статистика" and str(m.from_user.id) == str(ADMIN_ID))
def st(m):
    stats_command(m)

@bot.message_handler(func=lambda m: m.text == "👥 Пользователи" and str(m.from_user.id) == str(ADMIN_ID))
def ul(m):
    list_users_admin(m)

@bot.message_handler(func=lambda m: m.text == "🌐 Открыть сайт" and str(m.from_user.id) == str(ADMIN_ID))
def osite(m):
    bot.send_message(ADMIN_ID, "🌐 Админ сайт доступен по ссылке от Render/Railway")

@bot.message_handler(func=lambda m: m.text == "🗑 Сброс паролей" and str(m.from_user.id) == str(ADMIN_ID))
def rp(m):
    parole_active.clear()
    save_data()
    bot.send
import threading
from flask import Flask, render_template_string, request

# ========== КОНФИГ ==========
TOKEN = "8307596159:AAES-a6TjEaAaP_j6LPogq2Eb9vsoBqtL4o"
ADMIN_ID = 7072265211

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

def get_time():
    return datetime.utcnow() + timedelta(hours=3)

# Цены и лимиты
PRET = 6  # цена обычного билета
VIP_PRICE = 25  # цена VIP на неделю
VIP_DAYS = 7  # сколько дней действует VIP

# Лимиты для обычных пользователей
NORMAL_DAILY_LIMIT = 3  # 3 билета в день
NORMAL_COOLDOWN_MINUTES = 45  # кулдаун 45 минут

bilete_active = {}
user_access = {}
user_cooldown = {}
parole_active = []
user_stats = {}
user_vip = {}  # {user_id: expiry_date_iso}
user_daily_tickets = {}  # {user_id: {'count': 0, 'date': '2024-01-01'}}

DATA_FILE = "bot_data.json"

def load_data():
    global bilete_active, user_access, user_cooldown, parole_active, user_stats, user_vip, user_daily_tickets
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

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'tickets': bilete_active,
            'access': user_access,
            'cooldown': user_cooldown,
            'passwords': parole_active,
            'stats': user_stats,
            'vip': user_vip,
            'daily_tickets': user_daily_tickets
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

def remove_vip(user_id):
    uid = str(user_id)
    if uid in user_vip:
        del user_vip[uid]
        save_data()

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
    uid = str(user_id)
    
    if is_vip(user_id):
        daily_count = get_daily_tickets_count(user_id)
        if daily_count >= 10:
            return False, "❌ У VIP лимит 10 билетов в день. Завтра будут новые!"
        return True, 0, "vip"
    
    if str(user_id) == str(ADMIN_ID):
        return True, 0, "admin"
    
    last = user_cooldown.get(uid)
    if last:
        last_time = datetime.fromisoformat(last)
        now = get_time()
        passed = now - last_time
        if passed < timedelta(minutes=NORMAL_COOLDOWN_MINUTES):
            remaining = timedelta(minutes=NORMAL_COOLDOWN_MINUTES) - passed
            return False, int(remaining.total_seconds() // 60), "normal"
    
    daily_count = get_daily_tickets_count(user_id)
    if daily_count >= NORMAL_DAILY_LIMIT:
        return False, 0, "limit"
    
    return True, 0, "normal"

def set_cooldown(user_id):
    user_cooldown[str(user_id)] = get_time().isoformat()
    save_data()

def update_stats(user_id, name):
    uid = str(user_id)
    if uid not in user_stats:
        user_stats[uid] = {'name': name, 'tickets': 0, 'vip_bought': False}
    user_stats[uid]['tickets'] += 1
    save_data()

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
                <tr><th>ID</th><th>Имя</th><th>Билетов</th><th>VIP</th><th>Статус</th><th>Кулдаун</th></tr>
                {% for u in users %}
                <tr>
                    <td>{{ u.id }}</td>
                    <td>{{ u.name }} {% if u.vip %}<span class="vip-badge">💎 VIP</span>{% endif %}</td>
                    <td>{{ u.tickets }}</td>
                    <td>{% if u.vip_expiry %}до {{ u.vip_expiry }}{% else %}—{% endif %}</td>
                    <td>{% if u.access %}✅ Активен{% else %}❌ Блок{% endif %}</td>
                    <td>{% if u.cooldown > 0 %}{{ u.cooldown }} мин{% else %}✅ Готов{% endif %}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        <div id="tickets" class="tab-content">
            <h3>Последние билеты</h3>
            <tr>
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
            cd = user_cooldown.get(uid)
            remaining = 0
            if cd and not is_vip(int(uid)):
                last = datetime.fromisoformat(cd)
                passed = (get_time() - last).total_seconds() / 60
                remaining = max(0, int(NORMAL_COOLDOWN_MINUTES - passed))
            
            vip_expiry = get_vip_expiry(int(uid))
            users.append({
                'id': uid,
                'name': stats.get('name', 'Unknown'),
                'tickets': stats.get('tickets', 0),
                'vip': vip_expiry is not None,
                'vip_expiry': vip_expiry.strftime('%d.%m') if vip_expiry else None,
                'access': access,
                'cooldown': remaining
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
    mk.row("🗑 Сброс паролей", "🌐 Открыть сайт")
    mk.row("❓ Команды")
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

# ========== КОМАНДЫ БОТА ==========

# Команда /help - список всех команд
@bot.message_handler(commands=['help', 'start'])
def send_help(m):
    uid = m.from_user.id
    
    if str(uid) == str(ADMIN_ID):
        help_text = """
🤖 **Команды бота (Админ)**

📌 **Основные:**
/start - Главное меню
/help - Список команд

👑 **Админ команды:**
/admin - Открыть админ меню
/give_vip [ID] [дни] - Выдать VIP (пример: /give_vip 7072265211 7)
/users - Список всех пользователей
/stats - Статистика бота
/ad [текст] - Сделать рассылку
/site - Ссылка на админ панель

🎫 **Управление паролями:**
/gen_pass - Создать пароль
/list_pass - Список паролей
/clear_pass - Удалить все пароли

💎 **VIP:**
/vip_list - Список VIP пользователей
/remove_vip [ID] - Снять VIP

📊 **Статистика:**
/tickets - Последние билеты
"""
    else:
        daily = get_daily_tickets_count(uid)
        limit = NORMAL_DAILY_LIMIT if not is_vip(uid) else 10
        
        help_text = f"""
🤖 **Доступные команды**

/start - Главное меню
/help - Этот список команд
/buy_vip - Купить VIP статус

🎫 **Покупка билетов:**
• Напиши номер автобуса (2000-2099)
• Или нажми кнопку "Купить билет"

📊 **Статус:**
/status - Проверить лимиты и кулдаун

💰 **Тарифы:**
⭐ Обычный: {NORMAL_DAILY_LIMIT} билетов/день, кулдаун {NORMAL_COOLDOWN_MINUTES} мин
💎 VIP: 10 билетов/день, без кулдауна - {VIP_PRICE} лей/неделя

📅 **Сегодня использовано:** {daily}/{limit} билетов

❓ Есть вопросы? @RaskovskI
"""
    bot.send_message(uid, help_text, parse_mode='Markdown')

# Команда /status
@bot.message_handler(commands=['status'])
def status_command(m):
    uid = m.from_user.id
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала введи код доступа через /start")
        return
    
    daily_count = get_daily_tickets_count(uid)
    
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        text = f"""
💎 **Твой VIP статус**

📅 Действует до: {expiry.strftime('%d.%m.%Y %H:%M')}
🎫 Осталось билетов сегодня: {10 - daily_count}
⏰ Кулдаун: отсутствует
💰 Цена билета: {PRET} лей
"""
    else:
        can, mins, _ = check_can_buy_ticket(uid)
        cooldown_text = "✅ Можешь купить билет" if can else f"⏰ Кулдаун: {mins} мин"
        text = f"""
⭐ **Обычный режим**

📅 Сегодня использовано: {daily_count}/{NORMAL_DAILY_LIMIT} билетов
{cooldown_text}
💰 Цена билета: {PRET} лей

💎 Купи VIP за {VIP_PRICE} лей/неделя:
• 10 билетов в день
• Без кулдауна
• Приоритетная поддержка

Напиши /buy_vip
"""
    bot.send_message(uid, text, parse_mode='Markdown')

# Команда /buy_vip
@bot.message_handler(commands=['buy_vip'])
def buy_vip(m):
    uid = m.from_user.id
    username = m.from_user.username or m.from_user.first_name
    user_link = f"@{username}" if username else f"[{m.from_user.first_name}](tg://user?id={uid})"
    
    if not user_access.get(str(uid), False):
        bot.send_message(uid, "❌ Сначала введи код доступа через /start")
        return
    
    if is_vip(uid):
        expiry = get_vip_expiry(uid)
        bot.send_message(uid, f"💎 У тебя уже есть VIP до {expiry.strftime('%d.%m.%Y')}")
        return
    
    bot.send_message(ADMIN_ID, 
        f"🟢 **НОВАЯ ЗАЯВКА НА VIP**\n\n"
        f"👤 Пользователь: {user_link}\n"
        f"🆔 ID: `{uid}`\n"
        f"📝 Имя: {m.from_user.first_name}\n"
        f"💰 Сумма: {VIP_PRICE} лей\n"
        f"📅 Дней: {VIP_DAYS}\n\n"
        f"✅ Чтобы выдать VIP, отправь:\n`/give_vip {uid} {VIP_DAYS}`",
        parse_mode='Markdown')
    
    bot.send_message(uid, 
        f"💎 **VIP статус**\n\n"
        f"💰 Цена: {VIP_PRICE} лей\n"
        f"📅 Длительность: {VIP_DAYS} дней\n"
        f"🎫 Преимущества: 10 билетов в день, без кулдауна\n\n"
        f"📩 **Свяжись с админом:** @RaskovskI\n\n"
        f"После оплаты админ активирует VIP статус командой /give_vip",
        parse_mode='Markdown')

# Команда /users (админ)
@bot.message_handler(commands=['users'])
def list_users_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    if not user_access:
        bot.send_message(ADMIN_ID, "❌ Нет пользователей")
        return
    
    text = "👥 **Список пользователей:**\n\n"
    for uid, access in user_access.items():
        if access:
            stats = user_stats.get(uid, {})
            name = stats.get('name', 'Unknown')
            tickets = stats.get('tickets', 0)
            vip = "💎" if is_vip(int(uid)) else "⭐"
            text += f"{vip} `{uid}` - {name} - {tickets} билетов\n"
    
    if len(text) > 4000:
        text = text[:4000]
    
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

# Команда /give_vip (админ)
@bot.message_handler(commands=['give_vip'])
def give_vip_command(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(ADMIN_ID, "❌ Используй: `/give_vip ID дни`\nПример: `/give_vip 7072265211 7`", parse_mode='Markdown')
            return
        
        user_id = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else VIP_DAYS
        
        set_vip(user_id, days)
        
        bot.send_message(ADMIN_ID, f"✅ VIP выдан пользователю `{user_id}` на {days} дней", parse_mode='Markdown')
        
        try:
            bot.send_message(user_id, 
                f"💎 **VIP статус активирован!**\n\n"
                f"📅 Действует до: {(get_time() + timedelta(days=days)).strftime('%d.%m.%Y %H:%M')}\n"
                f"🎫 Теперь у тебя: 10 билетов в день\n"
                f"⏰ Без кулдауна!\n\n"
                f"Напиши /start чтобы увидеть изменения",
                parse_mode='Markdown')
        except:
            bot.send_message(ADMIN_ID, f"⚠️ Не удалось отправить уведомление пользователю {user_id}")
            
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка: {e}")

# Команда /remove_vip (админ)
@bot.message_handler(commands=['remove_vip'])
def remove_vip_command(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(ADMIN_ID, "❌ Используй: `/remove_vip ID`", parse_mode='Markdown')
            return
        
        user_id = int(parts[1])
        remove_vip(user_id)
        
        bot.send_message(ADMIN_ID, f"✅ VIP снят с пользователя `{user_id}`", parse_mode='Markdown')
        
        try:
            bot.send_message(user_id, "💎 Ваш VIP статус был снят администратором")
        except:
            pass
            
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка: {e}")

# Команда /vip_list (админ)
@bot.message_handler(commands=['vip_list'])
def vip_list_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    text = "💎 **VIP пользователи:**\n\n"
    count = 0
    for uid, expiry_str in user_vip.items():
        expiry = datetime.fromisoformat(expiry_str)
        if expiry > get_time():
            stats = user_stats.get(uid, {})
            name = stats.get('name', 'Unknown')
            days_left = (expiry - get_time()).days
            text += f"• `{uid}` - {name} - осталось {days_left} дн.\n"
            count += 1
    
    if count == 0:
        text = "❌ Нет активных VIP пользователей"
    
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

# Команда /stats (админ)
@bot.message_handler(commands=['stats'])
def stats_command(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    active_users = len([u for u in user_access if user_access[u]])
    vip_count = len([u for u in user_vip if datetime.fromisoformat(user_vip[u]) > get_time()])
    today_tickets = len([b for b in bilete_active.values() if b.get('date') == get_time().strftime('%d.%m.%Y')])
    
    text = f"""
📊 **Статистика бота**

👥 Всего пользователей: {active_users}
💎 VIP пользователей: {vip_count}
🎫 Всего билетов: {len(bilete_active)}
📅 Билетов сегодня: {today_tickets}
💰 Выручка: {len(bilete_active) * PRET} MDL
⭐ Обычный лимит: {NORMAL_DAILY_LIMIT} билетов/день
⏰ Обычный кулдаун: {NORMAL_COOLDOWN_MINUTES} мин
💎 VIP лимит: 10 билетов/день
💎 VIP цена: {VIP_PRICE} лей/{VIP_DAYS} дней
"""
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

# Команда /tickets (админ)
@bot.message_handler(commands=['tickets'])
def tickets_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    
    if not bilete_active:
        bot.send_message(ADMIN_ID, "❌ Нет билетов")
        return
    
    text = "🎫 **Последние 20 билетов:**\n\n"
    for nr, b in list(bilete_active.items())[-20:]:
        text += f"• Билет `{nr}` - Автобус {b.get('bus')} - {b.get('user_name')} - {b.get('date')} {b.get('time')}\n"
    
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

# Команда /ad (админ - рассылка)
@bot.message_handler(commands=['ad'])
def ad_command(m):
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

# Команда /gen_pass (админ)
@bot.message_handler(commands=['gen_pass'])
def gen_pass_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    p = gen_parola()
    parole_active.append(p)
    save_data()
    bot.send_message(ADMIN_ID, f"🆕 Пароль: `{p}`", parse_mode='Markdown')

# Команда /list_pass (админ)
@bot.message_handler(commands=['list_pass'])
def list_pass_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    if parole_active:
        bot.send_message(ADMIN_ID, "📋 Пароли:\n" + "\n".join(parole_active))
    else:
        bot.send_message(ADMIN_ID, "❌ Нет паролей")

# Команда /clear_pass (админ)
@bot.message_handler(commands=['clear_pass'])
def clear_pass_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    parole_active.clear()
    save_data()
    bot.send_message(ADMIN_ID, "✅ Все пароли удалены")

# Команда /site (админ)
@bot.message_handler(commands=['site'])
def site_admin(m):
    if str(m.from_user.id) != str(ADMIN_ID):
        return
    bot.send_message(ADMIN_ID, "🌐 Админ сайт доступен по ссылке от Render/Railway")

# Команда /admin (админ меню)
@bot.message_handler(commands=['admin'])
def admin_panel(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        bot.send_message(ADMIN_ID, "🔐 Админ панель", reply_markup=admin_menu())
    else:
        bot.send_message(m.chat.id, "❌ Нет доступа")

# ========== ОБРАБОТЧИКИ КНОПОК ==========

@bot.message_handler(func=lambda m: m.text == "💎 Выдать VIP" and str(m.from_user.id) == str(ADMIN_ID))
def give_vip_button(m):
    bot.send_message(ADMIN_ID, 
        "💎 **Выдать VIP**\n\n"
        "Используй команду:\n"
        "`/give_vip ID дни`\n\n"
        "Пример: `/give_vip 7072265211 7`\n\n"
        "Список пользователей: /users\n"
        "Список VIP: /vip_list", 
        parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📢 Рассылка" and str(m.from_user.id) == str(ADMIN_ID))
def ad_button(m):
    ad_command(m)

@bot.message_handler(func=lambda m: m.text == "❓ Команды")
def commands_button(m):
    send_help(m)

@bot.message_handler(func=lambda m: m.text == "⭐ Купить VIP")
def buy_vip_button(m):
    buy_vip(m)

@bot.message_handler(func=lambda m: m.text == "💎 Мой VIP")
def my_vip_button(m):
    status_command(m)

@bot.message_handler(func=lambda m: m.text == "⏰ Мой статус")
def status_button(m):
    status_command(m)

@bot.message_handler(func=lambda m: m.text == "🆕 Создать пароль" and str(m.from_user.id) == str(ADMIN_ID))
def cp(m):
    p = gen_parola()
    parole_active.append(p)
    save_data()
    bot.send_message(ADMIN_ID, f"🆕 Пароль: `{p}`", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📋 Список паролей" and str(m.from_user.id) == str(ADMIN_ID))
def lp(m):
    if parole_active:
        bot.send_message(ADMIN_ID, "📋 Пароли:\n" + "\n".join(parole_active))
    else:
        bot.send_message(ADMIN_ID, "❌ Нет паролей")

@bot.message_handler(func=lambda m: m.text == "📊 Статистика" and str(m.from_user.id) == str(ADMIN_ID))
def st(m):
    stats_command(m)

@bot.message_handler(func=lambda m: m.text == "👥 Пользователи" and str(m.from_user.id) == str(ADMIN_ID))
def ul(m):
    list_users_admin(m)

@bot.message_handler(func=lambda m: m.text == "🌐 Открыть сайт" and str(m.from_user.id) == str(ADMIN_ID))
def osite(m):
    bot.send_message(ADMIN_ID, "🌐 Админ сайт доступен по ссылке от Render/Railway")

@bot.message_handler(func=lambda m: m.text == "🗑 Сброс паролей" and str(m.from_user.id) == str(ADMIN_ID))
def rp(m):
    parole_active.clear()
    save_data()
    bot.send
