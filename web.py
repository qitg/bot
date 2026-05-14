from flask import Flask, render_template_string, jsonify
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)
DATA_FILE = "bot_data.json"

def get_time():
    return datetime.utcnow() + timedelta(hours=3)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

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
        
        <h3>Последние билеты</h3>
        <table>
            <tr><th>№ билета</th><th>Автобус</th><th>Пользователь</th><th>Дата</th><th>Время</th></tr>
            {% for t in tickets %}
            <tr>
                <td>{{ t.num }}</td>
                <td>{{ t.bus }}</td>
                <td>{{ t.user }}</td>
                <td>{{ t.date }}</td>
                <td>{{ t.time }}</td>
            </tr>
            {% endfor %}
        </table>
        
        <div class="footer">
            🎫 Обычные: 3 билета/день, кулдаун 45 мин | 💎 VIP: 10 билетов/день
        </div>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    data = load_data()
    bilete_active = data.get('tickets', {})
    user_access = data.get('access', {})
    user_vip = data.get('vip', {})
    
    tickets = []
    for nr, b in list(bilete_active.items())[-30:]:
        tickets.append({
            'num': nr,
            'bus': b.get('bus'),
            'user': b.get('user_name', 'Unknown'),
            'date': b.get('date', ''),
            'time': b.get('time', '')
        })
    
    vip_count = 0
    for uid, expiry_str in user_vip.items():
        expiry = datetime.fromisoformat(expiry_str)
        if expiry > get_time():
            vip_count += 1
    
    return render_template_string(HTML,
        now=get_time().strftime('%d.%m.%Y %H:%M:%S'),
        users_count=len([u for u in user_access if user_access[u]]),
        tickets_count=len(bilete_active),
        revenue=len(bilete_active) * 6,
        vip_count=vip_count,
        tickets=tickets
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
