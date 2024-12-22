import sqlite3
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from datetime import datetime
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key'


# Database Initialization
def init_db():
    conn = sqlite3.connect('credit_site.db')
    c = conn.cursor()

    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS administrators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE,
                    password TEXT
                 )''')

    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE,
                    name TEXT,
                    start_date DATE,
                    end_date DATE,
                    approved TEXT
                 )''')

    c.execute('''CREATE TABLE IF NOT EXISTS calculator (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client TEXT,
                    type TEXT,
                    bid REAL,
                    is_available TEXT,
                    summ REAL
                 )''')

    c.execute('''CREATE TABLE IF NOT EXISTS loan_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    amount REAL,
                    period INTEGER,
                    rate REAL,
                    type TEXT,
                    status TEXT DEFAULT 'Pending'
                 )''')


    # Insert default admin
    c.execute('''INSERT OR IGNORE INTO administrators (email, password) VALUES ('admin@admin.com', 'admin')''')

    conn.commit()
    conn.close()


# Loan Calculation
def calculate_loan(amount, period, rate, loan_type):
    monthly_rate = rate / 100 / 12
    if loan_type == 'annuity':
        annuity = amount * (monthly_rate * (1 + monthly_rate) ** period) / ((1 + monthly_rate) ** period - 1)
        payments = [annuity for _ in range(period)]
    else:  # differentiated
        principal = amount / period
        payments = [(principal + (amount - i * principal) * monthly_rate) for i in range(period)]
    return payments


# User Authentication
def authenticate_user(email, password):
    conn = sqlite3.connect('credit_site.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (email,))
    user = c.fetchone()
    conn.close()
    return user


# User Registration
def register_user(email, password):
    conn = sqlite3.connect('credit_site.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (user_id, name, start_date, end_date, approved) VALUES (?, ?, ?, ?, ?)",
                  (email, email.split('@')[0], datetime.now(), None, 'no'))
        conn.commit()
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()
    return True


# Submit Loan Application
def submit_application(user_id, amount, period, rate, loan_type):
    conn = sqlite3.connect('credit_site.db')
    c = conn.cursor()
    c.execute("INSERT INTO loan_applications (user_id, amount, period, rate, type) VALUES (?, ?, ?, ?, ?)",
              (user_id, amount, period, rate, loan_type))
    conn.commit()
    conn.close()


# Approve or Reject Loan Application
def update_application_status(app_id, status):
    conn = sqlite3.connect('credit_site.db')
    c = conn.cursor()
    c.execute("UPDATE loan_applications SET status = ? WHERE id = ?", (status, app_id))
    conn.commit()
    conn.close()


def get_user_profile(email):
    conn = sqlite3.connect('credit_site.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (email,))
    user_data = c.fetchone()
    c.execute("SELECT * FROM loan_applications WHERE user_id = ?", (email,))
    loan_data = c.fetchall()
    conn.close()
    return user_data, loan_data


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if register_user(email, password):
            return redirect(url_for('login'))
        else:
            return "User already exists!"
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = authenticate_user(email, password)
        if user:
            session['user'] = email
            return redirect(url_for('calculator'))
        else:
            return "Invalid credentials!"
    return render_template('login.html')


@app.route('/profile')
def profile():
    if 'user' in session:
        user_data, loan_data = get_user_profile(session['user'])

        # Генерация графика по последней заявке
        if loan_data:
            last_loan = loan_data[-1]
            payments = calculate_loan(last_loan[2], last_loan[3], last_loan[4], last_loan[5])

            plt.figure(figsize=(10, 5))
            plt.plot(payments, marker='o')
            plt.title(f'Loan Payment Schedule for Application #{last_loan[0]}')
            plt.xlabel('Month')
            plt.ylabel('Payment Amount')
            plt.grid(True)

            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            buf.close()
        else:
            img_base64 = None

        return render_template('profile.html', user=user_data, loans=loan_data, chart=img_base64)
    return redirect(url_for('login'))


@app.route('/calculator', methods=['GET', 'POST'])
def calculator():
    if 'user' in session:
        if request.method == 'POST':
            amount = float(request.form['amount'])
            period = int(request.form['period'])
            rate = float(request.form['rate'])
            loan_type = request.form['type']

            payments = calculate_loan(amount, period, rate, loan_type)
            submit_application(session['user'], amount, period, rate, loan_type)
            plt.figure(figsize=(10, 5))
            plt.plot(payments, marker='o')
            plt.title('Loan Payment Schedule')
            plt.xlabel('Month')
            plt.ylabel('Payment Amount')
            plt.grid(True)

            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            buf.close()

            return render_template('calculator.html', result=f"Application submitted for {loan_type} loan of {amount}",
                                   chart=img_base64)
        return render_template('calculator.html', result=None)
    return redirect(url_for('login'))


@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('credit_site.db')
        c = conn.cursor()
        c.execute("SELECT * FROM administrators WHERE email = ? AND password = ?", (email, password))
        admin = c.fetchone()
        conn.close()
        if admin:
            session['admin'] = email
            return redirect(url_for('admin_dashboard'))
        else:
            return "Invalid admin credentials!"
    return render_template('admin_login.html')


@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin' in session:
        conn = sqlite3.connect('credit_site.db')
        c = conn.cursor()
        c.execute("SELECT * FROM loan_applications")
        applications = c.fetchall()
        conn.close()
        if request.method == 'POST':
            app_id = request.form['app_id']
            status = request.form['status']
            update_application_status(app_id, status)
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_dashboard.html', applications=applications)
    return redirect(url_for('admin_login'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
