from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_mail import Mail, Message
import sqlite3
import os
import io
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

# ── Email 設定（從環境變數讀取，未設定則停用）──
app.config['MAIL_SERVER']         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT']           = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS']        = True
app.config['MAIL_USERNAME']       = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD']       = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', '')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', os.environ.get('MAIL_USERNAME', ''))
mail = Mail(app)

# ── 顏色標籤定義 ──
COLORS = [
    ('white',  '白色系', '#F8FAFC', '#64748B'),
    ('gray',   '灰色系', '#E2E8F0', '#475569'),
    ('black',  '黑色系', '#1E293B', '#F1F5F9'),
    ('beige',  '米色系', '#FEF3C7', '#92400E'),
    ('brown',  '棕色系', '#78350F', '#FEF3C7'),
    ('green',  '綠色系', '#D1FAE5', '#065F46'),
    ('blue',   '藍色系', '#DBEAFE', '#1E40AF'),
    ('red',    '紅色系', '#FEE2E2', '#991B1B'),
    ('multi',  '多彩',   '#F3E8FF', '#6D28D9'),
]
COLOR_MAP = {c[0]: c for c in COLORS}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── 圖片 AI 分析工具 ──
def classify_rgb(r, g, b):
    """RGB → 9種顏色標籤代碼"""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h_deg = h * 360.0

    # 黑白灰系（依亮度與飽和度）
    if v > 0.82 and s < 0.18:
        return 'white'
    if v < 0.22:
        return 'black'
    if s < 0.13:
        return 'gray'

    # 色相分類
    if h_deg < 20 or h_deg >= 340:
        return 'red'
    if h_deg < 50:
        return 'beige' if (v > 0.62 and s < 0.45) else 'brown'
    if h_deg < 70:
        return 'beige' if v > 0.65 else 'brown'
    if h_deg < 195:  # 涵蓋翠綠、青綠、蛇紋綠
        return 'green'
    if h_deg < 260:
        return 'blue'
    return 'red'  # 紫紅範圍歸類為紅


def analyze_image(filepath_or_fileobj):
    """分析圖片，回傳 (color_code, perceptual_hash, dominant_rgb_str)"""
    try:
        from PIL import Image
        import imagehash
        if hasattr(filepath_or_fileobj, 'read'):
            filepath_or_fileobj.seek(0)
            img = Image.open(filepath_or_fileobj).convert('RGB')
        else:
            img = Image.open(filepath_or_fileobj).convert('RGB')

        # 主色偵測（量化 5 色取最多）
        thumb = img.copy()
        thumb.thumbnail((150, 150))
        try:
            paletted = thumb.convert('P', palette=Image.Palette.ADAPTIVE, colors=5)
        except AttributeError:
            paletted = thumb.convert('P', palette=Image.ADAPTIVE, colors=5)
        palette = paletted.getpalette() or []
        color_counts = sorted(paletted.getcolors() or [], reverse=True)
        if color_counts and palette:
            idx = color_counts[0][1]
            r = palette[idx * 3]
            g = palette[idx * 3 + 1]
            b = palette[idx * 3 + 2]
            color_code = classify_rgb(r, g, b)
            rgb_str = f'{r},{g},{b}'
        else:
            color_code, rgb_str = '', ''

        # 感知雜湊（用於以圖搜圖）
        phash = str(imagehash.phash(img))
        return (color_code, phash, rgb_str)
    except Exception as e:
        print(f'[圖片分析失敗] {e}')
        return ('', '', '')


def hash_distance(h1, h2):
    """兩個 phash 字串的差異（0-64，越小越相似）"""
    if not h1 or not h2:
        return 64
    try:
        import imagehash
        return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)
    except Exception:
        return 64


def rgb_distance(rgb1_str, rgb2_str):
    """兩個 RGB 字串的歐氏距離（0-441）"""
    try:
        r1, g1, b1 = map(int, rgb1_str.split(','))
        r2, g2, b2 = map(int, rgb2_str.split(','))
        return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5
    except Exception:
        return 441.0


