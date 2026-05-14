import telebot
from datetime import datetime, timedelta
import random
import re
import json
import os
import time
import threading
from flask import Flask, render_template_string, request

# ========== КОНФИГ (ЭТО ТЫ МЕНЯЕШЬ) ==========
TOKEN = "8307596159:AAES-a6TjEaAaP_j6LPogq2Eb9vsoBqtL4o"
ADMIN_ID = 7072265211

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

def get_time():
    return datetime.utcnow() + timedelta(hours=3)

PRET = 6
VALABILITATE_ORE = 1
COOLDOWN_ORE = 1

bilete_active = {}
user_access = {}
user_cooldown = {}
parole_active = []
user_stats = {}

DATA_FILE = "bot_data.json"

def load_data():
    global bilete_active, user_access, user_cooldown, parole_active, user_stats
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            bilete_active = data.get('tickets', {})
            user_access = data.get('access', {})
            user_cooldown = data.get('cooldown', {})
            parole_active = data.get('passwords', [])
            user_stats = data.get('stats', {})

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'tickets': bilete_active,
            'access': user_access,
            'cooldown': user_cooldown,
            'passwords': parole_active,
            'stats': user_stats
        }, f)

def gen_parola():
    return str(random.randint(100000, 999999))

def check_cooldown(user_id):
    if str(user_id) == str(ADMIN_ID):
        return True, 0
    last = user_cooldown.get(str(user_id))
    if last:
        last_time = datetime.fromisoformat(last)
        now = get_time()
        passed = now - last_time
        if passed < timedelta(hours=COOLDOWN_ORE):
            remaining = timedelta(hours=COOLDOWN_ORE) - passed
            return False, int(remaining.total_seconds() // 60)
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

# HTML (я ничего не менял, твой же)
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
            <div class="card"><div class="num">{{ passwords_count }}</div><div class="label">Активных паролей</div></div>
        </div>
        
        <div class="tabs">
            <div class="tab active" onclick="openTab('users')">👥 Пользователи</div>
            <div class="tab" onclick="openTab('tickets')">🎫 Билеты</div>
            <div class="tab" onclick="openTab('passwords')">🔑 Пароли</div>
        </div>
        
        <div id="users" class="tab-content active">
            <h3>Список пользователей</h3>
            <table>
                <tr><th>ID</th><th>Имя</th><th>Билетов</th><th>Статус</th><th>Кулдаун</th></tr>
                {% for u in users %}
                <tr>
                    <td>{{ u.id }}</td>
                    <td>{{ u.name }}</td>
                    <td>{{ u.tickets }}</td>
                    <td>{% if u.access %}✅ Активен{% else %}❌ Блок{% endif %}</td>
                    <td>{% if u.cooldown > 0 %}{{ u.cooldown }} мин{% else %}✅ Готов{% endif %}</td>
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
            Transport Moldova — Система электронных билетов
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
            if cd:
                last = datetime.fromisoformat(cd)
                passed = (get_time() - last).total_seconds() / 60
                remaining = max(0, int(COOLDOWN_ORE * 60 - passed))
            users.append({
                'id': uid,
                'name': stats.get('name', 'Unknown'),
                'tickets': stats.get('tickets', 0),
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
        passwords_count=len(parole_active),
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
    # ЭТО ИСПРАВЛЕНИЕ #1: порт для Render/Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ========== БОТ (НИЧЕГО НЕ МЕНЯЛ) ==========
def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("🆕 Создать пароль", "📋 Список паролей")
    mk.row("📊 Статистика", "👥 Пользователи")
    mk.row("🌐 Открыть сайт", "🗑 Сброс паролей")
    return mk

def user_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("🎫 Купить билет", "⏰ Мой статус")
    return mk

@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    if str(uid) == str(ADMIN_ID):
        bot.send_message(uid, "🔐 Админ панель", reply_markup=admin_menu())
        return
    if user_access.get(str(uid), False):
        bot.send_message(uid, f"✅ Привет, {name}!\nНапиши номер автобуса (2000-2099)", reply_markup=user_menu())
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
        bot.send_message(uid, f"✅ Доступ открыт!\nПиши номер автобуса (2000-2099)", reply_markup=user_menu())
    else:
        bot.send_message(uid, "❌ Неверный код!")
        bot.register_next_step_handler(m, check_code)

@bot.message_handler(commands=['admin'])
def admin(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        bot.send_message(ADMIN_ID, "Админ панель", reply_markup=admin_menu())
    else:
        bot.send_message(m.chat.id, "Нет доступа")

@bot.message_handler(commands=['site'])
def site(m):
    if str(m.from_user.id) == str(ADMIN_ID):
        # ИСПРАВЛЕНИЕ #2: убрал localhost, теперь показывает реальный URL
        bot.send_message(ADMIN_ID, "🌐 Админ сайт доступен по ссылке от Render/Railway")

@bot.message_handler(func=lambda m: m.text == "🆕 Создать пароль" and str(m.from_user.id) == str(ADMIN_ID))
def cp(m):
    p = gen_parola()
    parole_active.append(p)
    save_data()
    bot.send_message(ADMIN_ID, f"🆕 Пароль: `{p}`", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📋 Список паролей" and str(m.from_user.id) == str(ADMIN_ID))
def lp(m):
    if parole_active:
        bot.send_message(ADMIN_ID, "Пароли:\n" + "\n".join(parole_active))
    else:
        bot.send_message(ADMIN_ID, "Нет паролей")

@bot.message_handler(func=lambda m: m.text == "📊 Статистика" and str(m.from_user.id) == str(ADMIN_ID))
def st(m):
    bot.send_message(ADMIN_ID, f"📊 Статистика\nБилетов: {len(bilete_active)}\nПользователей: {len([u for u in user_access if user_access[u]])}\nВыручка: {len(bilete_active) * PRET} MDL")

@bot.message_handler(func=lambda m: m.text == "👥 Пользователи" and str(m.from_user.id) == str(ADMIN_ID))
def ul(m):
    if not user_access:
        bot.send_message(ADMIN_ID, "Нет пользователей")
        return
    text = "👥 Пользователи:\n"
    for uid, access in user_access.items():
        if access:
            name = user_stats.get(uid, {}).get('name', 'Unknown')
            tickets = user_stats.get(uid, {}).get('tickets', 0)
            text += f"• {name} - {tickets} билетов\n"
    bot.send_message(ADMIN_ID, text)

@bot.message_handler(func=lambda m: m.text == "🌐 Открыть сайт" and str(m.from_user.id) == str(ADMIN_ID))
def osite(m):
    # ИСПРАВЛЕНИЕ #3: убрал localhost
    bot.send_message(ADMIN_ID, "🌐 Админ сайт доступен по ссылке от Render/Railway")

@bot.message_handler(func=lambda m: m.text == "🗑 Сброс паролей" and str(m.from_user.id) == str(ADMIN_ID))
def rp(m):
    parole_active.clear()
    save_data()
    bot.send_message(ADMIN_ID, "✅ Пароли сброшены")

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
        save_data()
        ticket = f"{cod}\n{now.strftime('%I:%M %p').lstrip('0')}\n\nCererea dumneavoastră procesare.\n\nBiletul electronic nr. {nr}\n{now.strftime('%d.%m.%Y')}\nValabil {VALABILITATE_ORE} ora (de la {now.strftime('%H:%M')} Pret {PRET} MDL)\n\nNumarul de bord: {cod}"
        bot.send_message(chat_id, ticket)
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == "🎫 Купить билет")
def buy(m):
    bot.send_message(m.chat.id, "Введи номер автобуса (2000-2099):", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, process)

def process(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    text = m.text.strip()
    if not re.match(r'^\d{4}$', text):
        bot.send_message(uid, "❌ Нужно 4 цифры!", reply_markup=user_menu())
        return
    cod = int(text)
    if cod < 2000 or cod > 2099:
        bot.send_message(uid, f"❌ {cod} не в диапазоне 2000-2099", reply_markup=user_menu())
        return
    can, mins = check_cooldown(uid)
    if not can and str(uid) != str(ADMIN_ID):
        bot.send_message(uid, f"⏰ Жди {mins} мин!", reply_markup=user_menu())
        return
    threading.Thread(target=issue_ticket, args=(uid, uid, cod, name)).start()

@bot.message_handler(func=lambda m: m.text == "⏰ Мой статус")
def status(m):
    uid = m.from_user.id
    can, mins = check_cooldown(uid)
    if can:
        bot.send_message(uid, "✅ Можешь купить билет!", reply_markup=user_menu())
    else:
        bot.send_message(uid, f"⏰ Следующий билет через {mins} мин", reply_markup=user_menu())

@bot.message_handler(func=lambda m: True)
def handle(m):
    uid = m.from_user.id
    name = m.from_user.first_name
    text = m.text.strip()
    if str(uid) == str(ADMIN_ID) or user_access.get(str(uid), False):
        if re.match(r'^\d{4}$', text):
            cod = int(text)
            if 2000 <= cod <= 2099:
                can, mins = check_cooldown(uid)
                if not can and str(uid) != str(ADMIN_ID):
                    bot.send_message(uid, f"⏰ Жди {mins} мин!")
                    return
                threading.Thread(target=issue_ticket, args=(uid, uid, cod, name)).start()
                return
        bot.send_message(uid, "🚌 Введи номер автобуса (2000-2099)\nПример: 2044", reply_markup=user_menu())

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    load_data()
    threading.Thread(target=start_web, daemon=True).start()
    print("=" * 50)
    print("✅ БОТ ЗАПУЩЕН")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print("=" * 50)
    bot.infinity_polling()