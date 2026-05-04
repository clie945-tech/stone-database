from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import secrets
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'stone-circular-db-secret-2024'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
DB_PATH = 'stone_database.db'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS stones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stone_type TEXT NOT NULL,
            photo TEXT,
            photo2 TEXT,
            photo3 TEXT,
            width REAL,
            height REAL,
            thickness REAL,
            quantity INTEGER,
            unit TEXT DEFAULT '片',
            price REAL,
            vendor TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stone_id INTEGER,
            stone_name TEXT,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            customer_phone TEXT,
            quantity INTEGER,
            message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # 舊資料庫遷移：補上 photo2, photo3 欄位
    for col in ['photo2', 'photo3']:
        try:
            conn.execute(f'ALTER TABLE stones ADD COLUMN {col} TEXT')
            conn.commit()
        except Exception:
            pass

    # 建立預設管理員帳號
    cursor = conn.execute('SELECT COUNT(*) FROM admin_users')
    if cursor.fetchone()[0] == 0:
        conn.execute('INSERT INTO admin_users (username, password) VALUES (?, ?)',
                     ('admin', generate_password_hash('admin123', method='pbkdf2:sha256')))
        conn.commit()
    conn.close()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_photo(file_field):
    """儲存上傳照片，回傳檔名或 None"""
    if file_field and file_field.filename and allowed_file(file_field.filename):
        filename = secure_filename(file_field.filename)
        filename = f"{secrets.token_hex(8)}_{filename}"
        file_field.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None


def delete_photo(filename):
    """刪除照片檔案"""
    if filename:
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(path):
            os.remove(path)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def customer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('customer_id'):
            flash('請先登入會員帳號', 'error')
            return redirect(url_for('customer_login'))
        return f(*args, **kwargs)
    return decorated


# ─── 公開前台 ───────────────────────────────────────────────

@app.route('/')
def index():
    conn = get_db()
    search = request.args.get('search', '')
    stone_type = request.args.get('type', '')

    query = 'SELECT * FROM stones WHERE 1=1'
    params = []

    if search:
        query += ' AND (stone_type LIKE ? OR vendor LIKE ? OR description LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    if stone_type:
        query += ' AND stone_type = ?'
        params.append(stone_type)

    query += ' ORDER BY created_at DESC'
    stones = conn.execute(query, params).fetchall()
    types = conn.execute('SELECT DISTINCT stone_type FROM stones ORDER BY stone_type').fetchall()
    total = conn.execute('SELECT COUNT(*) FROM stones').fetchone()[0]
    conn.close()

    return render_template('index.html', stones=stones, types=types,
                           search=search, selected_type=stone_type, total=total)


@app.route('/stone/<int:id>')
def stone_detail(id):
    conn = get_db()
    stone = conn.execute('SELECT * FROM stones WHERE id = ?', (id,)).fetchone()
    conn.close()
    if not stone:
        return redirect(url_for('index'))
    return render_template('stone_detail.html', stone=stone)


