import os
from flask import Flask, render_template_string, request, redirect, url_for
import psycopg2

app = Flask(__name__)

# 🛑 REPLACE THIS with your Supabase URL later! 🛑
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:YOUR_PASSWORD@db.xxxx.supabase.co:5432/postgres")

def get_db():
    return psycopg2.connect(DB_URL, sslmode='require')

def init_db():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS farmers (
            id SERIAL PRIMARY KEY, name TEXT UNIQUE, phone TEXT,
            outstanding REAL DEFAULT 0, score INTEGER DEFAULT 100,
            status TEXT DEFAULT 'SAFE', promised_date TEXT DEFAULT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY, farmer_id INTEGER, action TEXT,
            points INTEGER, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"DB Error: {e}")

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Shetkari CRM Mobile</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #0a0a0c; color: white; margin: 0; padding: 20px; }
        .card { background-color: #1c1c1e; padding: 20px; border-radius: 15px; margin-bottom: 15px; border: 1px solid #333; }
        h1, h2 { margin-top: 0; }
        .btn { background-color: #0a84ff; color: white; padding: 12px 20px; border: none; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block; margin-top: 10px;}
        .danger { background-color: #ff453a; }
        .success { background-color: #32d74b; color: black; }
        input, select { width: 100%; padding: 12px; margin: 8px 0; background-color: #2c2c2e; border: 1px solid #444; border-radius: 8px; color: white; box-sizing: border-box; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #333; }
        .red { color: #ff453a; }
        .green { color: #32d74b; }
    </style>
</head>
<body>
    <h1>🚜 Shetkari CRM</h1>
    {% if view == 'dashboard' %}
        <div class="card">
            <h2>Total Debt: ₹{{ total_debt }}</h2>
            <p>Total Customers: {{ total_cust }}</p>
        </div>
        <div class="card">
            <h2>Customers</h2>
            <table>
                <tr><th>Name</th><th>Debt</th><th>Action</th></tr>
                {% for f in farmers %}
                <tr>
                    <td>{{ f[1] }}</td>
                    <td class="{% if f[3] > 0 %}red{% else %}green{% endif %}">₹{{ f[3] }}</td>
                    <td><a href="/customer/{{ f[0] }}" class="btn" style="padding: 5px 10px; font-size: 12px;">View</a></td>
                </tr>
                {% endfor %}
            </table>
        </div>
    {% elif view == 'customer' %}
        <div class="card">
            <h2>{{ farmer[1] }}</h2>
            <p>Phone: {{ farmer[2] }}</p>
            <p>Debt: <span class="red">₹{{ farmer[3] }}</span></p>
            <p>Score: {{ farmer[4] }} / 100</p>
        </div>
        <div class="card">
            <h3>Receive Payment</h3>
            <form method="POST" action="/pay/{{ farmer[0] }}">
                <input type="number" name="amount" placeholder="Amount (₹)" required>
                <input type="text" name="notes" placeholder="Notes (e.g. Cash)">
                <button type="submit" class="btn success">Receive</button>
            </form>
        </div>
        <div class="card">
            <h3>Add Bill</h3>
            <form method="POST" action="/bill/{{ farmer[0] }}">
                <input type="number" name="amount" placeholder="Bill Amount (₹)" required>
                <input type="text" name="item" placeholder="Item (e.g. Seeds)">
                <button type="submit" class="btn" style="background-color: #ff9f0a;">Add Bill</button>
            </form>
        </div>
        <a href="/" class="btn">Back to Dashboard</a>
    {% endif %}
</body>
</html>
"""

@app.route('/')
def dashboard():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT SUM(outstanding) FROM farmers")
    total_debt = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(id) FROM farmers")
    total_cust = c.fetchone()[0] or 0
    c.execute("SELECT id, name, phone, outstanding, score, status FROM farmers ORDER BY name ASC")
    farmers = c.fetchall()
    conn.close()
    return render_template_string(HTML, view='dashboard', farmers=farmers, total_debt=f"{total_debt:,.2f}", total_cust=total_cust)

@app.route('/customer/<int:f_id>')
def customer(f_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, phone, outstanding, score, status, promised_date FROM farmers WHERE id=%s", (f_id,))
    farmer = c.fetchone()
    conn.close()
    return render_template_string(HTML, view='customer', farmer=farmer)

@app.route('/pay/<int:f_id>', methods=['POST'])
def pay(f_id):
    amount = float(request.form['amount'])
    notes = request.form.get('notes', '')
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE farmers SET outstanding = GREATEST(0, outstanding - %s) WHERE id=%s", (amount, f_id))
    c.execute("INSERT INTO logs (farmer_id, action, points) VALUES (%s, %s, 10)", (f_id, f"Paid ₹{amount:,.2f} | Note: {notes}"))
    conn.commit()
    conn.close()
    return redirect(url_for('customer', f_id=f_id))

@app.route('/bill/<int:f_id>', methods=['POST'])
def bill(f_id):
    amount = float(request.form['amount'])
    item = request.form.get('item', 'Purchase')
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE farmers SET outstanding = outstanding + %s WHERE id=%s", (amount, f_id))
    c.execute("INSERT INTO logs (farmer_id, action, points) VALUES (%s, %s, 0)", (f_id, f"🛒 Bill: {item} (₹{amount:,.2f})"))
    conn.commit()
    conn.close()
    return redirect(url_for('customer', f_id=f_id))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