def send_email_safe(subject, recipients, html_body):
    """安全發送 Email，若未設定則略過"""
    if not app.config.get('MAIL_USERNAME'):
        return
    try:
        msg = Message(subject, recipients=recipients, html=html_body)
        mail.send(msg)
    except Exception as e:
        print(f'[Email 發送失敗] {e}')


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

    # 顏色標籤欄位遷移
    try:
        conn.execute("ALTER TABLE stones ADD COLUMN color TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass

    # AI 圖片分析欄位遷移（image_hash 用於以圖搜圖、dominant_rgb 用於色彩比對）
    for col in ['image_hash', 'dominant_rgb']:
        try:
            conn.execute(f"ALTER TABLE stones ADD COLUMN {col} TEXT DEFAULT ''")
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


# ─── 增強型搜尋：同義詞字典 ──────────────────────────────────
SYNONYMS = {
    '大理石': ['marble', '雲石', '大理岩', 'marmo'],
    '花崗岩': ['granite', '花崗石', '麻石', 'granitе'],
    '板岩':   ['slate', '石板', '頁岩'],
    '石英岩': ['quartzite', '石英石', '水晶石'],
    '石灰岩': ['limestone', '石灰石', '珊瑚石'],
    '砂岩':   ['sandstone', '沙岩'],
    '玄武岩': ['basalt', '火山岩', '玄武石'],
    '洞石':   ['travertine', '石灰華'],
    '白色':   ['米白', '象牙白', '珍珠白', '純白', 'white'],
    '灰色':   ['深灰', '淺灰', '銀灰', '鐵灰', 'grey', 'gray'],
    '黑色':   ['深黑', '烏黑', 'black', '黑'],
    '米色':   ['米白', '杏色', '奶油色', 'beige'],
    '棕色':   ['咖啡色', '褐色', '棕褐', 'brown'],
    '綠色':   ['墨綠', '翠綠', 'green', '翠'],
    '地板':   ['地面', '地坪', '鋪地', '地磚'],
    '牆面':   ['牆壁', '立面', '壁面', '外牆', '內牆'],
    '廚房':   ['廚衛', '流理台', '檯面', '廚具'],
    '衛浴':   ['浴室', '廁所', '衛生間', '浴間'],
    '戶外':   ['室外', '外部', '庭院', '廣場'],
}

def expand_query(query):
    """將搜尋字串展開為包含同義詞的列表"""
    q = query.strip().lower()
    terms = {q}
    for key, values in SYNONYMS.items():
        all_terms = [key.lower()] + [v.lower() for v in values]
        if any(t in q or q in t for t in all_terms):
            terms.update(all_terms)
    return list(terms)


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

    base_query = 'SELECT * FROM stones WHERE 1=1'
    params = []

    if search:
        # 展開同義詞進行增強搜尋
        terms = expand_query(search)
        conditions = []
        for term in terms:
            conditions.append(
                '(stone_type LIKE ? OR vendor LIKE ? OR description LIKE ?)'
            )
            params.extend([f'%{term}%', f'%{term}%', f'%{term}%'])
        base_query += ' AND (' + ' OR '.join(conditions) + ')'

    if stone_type:
        base_query += ' AND stone_type = ?'
        params.append(stone_type)

    color = request.args.get('color', '')
    if color:
        base_query += ' AND color = ?'
        params.append(color)

    base_query += ' ORDER BY created_at DESC'
    stones = conn.execute(base_query, params).fetchall()
    types = conn.execute('SELECT DISTINCT stone_type FROM stones ORDER BY stone_type').fetchall()
    total = conn.execute('SELECT COUNT(*) FROM stones').fetchone()[0]
    conn.close()

    return render_template('index.html', stones=stones, types=types,
                           search=search, selected_type=stone_type, total=total,
                           colors=COLORS, color_map=COLOR_MAP, selected_color=color)


@app.route('/stone/<int:id>')
def stone_detail(id):
    conn = get_db()
    stone = conn.execute('SELECT * FROM stones WHERE id = ?', (id,)).fetchone()
    if not stone:
        conn.close()
        return redirect(url_for('index'))

    # 智慧推薦：同類型優先，其次相近價格，排除自己
    price = stone['price'] or 0
    recommendations = conn.execute('''
        SELECT * FROM stones
        WHERE id != ?
        ORDER BY
            CASE WHEN stone_type = ? THEN 0 ELSE 1 END,
            CASE WHEN price IS NOT NULL AND ABS(COALESCE(price,0) - ?) < ? THEN 0 ELSE 1 END,
            created_at DESC
        LIMIT 4
    ''', (id, stone['stone_type'], price, max(price * 0.6, 2000))).fetchall()

    conn.close()
    return render_template('stone_detail.html', stone=stone, recommendations=recommendations,
                           color_map=COLOR_MAP)


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

    stone_name = stone['stone_type']
    conn.execute('''
        INSERT INTO inquiries (stone_id, stone_name, customer_name, customer_email,
                               customer_phone, quantity, message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (id, stone_name, name, email, phone, qty, message))
    conn.commit()
    conn.close()

    # 發送確認 Email 給客戶
    send_email_safe(
        subject='【ReStone】您的詢問已收到',
        recipients=[email],
        html_body=f'''
        <div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:2rem">
          <div style="background:#2563EB;border-radius:12px;padding:1.5rem;text-align:center;margin-bottom:1.5rem">
            <h2 style="color:white;margin:0;font-size:1.3rem">◈ ReStone 循環石材服務平台</h2>
          </div>
          <h3 style="color:#0F172A">感謝您的詢問！</h3>
          <p style="color:#64748B;line-height:1.8">您好 <strong>{name}</strong>，<br>
          我們已收到您針對「<strong>{stone_name}</strong>」的詢問，將盡快與您聯繫。</p>
          <div style="background:#EFF6FF;border-radius:10px;padding:1rem;margin-top:1.2rem;border:1px solid #BFDBFE">
            <p style="margin:0;font-size:0.85rem;color:#1E40AF">詢問數量：{qty or "未填寫"}<br>留言：{message or "（無）"}</p>
          </div>
          <hr style="border:none;border-top:1px solid #E2E8F0;margin:1.5rem 0">
          <p style="color:#94A3B8;font-size:0.78rem;text-align:center">ReStone 循環石材服務平台 · 支持循環經濟</p>
        </div>'''
    )
    # 發送通知 Email 給管理員
    if ADMIN_EMAIL:
        send_email_safe(
            subject=f'【ReStone】新詢問：{stone_name}',
            recipients=[ADMIN_EMAIL],
            html_body=f'''
            <div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:2rem">
              <h2 style="color:#2563EB">新詢問通知</h2>
              <table style="width:100%;border-collapse:collapse;font-size:0.9rem;margin-top:1rem">
                <tr><td style="padding:10px;background:#F8FAFC;color:#64748B;width:90px;border-bottom:1px solid #E2E8F0">石材</td>
                    <td style="padding:10px;font-weight:600;border-bottom:1px solid #E2E8F0">{stone_name}</td></tr>
                <tr><td style="padding:10px;background:#F8FAFC;color:#64748B;border-bottom:1px solid #E2E8F0">客戶姓名</td>
                    <td style="padding:10px;border-bottom:1px solid #E2E8F0">{name}</td></tr>
                <tr><td style="padding:10px;background:#F8FAFC;color:#64748B;border-bottom:1px solid #E2E8F0">Email</td>
                    <td style="padding:10px;border-bottom:1px solid #E2E8F0">{email}</td></tr>
                <tr><td style="padding:10px;background:#F8FAFC;color:#64748B;border-bottom:1px solid #E2E8F0">電話</td>
                    <td style="padding:10px;border-bottom:1px solid #E2E8F0">{phone or "—"}</td></tr>
                <tr><td style="padding:10px;background:#F8FAFC;color:#64748B;border-bottom:1px solid #E2E8F0">詢問數量</td>
                    <td style="padding:10px;border-bottom:1px solid #E2E8F0">{qty or "—"}</td></tr>
                <tr><td style="padding:10px;background:#F8FAFC;color:#64748B">留言</td>
                    <td style="padding:10px">{message or "—"}</td></tr>
              </table>
              <div style="margin-top:1.5rem">
                <a href="/admin/inquiries" style="background:#2563EB;color:white;padding:0.6rem 1.5rem;border-radius:8px;text-decoration:none;font-size:0.88rem;font-weight:600">查看詢問管理</a>
              </div>
            </div>'''
        )

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
        color       = request.form.get('color', '')

        photo  = save_photo(request.files.get('photo'))
        photo2 = save_photo(request.files.get('photo2'))
        photo3 = save_photo(request.files.get('photo3'))

        # 主照片 AI 分析：自動偵測顏色 + 計算雜湊
        image_hash, dominant_rgb = '', ''
        if photo:
            auto_color, image_hash, dominant_rgb = analyze_image(
                os.path.join(app.config['UPLOAD_FOLDER'], photo))
            if not color and auto_color:
                color = auto_color  # 未選顏色則套用自動偵測

        conn = get_db()
        conn.execute('''
            INSERT INTO stones (stone_type, photo, photo2, photo3,
                                width, height, thickness, quantity, unit, price, vendor, description, color,
                                image_hash, dominant_rgb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (stone_type, photo, photo2, photo3,
              width, height, thickness, quantity, unit, price, vendor, description, color,
              image_hash, dominant_rgb))
        conn.commit()
        conn.close()

        msg = f'「{stone_type}」已成功新增！'
        if photo and not request.form.get('color') and color:
            color_label = COLOR_MAP.get(color, ('', color, '', ''))[1]
            msg += f' 已自動偵測顏色為「{color_label}」'
        flash(msg, 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('stone_form.html', stone=None, title='新增石材', colors=COLORS)


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
        color       = request.form.get('color', '')

        # 處理三張照片（有新上傳才替換）
        photos = []
        main_photo_changed = False
        for field, old_key in [('photo', 'photo'), ('photo2', 'photo2'), ('photo3', 'photo3')]:
            new_file = request.files.get(field)
            new_photo = save_photo(new_file)
            if new_photo:
                delete_photo(stone[old_key])
                photos.append(new_photo)
                if field == 'photo':
                    main_photo_changed = True
            else:
                photos.append(stone[old_key])

        # 主照片若有變更或缺少分析資料，則重新分析
        image_hash = stone['image_hash'] if 'image_hash' in stone.keys() else ''
        dominant_rgb = stone['dominant_rgb'] if 'dominant_rgb' in stone.keys() else ''
        if photos[0] and (main_photo_changed or not image_hash):
            auto_color, image_hash, dominant_rgb = analyze_image(
                os.path.join(app.config['UPLOAD_FOLDER'], photos[0]))
            if not color and auto_color:
                color = auto_color

        conn.execute('''
            UPDATE stones
            SET stone_type=?, photo=?, photo2=?, photo3=?,
                width=?, height=?, thickness=?,
                quantity=?, unit=?, price=?, vendor=?, description=?, color=?,
                image_hash=?, dominant_rgb=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (stone_type, photos[0], photos[1], photos[2],
              width, height, thickness, quantity, unit, price, vendor, description, color,
              image_hash, dominant_rgb, id))
        conn.commit()
        conn.close()

        flash(f'「{stone_type}」資料已更新！', 'success')
        return redirect(url_for('admin_dashboard'))

    conn.close()
    return render_template('stone_form.html', stone=stone, title='編輯石材', colors=COLORS)


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


# ─── AI 圖片功能：以圖搜圖 ────────────────────────────────────

@app.route('/search/by-image', methods=['GET', 'POST'])
def search_by_image():
    if request.method == 'POST':
        ref_file = request.files.get('reference')
        if not ref_file or not ref_file.filename or not allowed_file(ref_file.filename):
            flash('請上傳有效的圖片（JPG／PNG／GIF／WEBP）', 'error')
            return redirect(url_for('search_by_image'))

        # 讀取參考圖、分析、轉成 base64 顯示（不寫入磁碟）
        import base64
        ref_bytes = ref_file.read()
        ref_b64 = base64.b64encode(ref_bytes).decode()
        ref_data_url = f'data:image/jpeg;base64,{ref_b64}'

        from io import BytesIO
        ref_color, ref_hash, ref_rgb = analyze_image(BytesIO(ref_bytes))

        if not ref_hash:
            flash('無法分析此圖片，請改用其他圖', 'error')
            return redirect(url_for('search_by_image'))

        # 比對所有有索引的石材
        conn = get_db()
        stones = conn.execute('SELECT * FROM stones').fetchall()
        conn.close()

        results = []
        for s in stones:
            sh = s['image_hash'] if 'image_hash' in s.keys() else ''
            sr = s['dominant_rgb'] if 'dominant_rgb' in s.keys() else ''
            if not sh:
                continue
            h_dist = hash_distance(ref_hash, sh)            # 0-64
            c_dist = rgb_distance(ref_rgb, sr) if sr else 220  # 0-441
            # 綜合分數：紋理 50% + 色彩 50%（越小越相似）
            norm = (h_dist / 64.0) * 0.5 + (c_dist / 441.0) * 0.5
            similarity = round(max(0.0, (1.0 - norm)) * 100, 1)
            results.append((s, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:12]

        return render_template('image_search.html',
                               results=results,
                               reference_url=ref_data_url,
                               detected_color=COLOR_MAP.get(ref_color),
                               color_map=COLOR_MAP,
                               not_indexed_count=sum(1 for s in stones
                                                     if not (s['image_hash'] if 'image_hash' in s.keys() else '')))

    return render_template('image_search.html', results=None, reference_url=None)


@app.route('/admin/reindex-images', methods=['POST'])
@admin_required
def reindex_images():
    """為現有的石材重新計算照片雜湊與顏色（一次性遷移用）"""
    conn = get_db()
    stones = conn.execute('SELECT id, photo, color FROM stones WHERE photo IS NOT NULL AND photo != ""').fetchall()
    updated = 0
    color_filled = 0
    for s in stones:
        path = os.path.join(app.config['UPLOAD_FOLDER'], s['photo'])
        if not os.path.exists(path):
            continue
        auto_color, phash, rgb = analyze_image(path)
        if not phash:
            continue
        new_color = s['color'] if s['color'] else auto_color
        if not s['color'] and auto_color:
            color_filled += 1
        conn.execute('UPDATE stones SET image_hash=?, dominant_rgb=?, color=? WHERE id=?',
                     (phash, rgb, new_color, s['id']))
        updated += 1
    conn.commit()
    conn.close()
    flash(f'✅ 已重新索引 {updated} 筆石材，自動補上 {color_filled} 筆顏色標籤', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/export/stones')
@admin_required
def export_stones():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '石材庫存'
    ws.append(['ID', '石材種類', '顏色', '寬(cm)', '高(cm)', '厚(cm)', '數量', '單位', '單價(NT$)', '廠商', '說明', '建立時間'])
    conn = get_db()
    stones = conn.execute('SELECT * FROM stones ORDER BY id').fetchall()
    conn.close()
    for s in stones:
        color_label = COLOR_MAP.get(s['color'] or '', ('', '', '', ''))[1] if s['color'] else ''
        ws.append([s['id'], s['stone_type'], color_label,
                   s['width'], s['height'], s['thickness'],
                   s['quantity'], s['unit'], s['price'],
                   s['vendor'], s['description'], s['created_at']])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='stones_export.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/admin/export/inquiries')
@admin_required
def export_inquiries():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '詢問記錄'
    ws.append(['ID', '石材', '客戶姓名', 'Email', '電話', '詢問數量', '留言', '狀態', '建立時間'])
    conn = get_db()
    rows = conn.execute('SELECT * FROM inquiries ORDER BY id DESC').fetchall()
    conn.close()
    status_map = {'pending': '待處理', 'replied': '已回覆', 'closed': '已結案'}
    for r in rows:
        ws.append([r['id'], r['stone_name'], r['customer_name'], r['customer_email'],
                   r['customer_phone'], r['quantity'], r['message'],
                   status_map.get(r['status'], r['status']), r['created_at']])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='inquiries_export.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


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