@app.route('/stone/<int:id>/inquiry', methods=['POST'])
def submit_inquiry(id):
    conn = get_db()
    stone = conn.execute('SELECT * FROM stones WHERE id = ?', (id,)).fetchone()
    if not stone:
        conn.close()
        return redirect(url_for('index'))

    name    = request.form.get('name', '').strip()
    email   = request.form.get('email', '').strip()
    phone   = request.form.get('phone', '').strip()
    qty     = request.form.get('quantity') or None
    message = request.form.get('message', '').strip()

    if not name or not email:
        flash('姓名與 Email 為必填欄位', 'error')
        conn.close()
        return redirect(url_for('stone_detail', id=id))

    conn.execute('''
        INSERT INTO inquiries (stone_id, stone_name, customer_name, customer_email,
                               customer_phone, quantity, message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (id, stone['stone_type'], name, email, phone, qty, message))
    conn.commit()
    conn.close()

    flash('詢問已送出！廠商將盡快與您聯繫。', 'success')
    return redirect(url_for('stone_detail', id=id))


# ─── 會員系統 ────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('customer_id'):
        return redirect(url_for('my_account'))
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip()
        phone    = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if not name or not email or not password:
            flash('姓名、Email 及密碼為必填', 'error')
        elif password != confirm:
            flash('兩次密碼不一致', 'error')
        elif len(password) < 6:
            flash('密碼至少需要 6 個字元', 'error')
        else:
            conn = get_db()
            existing = conn.execute('SELECT id FROM customers WHERE email = ?', (email,)).fetchone()
            if existing:
                flash('此 Email 已被註冊', 'error')
                conn.close()
            else:
                conn.execute('''INSERT INTO customers (name, email, phone, password)
                                VALUES (?, ?, ?, ?)''',
                             (name, email, phone,
                              generate_password_hash(password, method='pbkdf2:sha256')))
                conn.commit()
                customer = conn.execute('SELECT * FROM customers WHERE email = ?', (email,)).fetchone()
                conn.close()
                session['customer_id']    = customer['id']
                session['customer_name']  = customer['name']
                session['customer_email'] = customer['email']
                flash('註冊成功！歡迎加入 ReStone！', 'success')
                return redirect(url_for('my_account'))

    return render_template('register.html')


@app.route('/customer/login', methods=['GET', 'POST'])
def customer_login():
    if session.get('customer_id'):
        return redirect(url_for('my_account'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        customer = conn.execute('SELECT * FROM customers WHERE email = ?', (email,)).fetchone()
        conn.close()
        if customer and check_password_hash(customer['password'], password):
            session['customer_id']    = customer['id']
            session['customer_name']  = customer['name']
            session['customer_email'] = customer['email']
            flash(f'歡迎回來，{customer["name"]}！', 'success')
            return redirect(url_for('index'))
        else:
            flash('Email 或密碼錯誤', 'error')
    return render_template('customer_login.html')


@app.route('/customer/logout')
def customer_logout():
    session.pop('customer_id', None)
    session.pop('customer_name', None)
    session.pop('customer_email', None)
    return redirect(url_for('index'))


@app.route('/my-account')
@customer_required
def my_account():
    conn = get_db()
    inquiries = conn.execute('''
        SELECT i.*, s.stone_type FROM inquiries i
        LEFT JOIN stones s ON i.stone_id = s.id
        WHERE i.customer_email = ?
        ORDER BY i.created_at DESC
    ''', (session['customer_email'],)).fetchall()
    conn.close()
    return render_template('customer_dashboard.html', inquiries=inquiries)


# ─── 管理員後台 ─────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if session.get('admin'):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        conn = get_db()
        admin = conn.execute('SELECT * FROM admin_users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin['password'], password):
            session['admin'] = True
            session['admin_name'] = admin['username']
            return redirect(url_for('admin_dashboard'))
        else:
            flash('帳號或密碼錯誤，請重試', 'error')
    return render_template('login.html')


@app.route('/admin/logout')
def logout():
    session.pop('admin', None)
    session.pop('admin_name', None)
    return redirect(url_for('index'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()
    stones = conn.execute('SELECT * FROM stones ORDER BY created_at DESC').fetchall()
    total  = len(stones)
    new_inquiries = conn.execute(
        "SELECT COUNT(*) FROM inquiries WHERE status = 'pending'").fetchone()[0]
    conn.close()
    return render_template('admin.html', stones=stones, total=total,
                           new_inquiries=new_inquiries)


@app.route('/admin/inquiries')
@admin_required
def admin_inquiries():
    conn = get_db()
    inquiries = conn.execute('''
        SELECT i.*, s.stone_type FROM inquiries i
        LEFT JOIN stones s ON i.stone_id = s.id
        ORDER BY i.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin_inquiries.html', inquiries=inquiries)


@app.route('/admin/inquiry/<int:id>/status', methods=['POST'])
@admin_required
def update_inquiry_status(id):
    status = request.form.get('status', 'pending')
    conn = get_db()
    conn.execute('UPDATE inquiries SET status = ? WHERE id = ?', (status, id))
    conn.commit()
    conn.close()
    flash('詢問狀態已更新', 'success')
    return redirect(url_for('admin_inquiries'))


@app.route('/admin/add', methods=['GET', 'POST'])
@admin_required
def add_stone():
    if request.method == 'POST':
        stone_type = request.form.get('stone_type', '').strip()
        if not stone_type:
            flash('石材種類為必填欄位', 'error')
            return render_template('stone_form.html', stone=None, title='新增石材')

        width       = request.form.get('width') or None
        height      = request.form.get('height') or None
        thickness   = request.form.get('thickness') or None
        quantity    = request.form.get('quantity') or None
        unit        = request.form.get('unit', '片')
        price       = request.form.get('price') or None
        vendor      = request.form.get('vendor', '').strip()
        description = request.form.get('description', '').strip()

        photo  = save_photo(request.files.get('photo'))
        photo2 = save_photo(request.files.get('photo2'))
        photo3 = save_photo(request.files.get('photo3'))

        conn = get_db()
        conn.execute('''
            INSERT INTO stones (stone_type, photo, photo2, photo3,
                                width, height, thickness, quantity, unit, price, vendor, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (stone_type, photo, photo2, photo3,
              width, height, thickness, quantity, unit, price, vendor, description))
        conn.commit()
        conn.close()

        flash(f'「{stone_type}」已成功新增！', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('stone_form.html', stone=None, title='新增石材')


@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_stone(id):
    conn = get_db()
    stone = conn.execute('SELECT * FROM stones WHERE id = ?', (id,)).fetchone()

    if not stone:
        conn.close()
        flash('找不到該石材', 'error')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        stone_type  = request.form.get('stone_type', '').strip()
        width       = request.form.get('width') or None
        height      = request.form.get('height') or None
        thickness   = request.form.get('thickness') or None
        quantity    = request.form.get('quantity') or None
        unit        = request.form.get('unit', '片')
        price       = request.form.get('price') or None
        vendor      = request.form.get('vendor', '').strip()
        description = request.form.get('description', '').strip()

        # 處理三張照片（有新上傳才替換）
        photos = []
        for field, old_key in [('photo', 'photo'), ('photo2', 'photo2'), ('photo3', 'photo3')]:
            new_file = request.files.get(field)
            new_photo = save_photo(new_file)
            if new_photo:
                delete_photo(stone[old_key])
                photos.append(new_photo)
            else:
                photos.append(stone[old_key])

        conn.execute('''
            UPDATE stones
            SET stone_type=?, photo=?, photo2=?, photo3=?,
                width=?, height=?, thickness=?,
                quantity=?, unit=?, price=?, vendor=?, description=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (stone_type, photos[0], photos[1], photos[2],
              width, height, thickness, quantity, unit, price, vendor, description, id))
        conn.commit()
        conn.close()

        flash(f'「{stone_type}」資料已更新！', 'success')
        return redirect(url_for('admin_dashboard'))

    conn.close()
    return render_template('stone_form.html', stone=stone, title='編輯石材')


@app.route('/admin/delete/<int:id>', methods=['POST'])
@admin_required
def delete_stone(id):
    conn = get_db()
    stone = conn.execute('SELECT * FROM stones WHERE id = ?', (id,)).fetchone()

    if stone:
        for field in ['photo', 'photo2', 'photo3']:
            delete_photo(stone[field])
        conn.execute('DELETE FROM stones WHERE id = ?', (id,))
        conn.commit()
        flash('石材已成功刪除', 'success')
    else:
        flash('找不到該石材', 'error')

    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/customers')
@admin_required
def admin_customers():
    conn = get_db()
    customers = conn.execute('SELECT * FROM customers ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin_customers.html', customers=customers)


@app.route('/admin/change-password', methods=['GET', 'POST'])
@admin_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new_pw  = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        conn = get_db()
        admin = conn.execute('SELECT * FROM admin_users WHERE username = ?',
                             (session['admin_name'],)).fetchone()

        if not check_password_hash(admin['password'], current):
            flash('目前密碼不正確', 'error')
        elif new_pw != confirm:
            flash('新密碼與確認密碼不符', 'error')
        elif len(new_pw) < 6:
            flash('新密碼至少需要 6 個字元', 'error')
        else:
            conn.execute('UPDATE admin_users SET password = ? WHERE username = ?',
                         (generate_password_hash(new_pw, method='pbkdf2:sha256'),
                          session['admin_name']))
            conn.commit()
            flash('密碼已成功更新！', 'success')
        conn.close()

    return render_template('change_password.html')


# 不論是本機或雲端，啟動時都初始化資料庫
init_db()

if __name__ == '__main__':
    print("\n" + "="*50)
    print("  ReStone 循環石材服務平台 已啟動！")
    print("="*50)
    print("  前台瀏覽：http://127.0.0.1:5000")
    print("  管理後台：http://127.0.0.1:5000/admin/login")
    print("  預設帳號：admin")
    print("  預設密碼：admin123")
    print("="*50 + "\n")
    app.run(debug=False, port=5000)
