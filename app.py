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
    ''')
    # 建立預設管理員帳號
    cursor = conn.execute('SELECT COUNT(*) FROM admin_users')
    if cursor.fetchone()[0] == 0:
        conn.execute('INSERT INTO admin_users (username, password) VALUES (?, ?)',
                     ('admin', generate_password_hash('admin123', method='pbkdf2:sha256')))
        conn.commit()
    conn.close()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
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
    session.clear()
    return redirect(url_for('index'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()
    stones = conn.execute('SELECT * FROM stones ORDER BY created_at DESC').fetchall()
    total = len(stones)
    conn.close()
    return render_template('admin.html', stones=stones, total=total)


@app.route('/admin/add', methods=['GET', 'POST'])
@admin_required
def add_stone():
    if request.method == 'POST':
        stone_type = request.form.get('stone_type', '').strip()
        if not stone_type:
            flash('石材種類為必填欄位', 'error')
            return render_template('stone_form.html', stone=None, title='新增石材')

        width = request.form.get('width') or None
        height = request.form.get('height') or None
        thickness = request.form.get('thickness') or None
        quantity = request.form.get('quantity') or None
        unit = request.form.get('unit', '片')
        price = request.form.get('price') or None
        vendor = request.form.get('vendor', '').strip()
        description = request.form.get('description', '').strip()

        photo = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"{secrets.token_hex(8)}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo = filename

        conn = get_db()
        conn.execute('''
            INSERT INTO stones (stone_type, photo, width, height, thickness, quantity, unit, price, vendor, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (stone_type, photo, width, height, thickness, quantity, unit, price, vendor, description))
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
        stone_type = request.form.get('stone_type', '').strip()
        width = request.form.get('width') or None
        height = request.form.get('height') or None
        thickness = request.form.get('thickness') or None
        quantity = request.form.get('quantity') or None
        unit = request.form.get('unit', '片')
        price = request.form.get('price') or None
        vendor = request.form.get('vendor', '').strip()
        description = request.form.get('description', '').strip()

        photo = stone['photo']
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                if photo:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], photo)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                filename = secure_filename(file.filename)
                filename = f"{secrets.token_hex(8)}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo = filename

        conn.execute('''
            UPDATE stones
            SET stone_type=?, photo=?, width=?, height=?, thickness=?,
                quantity=?, unit=?, price=?, vendor=?, description=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (stone_type, photo, width, height, thickness, quantity, unit, price, vendor, description, id))
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
        if stone['photo']:
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], stone['photo'])
            if os.path.exists(photo_path):
                os.remove(photo_path)
        conn.execute('DELETE FROM stones WHERE id = ?', (id,))
        conn.commit()
        flash('石材已成功刪除', 'success')
    else:
        flash('找不到該石材', 'error')

    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/change-password', methods=['GET', 'POST'])
@admin_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
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
                         (generate_password_hash(new_pw, method='pbkdf2:sha256'), session['admin_name']))
            conn.commit()
            flash('密碼已成功更新！', 'success')
        conn.close()

    return render_template('change_password.html')


if __name__ == '__main__':
    init_db()
    print("\n" + "="*50)
    print("  ReStone 循環石材服務平台 已啟動！")
    print("="*50)
    print("  前台瀏覽：http://127.0.0.1:5000")
    print("  管理後台：http://127.0.0.1:5000/admin/login")
    print("  預設帳號：admin")
    print("  預設密碼：admin123")
    print("="*50 + "\n")
    app.run(debug=False, port=5000)
