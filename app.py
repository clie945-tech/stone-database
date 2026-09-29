from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_mail import Mail, Message
import sqlite3
import os
import io
import secrets
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from translations import LANGS, DEFAULT_LANG, HTML_LANG, translate

app = Flask(__name__)
app.secret_key = 'stone-circular-db-secret-2024'

# 上傳資料夾與資料庫路徑：優先讀環境變數（Railway Volume 用），預設本機開發用相對路徑
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
DB_PATH = os.environ.get('DB_PATH', 'stone_database.db')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'heic', 'heif'}

# 每位會員「我的設計」最多保留的合成圖數量，超過時自動刪除最舊的（控制 Volume 容量）
HISTORY_LIMIT = 30

# 每位會員「每日 AI 生圖」次數上限（控制 Gemini 付費 API 成本）；台灣時區每日 0 點重置。
# 可在 Railway 用環境變數 AI_DAILY_LIMIT 隨時調整，免改程式。設為 0 表示不限制。
from datetime import datetime, timezone, timedelta
AI_DAILY_LIMIT = int(os.environ.get('AI_DAILY_LIMIT', '5'))
_TPE_TZ = timezone(timedelta(hours=8))  # Asia/Taipei


def _setup_upload_symlink():
    """讓 /static/uploads URL 能對應到實際儲存位置（Volume 在不同路徑時用 symlink 連回）"""
    default_path = 'static/uploads'
    target = UPLOAD_FOLDER

    # 確保實際儲存資料夾存在
    os.makedirs(target, exist_ok=True)

    # 如果 UPLOAD_FOLDER 就是預設位置，不需要 symlink
    if os.path.abspath(target) == os.path.abspath(default_path):
        return

    # 確保 parent (static/) 存在
    os.makedirs(os.path.dirname(default_path) or '.', exist_ok=True)

    # 處理 static/uploads 既有狀態
    if os.path.lexists(default_path):
        if os.path.islink(default_path):
            return  # 已是 symlink，假設正確
        # 是實體資料夾：把裡面的檔案（如 .gitkeep 或舊照片）處理掉
        import shutil
        for name in os.listdir(default_path):
            src = os.path.join(default_path, name)
            if name == '.gitkeep':
                try:
                    os.remove(src)
                except OSError:
                    pass
                continue
            # 其他檔案搬到實際儲存位置（如果還沒在那邊）
            dst = os.path.join(target, name)
            try:
                if os.path.exists(dst):
                    os.remove(src)
                else:
                    shutil.move(src, dst)
                    print(f'[setup] 搬移既有檔案：{name}')
            except OSError as e:
                print(f'[setup] 搬移 {name} 失敗：{e}')
        # 移除空資料夾
        try:
            os.rmdir(default_path)
        except OSError as e:
            # 最後手段：強制遞迴刪除
            try:
                shutil.rmtree(default_path, ignore_errors=True)
            except Exception:
                print(f'[setup] 無法移除 {default_path}：{e}')
                return

    # 建立 symlink
    try:
        os.symlink(os.path.abspath(target), default_path)
        print(f'[setup] symlink 已建立：{default_path} → {target}')
    except (FileExistsError, OSError) as e:
        print(f'[setup] symlink 建立失敗：{e}')


_setup_upload_symlink()

# 啟用 HEIC / HEIF 格式支援（iPhone 預設拍照格式）
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORTED = True
    print('[startup] HEIC / HEIF 格式支援已啟用')
except ImportError:
    HEIC_SUPPORTED = False
    print('[startup] ⚠ pillow-heif 未安裝，HEIC 格式將無法上傳')

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

# ── Replicate AI 設定（從環境變數讀取）──
REPLICATE_API_TOKEN = os.environ.get('REPLICATE_API_TOKEN', '')
# 預設使用 flux-fill-pro（高品質 inpainting）
REPLICATE_MODEL = os.environ.get('REPLICATE_MODEL', 'black-forest-labs/flux-fill-pro')

# ── Gemini AI 設定（從環境變數讀取）──
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '') or os.environ.get('GOOGLE_API_KEY', '')
GEMINI_VISION_MODEL = os.environ.get('GEMINI_VISION_MODEL', 'gemini-2.5-flash')
GEMINI_IMAGE_MODEL = os.environ.get('GEMINI_IMAGE_MODEL', 'gemini-2.5-flash-image')

# ── 顏色標籤定義 ──
COLORS = [
    ('white',  '白色系', '#F8FAFC', '#64748B'),
    ('gray',   '灰色系', '#E2E8F0', '#475569'),
    ('black',  '黑色系', '#1E293B', '#F1F5F9'),
    ('beige',  '米色系', '#FEF3C7', '#92400E'),
    ('brown',  '棕色系', '#78350F', '#FEF3C7'),
    ('green',  '綠色系', '#D1FAE5', '#065F46'),
    ('red',    '紅色系', '#FEE2E2', '#991B1B'),
    ('multi',  '其他',   '#F3E8FF', '#6D28D9'),
]
COLOR_MAP = {c[0]: c for c in COLORS}

# ── 合作石材廠商清單 ──（未來新增請編輯此處）
VENDORS = [
    '同達大理石股份有限公司',
    '東星名石股份有限公司',
    '高陽益實業股份有限公司',
    '鎮一大理石有限公司',
]

# ──────────────────────────────────────────────────────────────────────
# 減碳效益計算（依 ICE Database v3.0, University of Bath, UK）
# 數據範疇：cradle-to-gate（開採至出廠）
# 單位：kg CO2e / m³
# ──────────────────────────────────────────────────────────────────────
CARBON_COEFFICIENTS = {
    '大理石': 237,
    '蛇紋石': 250,
    '化石':   200,
    '花崗岩': 280,
}
DEFAULT_CARBON_COEFFICIENT = 230  # 未知種類的預設值

# 生活化等量換算（讓抽象數字變具體）
CO2_PER_TREE_YEAR = 21.0       # 1 棵成樹/年 ≈ 21 kg CO2
CO2_PER_CAR_KM    = 0.120      # 汽車排放 ≈ 120 g/km
CO2_PER_KWH_TW    = 0.495      # 台電碳排係數（2024 公告值）


def calculate_carbon_saved(stone_type, width, height, thickness, quantity):
    """計算該批石材若回收使用可減少之碳排放（kg CO2e）

    Formula:  總體積 (m³) × 碳排係數 (kg CO2e/m³)
    """
    try:
        w = float(width or 0)
        h = float(height or 0)
        t = float(thickness or 0)
        q = int(quantity or 0)
        if not (w and h and t and q):
            return 0.0
        volume_m3 = (w * h * t / 1_000_000.0) * q   # cm³ → m³
        coef = CARBON_COEFFICIENTS.get(stone_type, DEFAULT_CARBON_COEFFICIENT)
        return volume_m3 * coef
    except (ValueError, TypeError):
        return 0.0


def carbon_equivalents(kg_co2):
    """把 kg CO2 翻譯成日常情境，回傳 dict"""
    if not kg_co2 or kg_co2 <= 0:
        return {'trees': 0, 'car_km': 0, 'kwh': 0}
    return {
        'trees':  kg_co2 / CO2_PER_TREE_YEAR,
        'car_km': kg_co2 / CO2_PER_CAR_KM,
        'kwh':    kg_co2 / CO2_PER_KWH_TW,
    }


def format_carbon(kg_co2):
    """格式化 kg CO2 顯示：< 1 顯示 g，>= 1000 顯示 t"""
    if kg_co2 < 1:
        return f"{kg_co2 * 1000:.0f} g"
    if kg_co2 < 1000:
        return f"{kg_co2:.1f} kg"
    return f"{kg_co2 / 1000:.2f} t"


# ─── 多語系（中文 / English / 日本語）──────────────────────────
def current_lang():
    """決定目前語言：session 選擇 > 瀏覽器語言 > 預設中文。"""
    lang = session.get('lang')
    if lang in LANGS:
        return lang
    # 首次到訪：依瀏覽器 Accept-Language 自動判斷（展場外賓可直接看到母語）
    best = request.accept_languages.best_match(['zh', 'zh-TW', 'zh-CN', 'en', 'ja'])
    if best:
        if best.startswith('ja'):
            return 'ja'
        if best.startswith('en'):
            return 'en'
    return DEFAULT_LANG


def _(msg):
    """把系統訊息翻成使用者目前語言；不在請求情境時回傳原文。"""
    try:
        return translate(msg, current_lang())
    except Exception:
        return msg


@app.route('/lang/<code>')
def set_lang(code):
    """切換語言後回到原本的頁面。"""
    if code in LANGS:
        session['lang'] = code
    target = request.referrer or url_for('index')
    return redirect(target)


def loc(row, field, lang=None):
    """取資料庫內容的在地化版本：<field>_en / <field>_ja，留空則回退中文原文。

    row 可以是 sqlite3.Row 或 dict。例：loc(stone, 'stone_name')
    """
    if row is None:
        return ''
    lang = lang or current_lang()
    base = ''
    try:
        base = row[field] or ''
    except (KeyError, IndexError, TypeError):
        base = ''
    if lang == DEFAULT_LANG:
        return base
    try:
        val = row[f'{field}_{lang}']
        if val:
            return val
    except (KeyError, IndexError, TypeError):
        pass
    return base


@app.context_processor
def inject_i18n():
    """讓所有模板都能用 t() 翻譯與語言資訊。"""
    lang = current_lang()
    return dict(
        t=lambda s: translate(s, lang),
        loc=lambda row, field: loc(row, field, lang),
        current_lang=lang,
        html_lang=HTML_LANG.get(lang, 'zh-TW'),
        LANGS=LANGS,
    )


@app.context_processor
def inject_carbon_helpers():
    """讓所有模板都能用減碳計算 helper"""
    return dict(
        calc_carbon=calculate_carbon_saved,
        carbon_eq=carbon_equivalents,
        fmt_carbon=format_carbon,
    )


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


# ─── 石材視覺特徵（以圖搜圖用）─────────────────────────────────
# pHash 是為「同一張圖的不同版本」設計的，對石材這種隨機紋理容易誤判：
# 同一塊石材換角度就找不到、不同石材只要明暗分布像就誤判。
# 改用「HSV 色彩直方圖 + 紋理統計量」，對角度與光線變化穩健得多。
FEATURE_VERSION = 2


def extract_stone_features(img):
    """從 PIL Image 抽出石材視覺特徵（色彩直方圖 + 紋理統計），回傳 dict。"""
    import numpy as np
    from PIL import Image

    if img.mode != 'RGB':
        img = img.convert('RGB')
    img = img.resize((256, 256), Image.BILINEAR)   # 統一尺度，消除解析度差異

    hsv = np.asarray(img.convert('HSV'), dtype=np.float32)
    h, s, v = hsv[..., 0] / 255.0, hsv[..., 1] / 255.0, hsv[..., 2] / 255.0

    # 色相：石材多為灰白米色，低飽和像素的色相無意義 → 另計為「無彩色」bin，
    # 這樣「兩張都是灰白石材」會正確地互相匹配，而不是被當成沒有共同色相。
    chromatic = s > 0.18
    h_hist = np.zeros(13, dtype=np.float32)
    if chromatic.any():
        np.add.at(h_hist, np.clip((h[chromatic] * 12).astype(int), 0, 11), 1.0)
    h_hist[12] = float((~chromatic).sum())
    h_hist /= max(1.0, float(h_hist.sum()))

    s_hist = np.histogram(s, bins=5, range=(0.0, 1.0))[0].astype(np.float32)
    s_hist /= max(1.0, float(s_hist.sum()))
    v_hist = np.histogram(v, bins=8, range=(0.0, 1.0))[0].astype(np.float32)
    v_hist /= max(1.0, float(v_hist.sum()))

    # 紋理：明度梯度描述「紋理強度」，縮圖後仍存的梯度比例描述「紋理粗細」
    detail = float(np.abs(np.diff(v, axis=1)).mean() + np.abs(np.diff(v, axis=0)).mean())
    contrast = float(v.std())
    small = np.asarray(img.convert('L').resize((64, 64), Image.BILINEAR), dtype=np.float32) / 255.0
    coarse = float(np.abs(np.diff(small, axis=1)).mean() + np.abs(np.diff(small, axis=0)).mean())
    scale = min(coarse / detail, 4.0) if detail > 1e-6 else 0.0

    return {
        'v': FEATURE_VERSION,
        'h': [round(float(x), 5) for x in h_hist],
        's': [round(float(x), 5) for x in s_hist],
        'vv': [round(float(x), 5) for x in v_hist],
        't': [round(contrast, 5), round(detail, 5), round(scale, 5)],
    }


def features_to_json(feat):
    import json
    return json.dumps(feat, separators=(',', ':')) if feat else ''


def features_from_json(raw):
    import json
    if not raw:
        return None
    try:
        f = json.loads(raw)
        return f if isinstance(f, dict) and f.get('v') == FEATURE_VERSION else None
    except Exception:
        return None


def _hist_distance(a, b):
    """直方圖交集距離（0 = 完全相同，1 = 完全不同）"""
    return max(0.0, 1.0 - sum(min(x, y) for x, y in zip(a, b)))


def feature_distance(f1, f2):
    """兩組石材特徵的距離（0 = 相同，1 = 完全不同）。色彩 62% + 紋理 38%。"""
    if not f1 or not f2:
        return 1.0
    try:
        dh = _hist_distance(f1['h'], f2['h'])
        ds = _hist_distance(f1['s'], f2['s'])
        dv = _hist_distance(f1['vv'], f2['vv'])
        t1, t2 = f1['t'], f2['t']
        # 三個紋理量各以典型滿量程正規化後平均
        dt = min(1.0, (abs(t1[0] - t2[0]) / 0.35
                       + abs(t1[1] - t2[1]) / 0.12
                       + abs(t1[2] - t2[2]) / 3.0) / 3.0)
        return dh * 0.28 + ds * 0.12 + dv * 0.22 + dt * 0.38
    except Exception:
        return 1.0


def analyze_image_full(src, box=None):
    """分析圖片，回傳 (color_code, phash, rgb_str, features_json)。
    box 為 (left, top, right, bottom) 的 0-1 比例值，用於只分析圈選範圍。"""
    try:
        from PIL import Image
        if hasattr(src, 'read'):
            src.seek(0)
            img = Image.open(src).convert('RGB')
        else:
            img = Image.open(src).convert('RGB')

        if box:
            W, H = img.size
            l, t, r, b = box
            l, t = max(0.0, min(l, 1.0)), max(0.0, min(t, 1.0))
            r, b = max(0.0, min(r, 1.0)), max(0.0, min(b, 1.0))
            px = (int(l * W), int(t * H), int(r * W), int(b * H))
            # 太小的框不裁（避免誤觸產生無意義的結果）
            if px[2] - px[0] >= 16 and px[3] - px[1] >= 16:
                img = img.crop(px)

        color_code, rgb_str = _dominant_color(img)
        import imagehash
        phash = str(imagehash.phash(img))
        feats = extract_stone_features(img)
        return (color_code, phash, rgb_str, features_to_json(feats))
    except Exception as e:
        print(f'[圖片分析失敗] {e}')
        return ('', '', '', '')


def _dominant_color(img):
    """量化取主色，回傳 (color_code, 'r,g,b')。"""
    from PIL import Image
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
        r, g, b = palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2]
        return (classify_rgb(r, g, b), f'{r},{g},{b}')
    return ('', '')


def send_email_safe(subject, recipients, html_body):
    """安全發送 Email，若未設定則略過"""
    if not app.config.get('MAIL_USERNAME'):
        return
    try:
        msg = Message(subject, recipients=recipients, html=html_body)
        mail.send(msg)
    except Exception as e:
        print(f'[Email 發送失敗] {e}')


# ── AI Prompt 自動生成（給設計工具 inpainting 用）──
STONE_PROMPT_EN = {
    '大理石': 'marble',
    '蛇紋石': 'serpentine stone',
    '化石': 'fossil limestone',
    '花崗岩': 'granite',
}
COLOR_WORD_EN = {
    'white': 'white',
    'gray':  'gray',
    'black': 'black',
    'beige': 'beige',
    'brown': 'brown',
    'green': 'green',
    'red':   'reddish',
    'multi': 'natural colored',
}

def generate_ai_prompt(stone_type, color, description=''):
    """產生簡短的 inpainting prompt（後備用，當視覺 AI 無法呼叫時）"""
    base = STONE_PROMPT_EN.get(stone_type, 'natural stone')
    color_word = COLOR_WORD_EN.get(color, '')
    parts = [color_word, base, 'polished surface']
    return ' '.join([p for p in parts if p]).strip()


_LAST_VISION_ERROR = ''

STONE_VISION_PROMPT = (
    'You are describing a natural stone slab surface for photorealistic texture generation. '
    'In 18-28 English words, describe ONLY the material itself: '
    '(1) base colour and secondary tones; '
    '(2) veining or speckles — their colour, thickness, density and direction; '
    '(3) overall pattern type (marbled, brecciated, speckled, or uniform); '
    '(4) surface finish (polished glossy, honed matte, or textured). '
    'Be concrete and visual. Do NOT mention background, lighting, objects, people, or shape. '
    'Example: "creamy white marble, fine grey diagonal veining with subtle gold flecks, '
    'medium density, smooth high-gloss polished finish". '
    'Output ONLY the comma-separated description phrase — no preamble, no quotes, no full sentence.'
)


def _clean_caption(caption):
    caption = (caption or '').strip().strip('"\'').rstrip('.')
    for prefix in ('Description:', 'description:', 'The image shows', 'This stone', 'The stone'):
        if caption.startswith(prefix):
            caption = caption[len(prefix):].lstrip(' :,').strip()
            break
    if len(caption) > 240:
        caption = caption[:240].rsplit(',', 1)[0]
    return caption


def _describe_with_gemini(image_path):
    """用 Gemini 視覺模型描述石材（首選：快、準、有免費額度、不受 Replicate 限速）。"""
    global _LAST_VISION_ERROR
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        with open(image_path, 'rb') as f:
            img_bytes = f.read()
        mime = 'image/png' if image_path.lower().endswith('.png') else 'image/jpeg'
        resp = client.models.generate_content(
            model=GEMINI_VISION_MODEL,
            contents=[types.Part.from_bytes(data=img_bytes, mime_type=mime), STONE_VISION_PROMPT],
        )
        caption = _clean_caption(getattr(resp, 'text', '') or '')
        if not caption:
            _LAST_VISION_ERROR = 'Gemini 回傳空白描述'
        return caption
    except Exception as e:
        _LAST_VISION_ERROR = f'Gemini {type(e).__name__}: {str(e)[:200]}'
        print(f'[Gemini Vision 錯誤] {_LAST_VISION_ERROR}')
        return ''


def translate_fields_with_gemini(items):
    """把中文欄位批次翻成英文與日文。

    items: {欄位名: 中文內容} —— 例如 {'stone_name': '和平白', 'description': '...'}
    回傳:  {'en': {欄位名: 英文}, 'ja': {欄位名: 日文}}；失敗回傳 None。

    石材品名採「國際通名／音譯 + 材質描述」而非直譯（例：和平白 → Hoping White）。
    """
    import json as _json
    import re as _re
    payload = {k: v for k, v in items.items() if v and str(v).strip()}
    if not payload:
        return {'en': {}, 'ja': {}}
    if not GEMINI_API_KEY:
        return None
    prompt = (
        'You are translating content for a Taiwanese circular-stone materials platform '
        '(reclaimed and offcut natural stone for designers).\n'
        'Translate each field from Traditional Chinese into English and Japanese.\n\n'
        'Rules:\n'
        '- Stone product names (stone_name) are proper nouns: use the established international '
        'trade name when one exists (卡拉拉白 -> Carrara White); otherwise romanise the place or '
        'brand name and keep the colour word (和平白 -> Hoping White). For Japanese, use katakana '
        'for romanised names.\n'
        '- Company names (vendor): use the official English name if evident, otherwise a natural '
        'romanisation. Japanese may keep kanji where natural.\n'
        '- Descriptions and announcements: translate naturally and concisely in the professional '
        'tone of a materials supplier. Preserve line breaks.\n'
        '- Do not invent information that is not in the source.\n\n'
        'Return ONLY a JSON object shaped exactly like:\n'
        '{"en": {<same keys>}, "ja": {<same keys>}}\n\n'
        'Source (Traditional Chinese):\n' + _json.dumps(payload, ensure_ascii=False, indent=2)
    )
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(model=GEMINI_VISION_MODEL, contents=[prompt])
        raw = (getattr(resp, 'text', '') or '').strip()
        raw = _re.sub(r'^```(?:json)?\s*|\s*```$', '', raw).strip()   # 去掉 ``` 圍欄
        data = _json.loads(raw)
        out = {}
        for lang in ('en', 'ja'):
            d = data.get(lang) or {}
            out[lang] = {k: str(d.get(k, '') or '').strip() for k in payload}
        return out
    except Exception as e:
        print(f'[Gemini 翻譯錯誤] {type(e).__name__}: {str(e)[:200]}')
        return None


def _describe_with_llava(image_path):
    """用 Replicate LLaVA 視覺 AI 描述石材（後備）。"""
    global _LAST_VISION_ERROR
    try:
        import replicate
        client = replicate.Client(api_token=REPLICATE_API_TOKEN)
        model_name = 'yorickvp/llava-v1.6-mistral-7b'
        try:
            model = client.models.get(model_name)
            ref = f'{model_name}:{model.latest_version.id}' if getattr(model, 'latest_version', None) else model_name
        except Exception:
            ref = model_name
        with open(image_path, 'rb') as f:
            output = client.run(ref, input={
                'image': f, 'prompt': STONE_VISION_PROMPT,
                'temperature': 0.15, 'max_tokens': 90,
            })
        caption = _clean_caption(''.join(str(t) for t in output) if isinstance(output, list) else str(output))
        if not caption:
            _LAST_VISION_ERROR = 'AI 回傳空白描述'
        return caption
    except Exception as e:
        _LAST_VISION_ERROR = f'{type(e).__name__}: {str(e)[:200]}'
        print(f'[Vision AI 錯誤] {_LAST_VISION_ERROR}')
        return ''


def describe_stone_with_vision(image_path):
    """看石材照片產生精準材質描述。優先用 Gemini，無金鑰時退回 Replicate LLaVA。"""
    global _LAST_VISION_ERROR
    _LAST_VISION_ERROR = ''
    if not image_path or not os.path.exists(image_path):
        _LAST_VISION_ERROR = f'找不到照片檔案：{image_path}'
        return ''
    if GEMINI_API_KEY:
        caption = _describe_with_gemini(image_path)
        if caption:
            return caption
    if REPLICATE_API_TOKEN:
        return _describe_with_llava(image_path)
    if not _LAST_VISION_ERROR:
        _LAST_VISION_ERROR = '未設定 GEMINI_API_KEY 或 REPLICATE_API_TOKEN'
    return ''


_LAST_SYNTH_ERROR = ''

def synthesize_with_gemini(design_path, mask_path, stone_photo_path, max_side=1280):
    """方案②：用 Gemini 2.5 Flash Image 把『實際石材照片』的材質貼到設計圖遮罩區（參考圖編輯）。
    在遮罩區塗半透明洋紅當「目標區域」提示，連同石材參考圖一起交給 Gemini 編輯。
    回傳合成後 PIL Image；失敗回 None 並記錄 _LAST_SYNTH_ERROR。"""
    global _LAST_SYNTH_ERROR
    _LAST_SYNTH_ERROR = ''
    try:
        from io import BytesIO
        from PIL import Image
        from google import genai
        from google.genai import types

        design = Image.open(design_path).convert('RGB')
        if max(design.size) > max_side:
            r = max_side / max(design.size)
            design = design.resize((round(design.width * r), round(design.height * r)), Image.LANCZOS)
        W, H = design.size
        mask = Image.open(mask_path).convert('L').resize((W, H), Image.LANCZOS)

        # 在遮罩區疊半透明洋紅，標示要替換的目標表面
        magenta = Image.new('RGB', (W, H), (255, 0, 255))
        marked = Image.composite(Image.blend(design, magenta, 0.5), design, mask)

        stone = Image.open(stone_photo_path).convert('RGB')
        if max(stone.size) > max_side:
            r = max_side / max(stone.size)
            stone = stone.resize((round(stone.width * r), round(stone.height * r)), Image.LANCZOS)

        def to_part(img):
            b = BytesIO(); img.save(b, 'PNG')
            return types.Part.from_bytes(data=b.getvalue(), mime_type='image/png')

        instruction = (
            'Image 1 is an interior or product design photo with a TARGET AREA highlighted in semi-transparent magenta. '
            'Image 2 is a real natural stone material sample. '
            'Re-surface ONLY the magenta-highlighted area of Image 1 with the EXACT stone material from Image 2 — '
            'same base colour, veining and pattern — following the surface perspective and preserving the original '
            'lighting, shadows and reflections so it looks photorealistic. '
            'Do NOT change anything outside the highlighted area, and completely remove the magenta highlight. '
            'Return only the edited image.'
        )

        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=[instruction, to_part(marked), to_part(stone)],
            config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE']),
        )
        # 萃取輸出影像（先用 resp.parts，再退回 candidates）；同時收集文字以利診斷
        parts = getattr(resp, 'parts', None)
        if not parts:
            parts = []
            for cand in (getattr(resp, 'candidates', None) or []):
                parts += (getattr(getattr(cand, 'content', None), 'parts', None) or [])
        text_chunks = []
        for part in (parts or []):
            inline = getattr(part, 'inline_data', None)
            if inline and getattr(inline, 'data', None):
                return Image.open(BytesIO(inline.data)).convert('RGB')
            if getattr(part, 'text', None):
                text_chunks.append(part.text)
        note = (' 模型回應文字：' + ' '.join(text_chunks)[:180]) if text_chunks else \
               ' 無影像也無文字（模型可能不可用、未開通或被安全機制擋下）'
        _LAST_SYNTH_ERROR = 'Gemini 未回傳影像。' + note
        return None
    except Exception as e:
        _LAST_SYNTH_ERROR = f'Gemini {type(e).__name__}: {str(e)[:200]}'
        print(f'[Gemini 合成錯誤] {_LAST_SYNTH_ERROR}')
        return None


# 展覽圖庫：5 個空間情境（一步到位，直接把石材生成在場景中）
SHOWCASE_SCENES = [
    {'label': '現代客廳特色牆', 'prompt': 'a modern minimalist living room with a full-height feature wall behind the sofa'},
    {'label': '餐廳餐桌桌面',   'prompt': 'an elegant dining room, close-up hero shot of the rectangular dining table top'},
    {'label': '廚房中島檯面',   'prompt': 'a contemporary luxury kitchen, focus on the large kitchen island countertop'},
    {'label': '旅店接待櫃台',   'prompt': 'a boutique hotel lobby, focus on the reception desk front cladding panel'},
    {'label': '衛浴洗手檯面',   'prompt': 'a high-end hotel bathroom, focus on the vanity countertop and backsplash'},
]


def generate_showcase_scene(stone_photo_path, scene_prompt):
    """展覽圖庫：把實際石材直接生成在指定空間情境中（單張）。回傳 PIL Image 或 None。"""
    global _LAST_SYNTH_ERROR
    _LAST_SYNTH_ERROR = ''
    try:
        from io import BytesIO
        from PIL import Image
        from google import genai
        from google.genai import types

        with open(stone_photo_path, 'rb') as f:
            stone_bytes = f.read()
        mime = 'image/png' if stone_photo_path.lower().endswith('.png') else 'image/jpeg'
        prompt = (
            f'Create a photorealistic interior design photograph: {scene_prompt}. '
            'The main surface is finished with the EXACT natural stone material shown in the reference image — '
            'faithfully match its real base colour, veining and pattern. '
            'High-end architectural interior photography, soft natural daylight, elegant modern styling, '
            'realistic reflections and shadows, shallow depth of field. No text, no watermark, no people.'
        )
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=[prompt, types.Part.from_bytes(data=stone_bytes, mime_type=mime)],
            config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE']),
        )
        parts = getattr(resp, 'parts', None)
        if not parts:
            parts = []
            for cand in (getattr(resp, 'candidates', None) or []):
                parts += (getattr(getattr(cand, 'content', None), 'parts', None) or [])
        text_chunks = []
        for part in (parts or []):
            inline = getattr(part, 'inline_data', None)
            if inline and getattr(inline, 'data', None):
                return Image.open(BytesIO(inline.data)).convert('RGB')
            if getattr(part, 'text', None):
                text_chunks.append(part.text)
        _LAST_SYNTH_ERROR = 'Gemini 未回傳影像。' + (
            ('模型回應：' + ' '.join(text_chunks)[:160]) if text_chunks else '（無內容）')
        return None
    except Exception as e:
        _LAST_SYNTH_ERROR = f'Gemini {type(e).__name__}: {str(e)[:200]}'
        print(f'[展覽圖庫生成錯誤] {_LAST_SYNTH_ERROR}')
        return None


def render_sketch_with_gemini(sketch_path, stone_photo_path, hint=''):
    """草圖渲染：把設計草圖 + 石材照片，用 Gemini 生成寫實產品渲染圖。回傳 PIL Image 或 None。"""
    global _LAST_SYNTH_ERROR
    _LAST_SYNTH_ERROR = ''
    try:
        from io import BytesIO
        from PIL import Image
        from google import genai
        from google.genai import types

        def part_of(path):
            with open(path, 'rb') as f:
                data = f.read()
            mime = 'image/png' if path.lower().endswith('.png') else 'image/jpeg'
            return types.Part.from_bytes(data=data, mime_type=mime)

        hint_line = f' The product is a {hint}.' if hint else ''
        prompt = (
            'Image 1 is a design SKETCH or line drawing of a product. Image 2 is a real natural stone material sample. '
            'Produce a photorealistic studio PRODUCT RENDERING of the object shown in the sketch, '
            'manufactured from the stone material in Image 2 — faithfully match its real colour, veining and pattern. '
            'Keep the form, proportions and structure faithful to the sketch.' + hint_line +
            ' Clean neutral studio background, soft realistic lighting, accurate reflections and shadows, '
            'high-end product photography. No text, no watermark, no people. Return only the rendered image.'
        )
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=[prompt, part_of(sketch_path), part_of(stone_photo_path)],
            config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE']),
        )
        parts = getattr(resp, 'parts', None)
        if not parts:
            parts = []
            for cand in (getattr(resp, 'candidates', None) or []):
                parts += (getattr(getattr(cand, 'content', None), 'parts', None) or [])
        text_chunks = []
        for part in (parts or []):
            inline = getattr(part, 'inline_data', None)
            if inline and getattr(inline, 'data', None):
                return Image.open(BytesIO(inline.data)).convert('RGB')
            if getattr(part, 'text', None):
                text_chunks.append(part.text)
        _LAST_SYNTH_ERROR = 'Gemini 未回傳影像。' + (
            ('模型回應：' + ' '.join(text_chunks)[:160]) if text_chunks else '（無內容）')
        return None
    except Exception as e:
        _LAST_SYNTH_ERROR = f'Gemini {type(e).__name__}: {str(e)[:200]}'
        print(f'[草圖渲染錯誤] {_LAST_SYNTH_ERROR}')
        return None


def simulate_wall_perspective(design_path, corners_frac, stone_photo_path,
                              stone_w_cm, stone_h_cm, wall_w_cm, wall_h_cm,
                              show_joints=True, max_side=1600):
    """牆面模擬（本地幾何運算，免 AI）：
    1) 依「牆面實際尺寸 ÷ 石材實際尺寸」計算拼貼片數 → 比例正確
    2) 石材照片拼貼成平面材質（棋盤式鏡像對花、可加拼縫線）
    3) 以透視投影把材質精準貼進牆面四角 → 透視正確
    4) 轉移原牆低頻光影，保留現場明暗
    corners_frac：[左上,右上,右下,左下] 的 (0~1) 比例座標。
    回傳 (PIL Image, tiles_x, tiles_y)。"""
    import math
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageOps

    design = Image.open(design_path).convert('RGB')
    if max(design.size) > max_side:
        r = max_side / max(design.size)
        design = design.resize((round(design.width * r), round(design.height * r)), Image.LANCZOS)
    W, H = design.size
    quad = [(fx * W, fy * H) for fx, fy in corners_frac]

    # 四邊形有效性（鞋帶公式面積 > 影像 0.5%）
    area = abs(sum(quad[i][0] * quad[(i + 1) % 4][1] - quad[(i + 1) % 4][0] * quad[i][1]
                   for i in range(4))) / 2
    if area < W * H * 0.005:
        raise ValueError('牆面四角範圍太小或無效，請重新點選')

    # 拼貼片數：依實際尺寸換算
    tiles_x = max(1, math.ceil(wall_w_cm / stone_w_cm))
    tiles_y = max(1, math.ceil(wall_h_cm / stone_h_cm))

    # 平面材質：每片 cover 裁切，棋盤式鏡像（對花效果）降低重複感
    tile_w = max(48, min(420, int(1800 / tiles_x)))
    tile_h = max(48, min(420, int(tile_w * (stone_h_cm / stone_w_cm))))
    stone = Image.open(stone_photo_path).convert('RGB')
    sc = max(tile_w / stone.width, tile_h / stone.height)
    srs = stone.resize((max(1, round(stone.width * sc)), max(1, round(stone.height * sc))), Image.LANCZOS)
    ox, oy = (srs.width - tile_w) // 2, (srs.height - tile_h) // 2
    tile = srs.crop((ox, oy, ox + tile_w, oy + tile_h))
    mir = ImageOps.mirror(tile)
    tex = Image.new('RGB', (tiles_x * tile_w, tiles_y * tile_h))
    for j in range(tiles_y):
        for i in range(tiles_x):
            t = mir if (i + j) % 2 else tile
            if j % 2:
                t = ImageOps.flip(t)
            tex.paste(t, (i * tile_w, j * tile_h))
    if show_joints and (tiles_x > 1 or tiles_y > 1):
        d = ImageDraw.Draw(tex)
        lw = max(1, tile_w // 120)
        for i in range(1, tiles_x):
            d.line([(i * tile_w, 0), (i * tile_w, tex.height)], fill=(108, 108, 108), width=lw)
        for j in range(1, tiles_y):
            d.line([(0, j * tile_h), (tex.width, j * tile_h)], fill=(108, 108, 108), width=lw)

    # 透視係數：設計圖四角 → 材質四角（PIL PERSPECTIVE 為輸出→輸入映射）
    src = [(0, 0), (tex.width, 0), (tex.width, tex.height), (0, tex.height)]
    A, B = [], []
    for (x, y), (u, v) in zip(quad, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    coeffs = np.linalg.solve(np.array(A, dtype=float), np.array(B, dtype=float))
    warped = tex.transform((W, H), Image.PERSPECTIVE, tuple(coeffs), Image.BICUBIC)

    # 牆面遮罩（羽化接縫）
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).polygon([(round(x), round(y)) for x, y in quad], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.5))

    # 光影轉移：原牆亮度取低頻（模糊）正規化後乘回石材
    lum = np.asarray(design.convert('L').filter(ImageFilter.GaussianBlur(max(3, W // 90))), dtype=np.float32)
    sel = np.asarray(mask, dtype=np.float32) > 128
    mean_lum = float(lum[sel].mean()) if sel.any() else 128.0
    if mean_lum < 1e-3:
        mean_lum = 128.0
    shading = np.clip(lum / mean_lum, 0.55, 1.5)[..., None]
    warped_np = np.clip(np.asarray(warped, dtype=np.float32) * shading, 0, 255)

    alpha = (np.asarray(mask, dtype=np.float32) / 255.0)[..., None]
    out = np.asarray(design, dtype=np.float32) * (1 - alpha) + warped_np * alpha
    return Image.fromarray(np.clip(out, 0, 255).astype('uint8'), 'RGB'), tiles_x, tiles_y


def gemini_edit_image(contents):
    """共用：呼叫 Gemini 圖像模型並萃取回傳影像。回傳 PIL Image 或 None（原因記在 _LAST_SYNTH_ERROR）。"""
    global _LAST_SYNTH_ERROR
    _LAST_SYNTH_ERROR = ''
    try:
        from io import BytesIO
        from PIL import Image
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE']),
        )
        parts = getattr(resp, 'parts', None)
        if not parts:
            parts = []
            for cand in (getattr(resp, 'candidates', None) or []):
                parts += (getattr(getattr(cand, 'content', None), 'parts', None) or [])
        text_chunks = []
        for part in (parts or []):
            inline = getattr(part, 'inline_data', None)
            if inline and getattr(inline, 'data', None):
                return Image.open(BytesIO(inline.data)).convert('RGB')
            if getattr(part, 'text', None):
                text_chunks.append(part.text)
        _LAST_SYNTH_ERROR = 'Gemini 未回傳影像。' + (
            ('模型回應：' + ' '.join(text_chunks)[:160]) if text_chunks else '（無內容）')
        return None
    except Exception as e:
        _LAST_SYNTH_ERROR = f'Gemini {type(e).__name__}: {str(e)[:200]}'
        print(f'[Gemini 圖像錯誤] {_LAST_SYNTH_ERROR}')
        return None


def resolve_ai_prompt(stone, custom_prompt=''):
    """決定 inpainting 要用的 prompt（方案 A：讓 AI 實際「看」石材照片）。
    優先序：使用者自訂 > 已快取的 ai_prompt > LLaVA 視覺描述(看真實照片，並快取) > 通用後備。"""
    if custom_prompt:
        return custom_prompt
    if 'ai_prompt' in stone.keys() and stone['ai_prompt']:
        return stone['ai_prompt']
    # 尚無描述 → 用 LLaVA 看實際石材照片產生精準描述，並快取回資料庫（之後免再呼叫）
    caption = ''
    if stone['photo']:
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], stone['photo'])
        caption = describe_stone_with_vision(photo_path)
    if caption:
        try:
            conn = get_db()
            conn.execute('UPDATE stones SET ai_prompt = ? WHERE id = ?', (caption, stone['id']))
            conn.commit()
            conn.close()
            print(f'[ai_prompt] 已用 LLaVA 視覺描述快取石材 {stone["id"]}：{caption}')
        except Exception as e:
            print(f'[ai_prompt cache 錯誤] {e}')
        return caption
    return generate_ai_prompt(stone['stone_type'], stone['color'] or '', stone['description'] or '')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    # 確保資料庫所在資料夾存在（給 Railway Volume 路徑用）
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    print(f'[init_db] 使用資料庫路徑：{DB_PATH}')
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
            is_vip INTEGER DEFAULT 0,
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

        CREATE TABLE IF NOT EXISTS synthesis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            stone_id INTEGER,
            stone_name TEXT,
            image_file TEXT,
            prompt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS showcase_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stone_id INTEGER,
            stone_name TEXT,
            scene_label TEXT,
            image_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            is_published INTEGER DEFAULT 1,
            pinned INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ai_usage (
            customer_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (customer_id, day)
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

    # 石材視覺特徵欄位（以圖搜圖 v2：HSV 直方圖 + 紋理統計，JSON 字串）
    try:
        conn.execute("ALTER TABLE stones ADD COLUMN features TEXT DEFAULT ''")
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

    # AI Prompt 欄位（用於設計工具的 inpainting prompt）
    try:
        conn.execute("ALTER TABLE stones ADD COLUMN ai_prompt TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass

    # 石材品名欄位（自訂名稱，如「帝諾」「卡拉拉白」；stone_type 為分類，stone_name 為品名）
    try:
        conn.execute("ALTER TABLE stones ADD COLUMN stone_name TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass

    # 會員基本資料擴充欄位（公司名稱、聯絡地址）
    for col in ['company', 'address']:
        try:
            conn.execute(f"ALTER TABLE customers ADD COLUMN {col} TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            pass

    # 測試資料標記（is_test = 1 的石材可由後台一鍵清除）
    try:
        conn.execute("ALTER TABLE stones ADD COLUMN is_test INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    # 多語系內容欄位：石材品名／描述／廠商 的英日文版本（留空則顯示中文原文）
    for col in ['stone_name_en', 'stone_name_ja', 'description_en', 'description_ja',
                'vendor_en', 'vendor_ja']:
        try:
            conn.execute(f"ALTER TABLE stones ADD COLUMN {col} TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            pass

    # 最新消息的英日文版本
    for col in ['title_en', 'title_ja', 'content_en', 'content_ja']:
        try:
            conn.execute(f"ALTER TABLE announcements ADD COLUMN {col} TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            pass

    # 會員身分欄位（is_vip：1 = VIP 不限生圖數量，0 = 一般依每日上限）
    try:
        conn.execute("ALTER TABLE customers ADD COLUMN is_vip INTEGER DEFAULT 0")
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


def normalize_image_to_jpg_path(file_field, max_size=2048):
    """將上傳檔（含 HEIC）統一轉成 JPG 暫存檔，回傳路徑。
    用於送 Replicate API 之前的格式正規化。失敗回傳 None。"""
    if not file_field or not file_field.filename:
        return None
    try:
        from PIL import Image
        import tempfile
        img = Image.open(file_field.stream)
        img.thumbnail((max_size, max_size))  # 大圖縮小，省 API 流量
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        fd, path = tempfile.mkstemp(suffix='.jpg')
        os.close(fd)
        img.save(path, 'JPEG', quality=92, optimize=True)
        return path
    except Exception as e:
        print(f'[normalize_image] 轉檔失敗：{type(e).__name__}: {e}')
        return None


def save_photo(file_field):
    """儲存上傳照片，回傳檔名或 None（含詳細診斷）
    iPhone 的 HEIC 格式會自動轉成 JPG 以確保所有瀏覽器都能顯示"""
    if not file_field:
        print('[save_photo] file_field 為 None（表單未夾帶檔案）')
        return None
    if not file_field.filename:
        print('[save_photo] file_field.filename 為空字串')
        return None
    if not allowed_file(file_field.filename):
        print(f'[save_photo] 副檔名不被允許：{file_field.filename}')
        return None
    try:
        original = file_field.filename
        ext = original.rsplit('.', 1)[1].lower() if '.' in original else 'jpg'
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        # HEIC / HEIF 自動轉成 JPG（瀏覽器普遍不支援 HEIC 直接顯示）
        if ext in ('heic', 'heif'):
            if not HEIC_SUPPORTED:
                print('[save_photo] ✗ HEIC 格式不支援（pillow-heif 未安裝）')
                return None
            from PIL import Image
            img = Image.open(file_field.stream)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            filename = f"{secrets.token_hex(12)}.jpg"
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            img.save(full_path, 'JPEG', quality=90, optimize=True)
            if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                print(f'[save_photo] ✓ HEIC → JPG 轉檔成功：{filename}（{os.path.getsize(full_path)} bytes）')
                return filename
            print(f'[save_photo] ⚠ HEIC 轉檔後檔案不存在或為空')
            return None

        # 一般格式直接存
        filename = f"{secrets.token_hex(12)}.{ext}"
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file_field.save(full_path)
        if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
            print(f'[save_photo] ✓ 儲存成功：{filename}（{os.path.getsize(full_path)} bytes）')
            return filename
        print(f'[save_photo] ⚠ 檔案儲存後不存在或為空：{full_path}')
        return None
    except Exception as e:
        print(f'[save_photo] ✗ 儲存發生例外：{type(e).__name__}: {e}')
        return None


def delete_photo(filename):
    """刪除照片檔案"""
    if filename:
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(path):
            os.remove(path)


def _record_design(customer_id, stone_id, stone_name, filename, prompt):
    """寫入一筆設計歷史，並自動清除超過 HISTORY_LIMIT 的舊圖（連同檔案）。回傳 hist_id。"""
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO synthesis_history (customer_id, stone_id, stone_name, image_file, prompt) '
        'VALUES (?, ?, ?, ?, ?)',
        (customer_id, stone_id, stone_name, filename, prompt)
    )
    hist_id = cur.lastrowid
    conn.commit()
    old_rows = conn.execute(
        'SELECT id, image_file FROM synthesis_history WHERE customer_id = ? '
        'ORDER BY created_at DESC, id DESC LIMIT -1 OFFSET ?',
        (customer_id, HISTORY_LIMIT)
    ).fetchall()
    for row in old_rows:
        delete_photo(row['image_file'])
        conn.execute('DELETE FROM synthesis_history WHERE id = ?', (row['id'],))
    conn.commit()
    conn.close()
    print(f'[history] 已存入會員 {customer_id} 的設計：{filename}（清除 {len(old_rows)} 張舊圖）')
    return hist_id


def save_synthesis_history(customer_id, stone_id, stone_name, result_url, prompt):
    """下載 AI 合成結果到 Volume，寫入歷史紀錄並修剪。回傳 (檔名, hist_id)；失敗回 (None, None)。"""
    import urllib.request
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filename = f'design_{secrets.token_hex(8)}.jpg'
        dest = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        req = urllib.request.Request(result_url, headers={'User-Agent': 'ReStone/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(dest, 'wb') as fh:
            fh.write(data)
        hist_id = _record_design(customer_id, stone_id, stone_name, filename, prompt)
        return filename, hist_id
    except Exception as e:
        print(f'[history] 儲存歷史失敗（不影響合成）：{e}')
        return None, None


# ── AI 設計提案 PDF 生成 ──
_PDF_FONT_NAME = None

def _get_pdf_font():
    """註冊並回傳繁體中文字型名稱。

    優先嵌入專案內的 Noto Sans TC（OFL 授權、TrueType），確保任何閱讀器都能
    正確顯示中文；若字型檔不存在則退回 reportlab 內建 CID 字型 MSung-Light。
    （皆為非中資來源：Noto = Google/OFL；reportlab/CID = US 來源）"""
    global _PDF_FONT_NAME
    if _PDF_FONT_NAME:
        return _PDF_FONT_NAME
    from reportlab.pdfbase import pdfmetrics
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ttf = os.path.join(base_dir, 'fonts', 'NotoSansTC-Regular.ttf')
    try:
        if os.path.exists(ttf):
            from reportlab.pdfbase.ttfonts import TTFont
            pdfmetrics.registerFont(TTFont('NotoSansTC', ttf))
            _PDF_FONT_NAME = 'NotoSansTC'
            return _PDF_FONT_NAME
    except Exception as e:
        print(f'[pdf] 嵌入 TTF 失敗，改用 CID 字型：{e}')
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    pdfmetrics.registerFont(UnicodeCIDFont('MSung-Light'))
    _PDF_FONT_NAME = 'MSung-Light'
    return _PDF_FONT_NAME


def build_proposal_pdf(design, stone, customer_name=''):
    """產生單一設計案的 A4 提案 PDF，回傳 BytesIO。
    design：synthesis_history 列；stone：對應 stones 列（可能為 None，若石材已刪除）。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image as RLImage, Table, TableStyle)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    font = _get_pdf_font()
    BLUE  = colors.HexColor('#2563EB')
    DARK  = colors.HexColor('#0F172A')
    MUTED = colors.HexColor('#64748B')
    LINE  = colors.HexColor('#E2E8F0')
    GREEN = colors.HexColor('#16A34A')
    GREENBG = colors.HexColor('#F0FDF4')

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title='ReStone AI 設計提案',
                            topMargin=16*mm, bottomMargin=14*mm,
                            leftMargin=18*mm, rightMargin=18*mm)
    avail_w = A4[0] - 36*mm

    s_brand = ParagraphStyle('brand', fontName=font, fontSize=15, textColor=BLUE, leading=18)
    s_sub   = ParagraphStyle('sub',   fontName=font, fontSize=8.5, textColor=MUTED, leading=12)
    s_h1    = ParagraphStyle('h1',    fontName=font, fontSize=20, textColor=DARK, leading=24, spaceBefore=2, spaceAfter=2)
    s_sec   = ParagraphStyle('sec',   fontName=font, fontSize=11, textColor=BLUE, leading=15, spaceBefore=4, spaceAfter=4)
    s_body  = ParagraphStyle('body',  fontName=font, fontSize=9.5, textColor=DARK, leading=15)
    s_muted = ParagraphStyle('mut',   fontName=font, fontSize=8.5, textColor=MUTED, leading=13)
    s_cell  = ParagraphStyle('cell',  fontName=font, fontSize=9.5, textColor=DARK, leading=14)
    s_celll = ParagraphStyle('celll', fontName=font, fontSize=9.5, textColor=MUTED, leading=14)
    s_green = ParagraphStyle('grn',   fontName=font, fontSize=9.5, textColor=GREEN, leading=15)

    elems = []
    name = design['stone_name'] or (stone['stone_name'] if stone and 'stone_name' in stone.keys() and stone['stone_name'] else (stone['stone_type'] if stone else '循環石材'))
    created = (design['created_at'] or '')[:16]

    # 頁首
    head_tbl = Table([[Paragraph('◈ ReStone 循環石材服務平台', s_brand),
                       Paragraph(f'AI 設計提案<br/>AI DESIGN PROPOSAL', s_sub)]],
                     colWidths=[avail_w*0.62, avail_w*0.38])
    head_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('LINEBELOW', (0,0), (-1,-1), 1, BLUE),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elems += [head_tbl, Spacer(1, 8)]

    elems += [Paragraph(name, s_h1),
              Paragraph(f'提案編號 #{design["id"]:04d} ｜ 產生日期 {created}'
                        + (f' ｜ 設計師 {customer_name}' if customer_name else ''), s_muted),
              Spacer(1, 10)]

    # 合成設計圖
    img_path = os.path.join(app.config['UPLOAD_FOLDER'], design['image_file'])
    if os.path.exists(img_path):
        try:
            from PIL import Image as PILImage
            with PILImage.open(img_path) as im:
                iw, ih = im.size
            disp_w = avail_w
            disp_h = disp_w * (ih / iw)
            max_h = 120*mm
            if disp_h > max_h:
                disp_h = max_h
                disp_w = disp_h * (iw / ih)
            elems += [RLImage(img_path, width=disp_w, height=disp_h, hAlign='CENTER'),
                      Spacer(1, 4),
                      Paragraph('▲ AI 合成效果圖（套用循環石材於設計空間）', s_muted),
                      Spacer(1, 12)]
        except Exception as e:
            print(f'[pdf] 圖片嵌入失敗：{e}')

    # 石材規格
    elems += [Paragraph('石材規格 ｜ Specifications', s_sec)]
    def spec_row(label, value):
        return [Paragraph(label, s_celll), Paragraph(str(value) if value not in (None, '') else '—', s_cell)]
    if stone:
        dims = '—'
        if stone['width'] and stone['height']:
            t = f" × {stone['thickness']}" if stone['thickness'] else ''
            dims = f"{stone['width']} × {stone['height']}{t} cm"
        rows = [
            spec_row('品名', name),
            spec_row('分類', stone['stone_type']),
            spec_row('尺寸 (寬×高×厚)', dims),
            spec_row('數量', f"{stone['quantity']} {stone['unit'] or '片'}" if stone['quantity'] else '—'),
            spec_row('參考單價', f"NT$ {stone['price']:,.0f}" if stone['price'] else '—'),
            spec_row('供應商', stone['vendor']),
        ]
    else:
        rows = [spec_row('品名', name),
                spec_row('備註', '此石材已自資料庫移除，僅保留設計圖紀錄')]
    spec_tbl = Table(rows, colWidths=[avail_w*0.28, avail_w*0.72])
    spec_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, LINE),
        ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
    ]))
    elems += [spec_tbl, Spacer(1, 12)]

    # 永續貢獻（減碳效益）
    if stone:
        kg = calculate_carbon_saved(stone['stone_type'], stone['width'],
                                    stone['height'], stone['thickness'], stone['quantity'])
        if kg and kg > 0:
            eq = carbon_equivalents(kg)
            elems += [Paragraph('永續貢獻 ｜ Sustainability', s_sec)]
            carbon_tbl = Table([[
                Paragraph(f'減少碳排放<br/><font size=15 color="#16A34A">{format_carbon(kg)}</font> CO2e', s_green),
                Paragraph(f'相當於<br/>{eq["trees"]:.1f} 棵樹一年的吸碳量', s_body),
                Paragraph(f'相當於<br/>少開 {eq["car_km"]:.0f} 公里的汽車碳排', s_body),
            ]], colWidths=[avail_w/3.0]*3)
            carbon_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), GREENBG),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#BBF7D0')),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#DCFCE7')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
            ]))
            elems += [carbon_tbl,
                      Paragraph('＊依體積 × ICE Database v3.0 碳排係數估算；選用循環石材取代開採新料之減碳效益。', s_muted),
                      Spacer(1, 12)]

    # 廠商聯繫
    if stone and stone['vendor']:
        elems += [Paragraph('採購聯繫 ｜ Contact', s_sec),
                  Paragraph(f'供應商：{stone["vendor"]}', s_body),
                  Paragraph('如需報價或洽詢庫存，請透過 ReStone 平台「詢問訂購」功能與供應商聯繫。', s_muted),
                  Spacer(1, 10)]

    # 頁尾
    elems += [Spacer(1, 6),
              Table([['']], colWidths=[avail_w], style=TableStyle([('LINEABOVE',(0,0),(-1,-1),0.5,LINE)])),
              Paragraph('本提案由 ReStone 循環石材服務平台 AI 設計工具自動生成　｜　支持循環經濟，讓石材物盡其用', s_muted)]

    doc.build(elems)
    buf.seek(0)
    return buf


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
            flash(_('請先登入會員帳號'), 'error')
            return redirect(url_for('customer_login'))
        return f(*args, **kwargs)
    return decorated


# ─── AI 生圖每日配額（控制 Gemini 付費成本）───────────────────────
def _today_tpe():
    """台灣時區的今天日期字串（YYYY-MM-DD），供每日配額歸零用。"""
    return datetime.now(_TPE_TZ).strftime('%Y-%m-%d')


def ai_usage_today(customer_id):
    """回傳該會員今日（台灣時區）已生成的付費 AI 圖數量。"""
    conn = get_db()
    row = conn.execute('SELECT count FROM ai_usage WHERE customer_id = ? AND day = ?',
                       (customer_id, _today_tpe())).fetchone()
    conn.close()
    return row['count'] if row else 0


def ai_usage_incr(customer_id):
    """成功生成一張付費 AI 圖後累加當日計數（不存在則建立）。"""
    conn = get_db()
    conn.execute(
        'INSERT INTO ai_usage (customer_id, day, count) VALUES (?, ?, 1) '
        'ON CONFLICT(customer_id, day) DO UPDATE SET count = count + 1',
        (customer_id, _today_tpe()))
    conn.commit()
    conn.close()


def is_vip_customer(customer_id):
    """該會員是否為 VIP（不限生圖數量）。"""
    conn = get_db()
    try:
        row = conn.execute('SELECT is_vip FROM customers WHERE id = ?', (customer_id,)).fetchone()
    except Exception:
        row = None
    conn.close()
    return bool(row and row['is_vip'])


def ai_quota_check():
    """在付費生圖端點開頭呼叫。若已達每日上限，回傳可直接 return 的 (json, status)；否則回傳 None。"""
    from flask import jsonify
    if AI_DAILY_LIMIT <= 0:
        return None  # 0 = 全站不限制
    cid = session.get('customer_id')
    if is_vip_customer(cid):
        return None  # VIP 不限量
    used = ai_usage_today(cid)
    if used >= AI_DAILY_LIMIT:
        return jsonify({
            'error': f'今日 AI 生圖已達上限（每人每日 {AI_DAILY_LIMIT} 張），請明天再試。',
            'quota_exceeded': True, 'used': used, 'limit': AI_DAILY_LIMIT,
        }), 429
    return None


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
                '(stone_type LIKE ? OR stone_name LIKE ? OR vendor LIKE ? OR description LIKE ?)'
            )
            params.extend([f'%{term}%', f'%{term}%', f'%{term}%', f'%{term}%'])
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

    # 平台累積總減碳量（涵蓋所有石材，不論篩選條件）
    all_stones = conn.execute(
        'SELECT stone_type, width, height, thickness, quantity FROM stones'
    ).fetchall()
    total_carbon_kg = sum(
        calculate_carbon_saved(s['stone_type'], s['width'], s['height'], s['thickness'], s['quantity'])
        for s in all_stones
    )

    # 最新消息（僅顯示已發布，置頂優先，取最新 3 則）
    announcements = conn.execute(
        'SELECT * FROM announcements WHERE is_published = 1 '
        'ORDER BY pinned DESC, created_at DESC LIMIT 3'
    ).fetchall()
    conn.close()

    return render_template('index.html', stones=stones, types=types,
                           search=search, selected_type=stone_type, total=total,
                           colors=COLORS, color_map=COLOR_MAP, selected_color=color,
                           total_carbon_kg=total_carbon_kg, announcements=announcements)


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
        flash(_('姓名與 Email 為必填欄位'), 'error')
        conn.close()
        return redirect(url_for('stone_detail', id=id))

    # 詢價時優先存品名（stone.stone_name），無則用分類（stone_type）
    inquiry_stone_name = (stone['stone_name'] if 'stone_name' in stone.keys() and stone['stone_name'] else None) or stone['stone_type']
    conn.execute('''
        INSERT INTO inquiries (stone_id, stone_name, customer_name, customer_email,
                               customer_phone, quantity, message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (id, inquiry_stone_name, name, email, phone, qty, message))
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

    flash(_('詢問已送出！廠商將盡快與您聯繫。'), 'success')
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
            flash(_('姓名、Email 及密碼為必填'), 'error')
        elif password != confirm:
            flash(_('兩次密碼不一致'), 'error')
        elif len(password) < 6:
            flash(_('密碼至少需要 6 個字元'), 'error')
        else:
            conn = get_db()
            existing = conn.execute('SELECT id FROM customers WHERE email = ?', (email,)).fetchone()
            if existing:
                flash(_('此 Email 已被註冊'), 'error')
                conn.close()
            else:
                conn.execute('''INSERT INTO customers (name, email, phone, password)
                                VALUES (?, ?, ?, ?)''',
                             (name, email, phone,
                              generate_password_hash(password, method='pbkdf2:sha256')))
                conn.commit()
                customer = conn.execute('SELECT * FROM customers WHERE email = ?', (email,)).fetchone()
                conn.close()
                # 角色互斥：註冊自動登入會員時清除任何管理員身分
                session.pop('admin', None)
                session.pop('admin_name', None)
                session['customer_id']    = customer['id']
                session['customer_name']  = customer['name']
                session['customer_email'] = customer['email']
                flash(_('註冊成功！歡迎加入 ReStone！'), 'success')
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
            # 角色互斥：登入會員即清除任何管理員身分
            session.pop('admin', None)
            session.pop('admin_name', None)
            session['customer_id']    = customer['id']
            session['customer_name']  = customer['name']
            session['customer_email'] = customer['email']
            flash(f'歡迎回來，{customer["name"]}！', 'success')
            return redirect(url_for('index'))
        else:
            flash(_('Email 或密碼錯誤'), 'error')
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
    customer = conn.execute('SELECT * FROM customers WHERE id = ?',
                            (session['customer_id'],)).fetchone()
    inquiries = conn.execute('''
        SELECT i.*, s.stone_type FROM inquiries i
        LEFT JOIN stones s ON i.stone_id = s.id
        WHERE i.customer_email = ?
        ORDER BY i.created_at DESC
    ''', (session['customer_email'],)).fetchall()
    recent_designs = conn.execute(
        'SELECT * FROM synthesis_history WHERE customer_id = ? ORDER BY created_at DESC, id DESC LIMIT 6',
        (session['customer_id'],)
    ).fetchall()
    conn.close()
    return render_template('customer_dashboard.html', customer=customer,
                           inquiries=inquiries, recent_designs=recent_designs)


@app.route('/my-account/update', methods=['POST'])
@customer_required
def update_my_account():
    name    = request.form.get('name', '').strip()
    phone   = request.form.get('phone', '').strip()
    company = request.form.get('company', '').strip()
    address = request.form.get('address', '').strip()
    if not name:
        flash(_('姓名為必填欄位'), 'error')
        return redirect(url_for('my_account'))
    conn = get_db()
    conn.execute(
        'UPDATE customers SET name = ?, phone = ?, company = ?, address = ? WHERE id = ?',
        (name, phone, company, address, session['customer_id'])
    )
    conn.commit()
    conn.close()
    session['customer_name'] = name
    flash(_('基本資料已更新'), 'success')
    return redirect(url_for('my_account'))


@app.route('/my-designs')
@customer_required
def my_designs():
    conn = get_db()
    designs = conn.execute(
        'SELECT * FROM synthesis_history WHERE customer_id = ? ORDER BY created_at DESC, id DESC',
        (session['customer_id'],)
    ).fetchall()
    conn.close()
    return render_template('my_designs.html', designs=designs, history_limit=HISTORY_LIMIT)


@app.route('/my-designs/<int:id>/delete', methods=['POST'])
@customer_required
def delete_my_design(id):
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM synthesis_history WHERE id = ? AND customer_id = ?',
        (id, session['customer_id'])
    ).fetchone()
    if row:
        delete_photo(row['image_file'])
        conn.execute('DELETE FROM synthesis_history WHERE id = ?', (id,))
        conn.commit()
        flash(_('已刪除該張設計'), 'success')
    conn.close()
    return redirect(url_for('my_designs'))


@app.route('/my-designs/<int:id>/proposal.pdf')
@customer_required
def design_proposal_pdf(id):
    conn = get_db()
    design = conn.execute(
        'SELECT * FROM synthesis_history WHERE id = ? AND customer_id = ?',
        (id, session['customer_id'])
    ).fetchone()
    if not design:
        conn.close()
        flash(_('找不到該設計'), 'error')
        return redirect(url_for('my_designs'))
    stone = None
    if design['stone_id']:
        stone = conn.execute('SELECT * FROM stones WHERE id = ?', (design['stone_id'],)).fetchone()
    conn.close()
    try:
        pdf = build_proposal_pdf(design, stone, session.get('customer_name', ''))
    except Exception as e:
        import traceback; traceback.print_exc()
        flash(f'PDF 生成失敗：{str(e)[:120]}', 'error')
        return redirect(url_for('my_designs'))
    safe_name = (design['stone_name'] or 'design').replace('/', '_').replace(' ', '_')
    return send_file(pdf, as_attachment=True,
                     download_name=f'ReStone_提案_{safe_name}_{id:04d}.pdf',
                     mimetype='application/pdf')


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
            # 角色互斥：登入管理員即清除任何會員身分
            session.pop('customer_id', None)
            session.pop('customer_name', None)
            session.pop('customer_email', None)
            session['admin'] = True
            session['admin_name'] = admin['username']
            return redirect(url_for('admin_dashboard'))
        else:
            flash(_('帳號或密碼錯誤，請重試'), 'error')
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
    # 平台累積減碳量
    total_carbon_kg = sum(
        calculate_carbon_saved(s['stone_type'], s['width'], s['height'], s['thickness'], s['quantity'])
        for s in stones
    )
    test_count = sum(1 for s in stones if s['is_test'])
    return render_template('admin.html', stones=stones, total=total,
                           new_inquiries=new_inquiries,
                           total_carbon_kg=total_carbon_kg,
                           test_count=test_count)


# ─── 測試資料（20 筆循環石材，照片本機生成，不呼叫任何 AI）──────────
@app.route('/admin/test-data/seed', methods=['POST'])
@admin_required
def admin_seed_test_data():
    import seed_data
    conn = get_db()
    try:
        replaced = seed_data.clear(conn, delete_photo)      # 重複按下時先替換舊的測試資料
        created = seed_data.seed(conn, app.config['UPLOAD_FOLDER'],
                                 analyze_image_full, generate_ai_prompt)
    except Exception as e:
        import traceback; traceback.print_exc()
        conn.close()
        flash(_('產生測試資料失敗') + f'：{str(e)[:120]}', 'error')
        return redirect(url_for('admin_dashboard'))
    conn.close()
    msg = _('已產生 {n} 筆測試資料').format(n=created)
    if replaced:
        msg += _('（已替換先前的 {n} 筆）').format(n=replaced)
    flash(msg, 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/test-data/clear', methods=['POST'])
@admin_required
def admin_clear_test_data():
    import seed_data
    conn = get_db()
    n = seed_data.clear(conn, delete_photo)
    conn.close()
    flash(_('已清除 {n} 筆測試資料（含照片）').format(n=n), 'success')
    return redirect(url_for('admin_dashboard'))


# ─── 內容多語翻譯（AI 產草稿，後台可再編輯）─────────────────────
@app.route('/admin/stone/<int:id>/translate', methods=['POST'])
@admin_required
def admin_translate_stone(id):
    """用 Gemini 把石材的品名／描述／廠商翻成英日文，存進資料庫供前台顯示。"""
    from flask import jsonify
    if not GEMINI_API_KEY:
        return jsonify({'error': '尚未設定 GEMINI_API_KEY，無法自動翻譯'}), 503
    conn = get_db()
    s = conn.execute('SELECT * FROM stones WHERE id = ?', (id,)).fetchone()
    if not s:
        conn.close()
        return jsonify({'error': '找不到該石材'}), 404
    fields = {}
    for f in ('stone_name', 'description', 'vendor'):
        try:
            if s[f]:
                fields[f] = s[f]
        except (KeyError, IndexError):
            pass
    if not fields:
        conn.close()
        return jsonify({'error': '此石材沒有可翻譯的文字內容'}), 400

    res = translate_fields_with_gemini(fields)
    if res is None:
        conn.close()
        return jsonify({'error': '翻譯失敗，請稍後再試'}), 500

    sets, vals = [], []
    for lang in ('en', 'ja'):
        for f, v in res[lang].items():
            if v:
                sets.append(f'{f}_{lang}=?')
                vals.append(v)
    if sets:
        vals.append(id)
        conn.execute(f'UPDATE stones SET {", ".join(sets)} WHERE id=?', vals)
        conn.commit()
    conn.close()
    return jsonify({'success': True, 'en': res['en'], 'ja': res['ja']})


@app.route('/admin/news/<int:id>/translate', methods=['POST'])
@admin_required
def admin_translate_news(id):
    """用 Gemini 把公告標題與內容翻成英日文。"""
    from flask import jsonify
    if not GEMINI_API_KEY:
        return jsonify({'error': '尚未設定 GEMINI_API_KEY，無法自動翻譯'}), 503
    conn = get_db()
    a = conn.execute('SELECT * FROM announcements WHERE id = ?', (id,)).fetchone()
    if not a:
        conn.close()
        return jsonify({'error': '找不到該公告'}), 404
    fields = {k: a[k] for k in ('title', 'content') if a[k]}
    res = translate_fields_with_gemini(fields)
    if res is None:
        conn.close()
        return jsonify({'error': '翻譯失敗，請稍後再試'}), 500
    sets, vals = [], []
    for lang in ('en', 'ja'):
        for f, v in res[lang].items():
            if v:
                sets.append(f'{f}_{lang}=?')
                vals.append(v)
    if sets:
        vals.append(id)
        conn.execute(f'UPDATE announcements SET {", ".join(sets)} WHERE id=?', vals)
        conn.commit()
    conn.close()
    return jsonify({'success': True, 'en': res['en'], 'ja': res['ja']})


# ─── 最新消息管理 ───────────────────────────────────────────────
@app.route('/admin/news')
@admin_required
def admin_news():
    conn = get_db()
    items = conn.execute(
        'SELECT * FROM announcements ORDER BY pinned DESC, created_at DESC'
    ).fetchall()
    editing = None
    edit_id = request.args.get('edit', type=int)
    if edit_id:
        editing = conn.execute(
            'SELECT * FROM announcements WHERE id = ?', (edit_id,)).fetchone()
    conn.close()
    return render_template('admin_news.html', items=items, editing=editing)


@app.route('/admin/news/save', methods=['POST'])
@admin_required
def admin_news_save():
    nid          = request.form.get('id', type=int)
    title        = request.form.get('title', '').strip()
    content      = request.form.get('content', '').strip()
    is_published = 1 if request.form.get('is_published') else 0
    pinned       = 1 if request.form.get('pinned') else 0
    if not title:
        flash(_('標題為必填'), 'error')
        return redirect(url_for('admin_news', edit=nid) if nid else url_for('admin_news'))
    conn = get_db()
    if nid:
        conn.execute(
            'UPDATE announcements SET title=?, content=?, is_published=?, pinned=?, '
            'title_en=?, title_ja=?, content_en=?, content_ja=?, '
            'updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (title, content, is_published, pinned,
             *[request.form.get(c, '').strip() for c in
               ('title_en','title_ja','content_en','content_ja')], nid))
        flash(_('公告已更新'), 'success')
    else:
        conn.execute(
            'INSERT INTO announcements (title, content, is_published, pinned, '
            'title_en, title_ja, content_en, content_ja) VALUES (?,?,?,?,?,?,?,?)',
            (title, content, is_published, pinned,
             *[request.form.get(c, '').strip() for c in
               ('title_en','title_ja','content_en','content_ja')]))
        flash(_('公告已新增'), 'success')
    conn.commit()
    conn.close()
    return redirect(url_for('admin_news'))


@app.route('/admin/news/<int:id>/delete', methods=['POST'])
@admin_required
def admin_news_delete(id):
    conn = get_db()
    conn.execute('DELETE FROM announcements WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash(_('公告已刪除'), 'success')
    return redirect(url_for('admin_news'))


@app.route('/admin/news/<int:id>/toggle', methods=['POST'])
@admin_required
def admin_news_toggle(id):
    conn = get_db()
    conn.execute('UPDATE announcements SET is_published = 1 - is_published WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_news'))


@app.route('/admin/news/<int:id>/pin', methods=['POST'])
@admin_required
def admin_news_pin(id):
    conn = get_db()
    conn.execute('UPDATE announcements SET pinned = 1 - pinned WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_news'))


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
    flash(_('詢問狀態已更新'), 'success')
    return redirect(url_for('admin_inquiries'))


@app.route('/admin/add', methods=['GET', 'POST'])
@admin_required
def add_stone():
    if request.method == 'POST':
        stone_type = request.form.get('stone_type', '').strip()
        stone_name = request.form.get('stone_name', '').strip()
        if not stone_type:
            flash(_('石材種類為必填欄位'), 'error')
            return render_template('stone_form.html', stone=None, title='新增石材', colors=COLORS, vendors=VENDORS)

        width       = request.form.get('width') or None
        height      = request.form.get('height') or None
        thickness   = request.form.get('thickness') or None
        quantity    = request.form.get('quantity') or None
        unit        = request.form.get('unit', '片')
        price       = request.form.get('price') or None
        vendor      = request.form.get('vendor', '').strip()
        description = request.form.get('description', '').strip()
        color       = request.form.get('color', '')

        # 紀錄表單收到的檔案清單（Railway log 用，協助排錯）
        print(f'[add_stone] request.files keys: {list(request.files.keys())}')
        for key in ['photo', 'photo2', 'photo3']:
            f = request.files.get(key)
            if f:
                print(f'[add_stone] {key}: filename="{f.filename}", content_type={f.content_type}')

        photo  = save_photo(request.files.get('photo'))
        photo2 = save_photo(request.files.get('photo2'))
        photo3 = save_photo(request.files.get('photo3'))

        # 主照片上傳失敗時，明確告知管理員
        main_photo_attempted = bool(request.files.get('photo') and request.files.get('photo').filename)
        if main_photo_attempted and not photo:
            flash(_('⚠ 主照片上傳失敗，請檢查檔案格式（PNG/JPG/HEIC/GIF/WebP）或檔案大小（≤32MB）'), 'error')

        # 主照片 AI 分析：自動偵測顏色 + 計算雜湊 + 視覺特徵（以圖搜圖用）
        image_hash, dominant_rgb, features = '', '', ''
        if photo:
            auto_color, image_hash, dominant_rgb, features = analyze_image_full(
                os.path.join(app.config['UPLOAD_FOLDER'], photo))
            if not color and auto_color:
                color = auto_color  # 未選顏色則套用自動偵測

        # AI Prompt：優先使用管理員填寫；否則用視覺 AI 看照片；最後退回模板
        ai_prompt = request.form.get('ai_prompt', '').strip()
        if not ai_prompt and photo:
            ai_prompt = describe_stone_with_vision(
                os.path.join(app.config['UPLOAD_FOLDER'], photo))
        if not ai_prompt:
            ai_prompt = generate_ai_prompt(stone_type, color, description)

        conn = get_db()
        conn.execute('''
            INSERT INTO stones (stone_type, stone_name, photo, photo2, photo3,
                                width, height, thickness, quantity, unit, price, vendor, description, color,
                                image_hash, dominant_rgb, features, ai_prompt,
                                stone_name_en, stone_name_ja, description_en, description_ja,
                                vendor_en, vendor_ja)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (stone_type, stone_name, photo, photo2, photo3,
              width, height, thickness, quantity, unit, price, vendor, description, color,
              image_hash, dominant_rgb, features, ai_prompt,
              *[request.form.get(c, '').strip() for c in
                ('stone_name_en','stone_name_ja','description_en','description_ja',
                 'vendor_en','vendor_ja')]))
        conn.commit()
        conn.close()

        # 顯示名稱：優先用品名，否則用分類
        display_name = stone_name or stone_type
        msg = f'「{display_name}」已成功新增！'
        if photo and not request.form.get('color') and color:
            color_label = COLOR_MAP.get(color, ('', color, '', ''))[1]
            msg += f' 已自動偵測顏色為「{color_label}」'
        flash(msg, 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('stone_form.html', stone=None, title='新增石材', colors=COLORS, vendors=VENDORS)


@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_stone(id):
    conn = get_db()
    stone = conn.execute('SELECT * FROM stones WHERE id = ?', (id,)).fetchone()

    if not stone:
        conn.close()
        flash(_('找不到該石材'), 'error')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        stone_type  = request.form.get('stone_type', '').strip()
        stone_name  = request.form.get('stone_name', '').strip()
        width       = request.form.get('width') or None
        height      = request.form.get('height') or None
        thickness   = request.form.get('thickness') or None
        quantity    = request.form.get('quantity') or None
        unit        = request.form.get('unit', '片')
        price       = request.form.get('price') or None
        vendor      = request.form.get('vendor', '').strip()
        description = request.form.get('description', '').strip()
        color       = request.form.get('color', '')

        # 紀錄表單收到的檔案清單（Railway log 用）
        print(f'[edit_stone] request.files keys: {list(request.files.keys())}')

        # 處理三張照片（有新上傳才替換）
        photos = []
        main_photo_changed = False
        failed_uploads = []
        for field, old_key in [('photo', 'photo'), ('photo2', 'photo2'), ('photo3', 'photo3')]:
            new_file = request.files.get(field)
            new_photo = save_photo(new_file)
            if new_photo:
                delete_photo(stone[old_key])
                photos.append(new_photo)
                if field == 'photo':
                    main_photo_changed = True
            else:
                # 使用者有選檔案但儲存失敗 → 記錄下來警示
                if new_file and new_file.filename:
                    failed_uploads.append(field)
                photos.append(stone[old_key])

        if failed_uploads:
            flash(f'⚠ 以下照片上傳失敗（已保留原檔案）：{", ".join(failed_uploads)}', 'error')

        # 主照片若有變更或缺少分析資料，則重新分析
        image_hash = stone['image_hash'] if 'image_hash' in stone.keys() else ''
        dominant_rgb = stone['dominant_rgb'] if 'dominant_rgb' in stone.keys() else ''
        features = stone['features'] if 'features' in stone.keys() else ''
        if photos[0] and (main_photo_changed or not image_hash or not features):
            auto_color, image_hash, dominant_rgb, features = analyze_image_full(
                os.path.join(app.config['UPLOAD_FOLDER'], photos[0]))
            if not color and auto_color:
                color = auto_color

        # AI Prompt：優先使用管理員填寫；主照片有變更則用視覺 AI 重新分析；最後退回模板
        ai_prompt = request.form.get('ai_prompt', '').strip()
        if not ai_prompt and photos[0] and main_photo_changed:
            ai_prompt = describe_stone_with_vision(
                os.path.join(app.config['UPLOAD_FOLDER'], photos[0]))
        if not ai_prompt:
            # 主照片沒換 → 沿用原本的；都沒有就退回模板
            existing = stone['ai_prompt'] if 'ai_prompt' in stone.keys() else ''
            ai_prompt = existing or generate_ai_prompt(stone_type, color, description)

        conn.execute('''
            UPDATE stones
            SET stone_type=?, stone_name=?, photo=?, photo2=?, photo3=?,
                width=?, height=?, thickness=?,
                quantity=?, unit=?, price=?, vendor=?, description=?, color=?,
                image_hash=?, dominant_rgb=?, features=?, ai_prompt=?,
                stone_name_en=?, stone_name_ja=?, description_en=?, description_ja=?,
                vendor_en=?, vendor_ja=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (stone_type, stone_name, photos[0], photos[1], photos[2],
              width, height, thickness, quantity, unit, price, vendor, description, color,
              image_hash, dominant_rgb, features, ai_prompt,
              *[request.form.get(c, '').strip() for c in
                ('stone_name_en','stone_name_ja','description_en','description_ja',
                 'vendor_en','vendor_ja')],
              id))
        conn.commit()
        conn.close()

        display_name = stone_name or stone_type
        flash(f'「{display_name}」資料已更新！', 'success')
        return redirect(url_for('admin_dashboard'))

    conn.close()
    return render_template('stone_form.html', stone=stone, title='編輯石材', colors=COLORS, vendors=VENDORS)


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
        flash(_('石材已成功刪除'), 'success')
    else:
        flash(_('找不到該石材'), 'error')

    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/customers')
@admin_required
def admin_customers():
    conn = get_db()
    customers = conn.execute('SELECT * FROM customers ORDER BY created_at DESC').fetchall()
    # 今日各會員生圖用量（台灣時區），供後台顯示
    usage_rows = conn.execute('SELECT customer_id, count FROM ai_usage WHERE day = ?',
                              (_today_tpe(),)).fetchall()
    conn.close()
    usage_today = {r['customer_id']: r['count'] for r in usage_rows}
    return render_template('admin_customers.html', customers=customers,
                           ai_daily_limit=AI_DAILY_LIMIT, usage_today=usage_today)


@app.route('/admin/customers/<int:id>/vip', methods=['POST'])
@admin_required
def admin_customer_vip(id):
    conn = get_db()
    conn.execute('UPDATE customers SET is_vip = 1 - COALESCE(is_vip, 0) WHERE id = ?', (id,))
    conn.commit()
    row = conn.execute('SELECT name, is_vip FROM customers WHERE id = ?', (id,)).fetchone()
    conn.close()
    if row:
        flash(f'已將「{row["name"]}」設為{"VIP 會員（不限生圖數量）" if row["is_vip"] else "一般會員"}', 'success')
    return redirect(url_for('admin_customers'))


# ─── AI 圖片功能：以圖搜圖 ────────────────────────────────────

@app.route('/search/by-image', methods=['GET', 'POST'])
def search_by_image():
    if request.method == 'POST':
        ref_file = request.files.get('reference')
        if not ref_file or not ref_file.filename or not allowed_file(ref_file.filename):
            flash(_('請上傳有效的圖片（JPG／PNG／GIF／WEBP）'), 'error')
            return redirect(url_for('search_by_image'))

        # 讀取參考圖、分析、轉成 base64 顯示（不寫入磁碟）
        # 統一用 Pillow 解碼後再轉成 JPG bytes，確保 HEIC 也能正常顯示
        import base64
        from io import BytesIO
        try:
            from PIL import Image
            ref_file.stream.seek(0)
            img = Image.open(ref_file.stream)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            buf = BytesIO()
            img.save(buf, 'JPEG', quality=88)
            ref_bytes = buf.getvalue()
        except Exception as e:
            print(f'[search_by_image] 圖片解碼失敗：{e}')
            flash(_('無法讀取此圖片，請改用 JPG 或 PNG 格式'), 'error')
            return redirect(url_for('search_by_image'))

        # 圈選範圍（0-1 比例）：只比對框內的石材區域，避免背景干擾
        def _frac(name):
            try:
                return max(0.0, min(1.0, float(request.form.get(name, ''))))
            except (TypeError, ValueError):
                return None
        cl, ct, cr, cb = _frac('crop_l'), _frac('crop_t'), _frac('crop_r'), _frac('crop_b')
        box = None
        if None not in (cl, ct, cr, cb) and cr - cl > 0.02 and cb - ct > 0.02:
            box = (cl, ct, cr, cb)

        # 預覽圖：有圈選就顯示裁切後的區域，讓使用者看到實際比對的範圍
        if box:
            W, H = img.size
            crop_img = img.crop((int(cl * W), int(ct * H), int(cr * W), int(cb * H)))
            cbuf = BytesIO()
            crop_img.save(cbuf, 'JPEG', quality=88)
            preview_bytes = cbuf.getvalue()
        else:
            preview_bytes = ref_bytes
        ref_data_url = 'data:image/jpeg;base64,' + base64.b64encode(preview_bytes).decode()

        ref_color, ref_hash, ref_rgb, ref_feat_json = analyze_image_full(BytesIO(ref_bytes), box=box)
        ref_feat = features_from_json(ref_feat_json)

        if not ref_hash:
            flash(_('無法分析此圖片，請改用其他圖'), 'error')
            return redirect(url_for('search_by_image'))

        # 比對所有有索引的石材
        conn = get_db()
        stones = conn.execute('SELECT * FROM stones').fetchall()
        conn.close()

        results = []
        stale = 0          # 尚未建立新版特徵、只能用舊方式比對的筆數
        for s in stones:
            sh = s['image_hash'] if 'image_hash' in s.keys() else ''
            sr = s['dominant_rgb'] if 'dominant_rgb' in s.keys() else ''
            sf = features_from_json(s['features'] if 'features' in s.keys() else '')
            if not sh and not sf:
                continue
            if ref_feat and sf:
                # 主要：色彩直方圖 + 紋理特徵（對角度/光線穩健）
                # 輔助：pHash 佔少量權重，讓「完全同一張圖」仍能拿到滿分
                d = feature_distance(ref_feat, sf) * 0.85 + (hash_distance(ref_hash, sh) / 64.0) * 0.15
            else:
                # 後備：該石材尚未重新索引，沿用舊的 pHash + 主色比對
                stale += 1
                d = (hash_distance(ref_hash, sh) / 64.0) * 0.5 + \
                    ((rgb_distance(ref_rgb, sr) if sr else 220) / 441.0) * 0.5
            results.append((s, round(max(0.0, 1.0 - d) * 100, 1)))

        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:12]

        return render_template('image_search.html',
                               results=results,
                               reference_url=ref_data_url,
                               cropped=bool(box),
                               stale_count=stale,
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
        auto_color, phash, rgb, feats = analyze_image_full(path)
        if not phash:
            continue
        new_color = s['color'] if s['color'] else auto_color
        if not s['color'] and auto_color:
            color_filled += 1
        conn.execute('UPDATE stones SET image_hash=?, dominant_rgb=?, features=?, color=? WHERE id=?',
                     (phash, rgb, feats, new_color, s['id']))
        updated += 1
    conn.commit()
    conn.close()
    flash(f'✅ 已重新索引 {updated} 筆石材（含新版視覺特徵），自動補上 {color_filled} 筆顏色標籤', 'success')
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
            flash(_('目前密碼不正確'), 'error')
        elif new_pw != confirm:
            flash(_('新密碼與確認密碼不符'), 'error')
        elif len(new_pw) < 6:
            flash(_('新密碼至少需要 6 個字元'), 'error')
        else:
            conn.execute('UPDATE admin_users SET password = ? WHERE username = ?',
                         (generate_password_hash(new_pw, method='pbkdf2:sha256'),
                          session['admin_name']))
            conn.commit()
            flash(_('密碼已成功更新！'), 'success')
        conn.close()

    return render_template('change_password.html')


# ─── AI 設計工具：套用石材到設計圖（僅限會員）────────────────────────
@app.route('/studio')
def studio():
    """設計工具功能選擇頁（Hub）：列出材質模擬、草圖渲染等工具，公開可瀏覽。"""
    return render_template('studio.html')


@app.route('/wall')
@customer_required
def wall_tool():
    """牆面模擬頁：點選牆面四角 + 選石材 + 輸入尺寸 → 透視/比例正確的即時模擬"""
    conn = get_db()
    stones = conn.execute(
        "SELECT id, stone_type, stone_name, color, photo, width, height, quantity, unit "
        "FROM stones WHERE photo IS NOT NULL AND photo != '' ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template('wall.html', stones=stones,
                           gemini_enabled=bool(GEMINI_API_KEY))


@app.route('/api/simulate-wall', methods=['POST'])
def api_simulate_wall():
    """牆面模擬：本地幾何運算（透視+比例+光影），即時、免 AI 費用（僅限會員）"""
    from flask import jsonify
    import json as _json
    if not session.get('customer_id'):
        return jsonify({'error': _('請先登入會員才能使用牆面模擬')}), 401

    photo    = request.files.get('photo')
    stone_id = request.form.get('stone_id', type=int)
    wall_w   = request.form.get('wall_w', type=float)
    wall_h   = request.form.get('wall_h', type=float)
    joints   = request.form.get('joints', '1') == '1'
    try:
        corners = _json.loads(request.form.get('corners', ''))
        assert isinstance(corners, list) and len(corners) == 4
        corners = [(float(p[0]), float(p[1])) for p in corners]
        assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in corners)
    except Exception:
        return jsonify({'error': _('牆面四角座標無效，請重新點選')}), 400
    if not photo or not stone_id:
        return jsonify({'error': _('缺少必要欄位（空間照片、石材）')}), 400
    if not wall_w or not wall_h or not (50 <= wall_w <= 2000) or not (50 <= wall_h <= 1000):
        return jsonify({'error': _('請輸入合理的牆面尺寸（寬 50–2000cm、高 50–1000cm）')}), 400

    conn = get_db()
    stone = conn.execute('SELECT * FROM stones WHERE id = ?', (stone_id,)).fetchone()
    conn.close()
    if not stone or not stone['photo']:
        return jsonify({'error': _('找不到石材或石材沒有照片')}), 404
    stone_photo_path = os.path.join(app.config['UPLOAD_FOLDER'], stone['photo'])
    if not os.path.exists(stone_photo_path):
        return jsonify({'error': _('石材照片檔案不存在')}), 400

    # 石材尺寸（未填則以 60×60cm 估算）
    sw, sh = stone['width'] or 0, stone['height'] or 0
    estimated = not (sw and sh)
    if estimated:
        sw, sh = 60.0, 60.0

    design_path = None
    try:
        design_path = normalize_image_to_jpg_path(photo, max_size=1600)
        if not design_path:
            return jsonify({'error': _('照片格式無法解析（支援 JPG / PNG / HEIC / WebP）')}), 400
        result_img, tiles_x, tiles_y = simulate_wall_perspective(
            design_path, corners, stone_photo_path, sw, sh, wall_w, wall_h, joints)

        display_name = (stone['stone_name'] if 'stone_name' in stone.keys() and stone['stone_name']
                        else stone['stone_type'])
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filename = f'design_{secrets.token_hex(8)}.jpg'
        result_img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'JPEG', quality=92)
        label = f'牆面模擬（{wall_w/100:.1f}×{wall_h/100:.1f}m・{tiles_x}×{tiles_y} 片）'
        design_id = _record_design(session['customer_id'], stone_id, display_name, filename, label)
        local_url = url_for('static', filename=f'uploads/{filename}')

        # 加值：用片數 → 庫存檢查 + 減碳效益
        tiles_total = tiles_x * tiles_y
        stock_qty = stone['quantity'] or 0
        carbon_kg = calculate_carbon_saved(stone['stone_type'], sw, sh,
                                           stone['thickness'] or 2.0, tiles_total)
        eq = carbon_equivalents(carbon_kg)
        return jsonify({
            'success': True, 'result_url': local_url, 'local_url': local_url,
            'saved': True, 'design_id': design_id, 'stone_name': display_name,
            'stats': {
                'tile_size': f'{sw:g}×{sh:g}cm' + ('（未填尺寸，估算值）' if estimated else ''),
                'tiles_x': tiles_x, 'tiles_y': tiles_y, 'tiles_total': tiles_total,
                'stock_qty': stock_qty,
                'stock_ok': bool(stock_qty and stock_qty >= tiles_total),
                'carbon': format_carbon(carbon_kg) if carbon_kg > 0 else '',
                'trees': round(eq['trees'], 1) if carbon_kg > 0 else 0,
            },
        })
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': f'牆面模擬失敗：{str(e)[:200]}'}), 500
    finally:
        if design_path and os.path.exists(design_path):
            try: os.unlink(design_path)
            except Exception: pass


@app.route('/api/enhance-wall', methods=['POST'])
def api_enhance_wall():
    """牆面模擬的 AI 擬真強化：把幾何貼合結果交給 Gemini 修飾光影/遮擋（僅限會員）"""
    from flask import jsonify
    if not session.get('customer_id'):
        return jsonify({'error': _('請先登入會員')}), 401
    if not GEMINI_API_KEY:
        return jsonify({'error': _('AI 擬真強化需要 Gemini（請設定 GEMINI_API_KEY）')}), 503
    _q = ai_quota_check()
    if _q:
        return _q
    design_id = request.form.get('design_id', type=int)
    if not design_id:
        return jsonify({'error': _('缺少 design_id')}), 400
    conn = get_db()
    row = conn.execute('SELECT * FROM synthesis_history WHERE id = ? AND customer_id = ?',
                       (design_id, session['customer_id'])).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': _('找不到該設計')}), 404
    comp_path = os.path.join(app.config['UPLOAD_FOLDER'], row['image_file'])
    if not os.path.exists(comp_path):
        return jsonify({'error': _('設計圖檔不存在')}), 400

    original = request.files.get('original')
    orig_path = None
    try:
        from google.genai import types
        def part_of(path):
            with open(path, 'rb') as f:
                data = f.read()
            mime = 'image/png' if path.lower().endswith('.png') else 'image/jpeg'
            return types.Part.from_bytes(data=data, mime_type=mime)

        has_orig = False
        if original and original.filename:
            orig_path = normalize_image_to_jpg_path(original, max_size=1600)
            has_orig = bool(orig_path)
        prompt = (
            'Image 1 is an interior photo where one wall has been digitally clad with stone panels '
            '(the tile layout, scale and perspective are already CORRECT). '
            + ('Image 2 is the original room photo before cladding. ' if has_orig else '') +
            'Refine Image 1 into a fully photorealistic photograph: blend the stone wall\'s lighting, '
            'shadows and reflections naturally with the room, keep the stone colour, veining, panel size, '
            'joints and perspective EXACTLY as shown'
            + (', and restore any foreground objects (furniture, plants, fixtures) from Image 2 that '
               'should appear in front of the wall' if has_orig else '') +
            '. Do not alter anything else in the room. Return only the edited image.'
        )
        contents = [prompt, part_of(comp_path)] + ([part_of(orig_path)] if has_orig else [])
        result_img = gemini_edit_image(contents)
        if result_img is None:
            return jsonify({'error': f'AI 強化失敗：{_LAST_SYNTH_ERROR or "未回傳影像"}'}), 500

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filename = f'design_{secrets.token_hex(8)}.jpg'
        result_img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'JPEG', quality=92)
        new_id = _record_design(session['customer_id'], row['stone_id'], row['stone_name'],
                                filename, (row['prompt'] or '牆面模擬') + '・AI 擬真強化')
        ai_usage_incr(session['customer_id'])
        local_url = url_for('static', filename=f'uploads/{filename}')
        return jsonify({'success': True, 'result_url': local_url, 'local_url': local_url,
                        'design_id': new_id})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': f'AI 強化失敗：{str(e)[:200]}'}), 500
    finally:
        if orig_path and os.path.exists(orig_path):
            try: os.unlink(orig_path)
            except Exception: pass


@app.route('/design-tool')
@customer_required
def design_tool():
    """設計工具頁：上傳設計圖 + 圈選區域 + 選石材 → AI 合成"""
    conn = get_db()
    stones = conn.execute(
        'SELECT id, stone_type, stone_name, color, photo, ai_prompt FROM stones ORDER BY id DESC'
    ).fetchall()
    conn.close()
    selected_id = request.args.get('stone_id', type=int)
    return render_template('design_tool.html',
                           stones=stones,
                           selected_id=selected_id,
                           color_map=COLOR_MAP,
                           replicate_enabled=bool(REPLICATE_API_TOKEN))


@app.route('/sketch')
@customer_required
def sketch_tool():
    """草圖渲染頁：上傳草圖 + 選石材 + 描述 → Gemini 生成產品渲染圖"""
    conn = get_db()
    stones = conn.execute(
        'SELECT id, stone_type, stone_name, color, photo FROM stones ORDER BY id DESC'
    ).fetchall()
    conn.close()
    return render_template('sketch.html', stones=stones,
                           gemini_enabled=bool(GEMINI_API_KEY))


@app.route('/api/render-sketch', methods=['POST'])
def api_render_sketch():
    """接收草圖 + stone_id + 描述，用 Gemini 生成產品渲染圖（僅限會員）"""
    from flask import jsonify
    if not session.get('customer_id'):
        return jsonify({'error': _('請先登入會員才能使用草圖渲染')}), 401
    if not GEMINI_API_KEY:
        return jsonify({'error': _('草圖渲染需要 Gemini（請設定 GEMINI_API_KEY）')}), 503
    _q = ai_quota_check()
    if _q:
        return _q

    stone_id = request.form.get('stone_id', type=int)
    sketch   = request.files.get('sketch')
    hint     = request.form.get('hint', '').strip()[:120]
    if not stone_id or not sketch:
        return jsonify({'error': _('缺少必要欄位（草圖、石材）')}), 400

    conn = get_db()
    stone = conn.execute('SELECT * FROM stones WHERE id = ?', (stone_id,)).fetchone()
    conn.close()
    if not stone:
        return jsonify({'error': _('找不到指定石材')}), 404
    if not stone['photo']:
        return jsonify({'error': _('此石材沒有照片，無法做材質渲染')}), 400
    stone_photo_path = os.path.join(app.config['UPLOAD_FOLDER'], stone['photo'])
    if not os.path.exists(stone_photo_path):
        return jsonify({'error': _('石材照片檔案不存在')}), 400

    sketch_path = None
    try:
        sketch_path = normalize_image_to_jpg_path(sketch, max_size=1280)
        if not sketch_path:
            return jsonify({'error': _('草圖格式無法解析（支援 JPG / PNG / HEIC / WebP）')}), 400

        result_img = render_sketch_with_gemini(sketch_path, stone_photo_path, hint)
        if result_img is None:
            return jsonify({'error': f'草圖渲染失敗：{_LAST_SYNTH_ERROR or "未回傳影像"}'}), 500

        display_name = (stone['stone_name'] if 'stone_name' in stone.keys() and stone['stone_name']
                        else stone['stone_type'])
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filename = f'design_{secrets.token_hex(8)}.jpg'
        result_img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'JPEG', quality=92)
        label = f'草圖渲染（{hint}）' if hint else '草圖渲染'
        design_id = _record_design(session['customer_id'], stone_id, display_name, filename, label)
        ai_usage_incr(session['customer_id'])
        local_url = url_for('static', filename=f'uploads/{filename}')
        return jsonify({
            'success': True, 'result_url': local_url, 'local_url': local_url,
            'saved': True, 'design_id': design_id,
            'prompt': label + '：' + display_name, 'stone_name': display_name,
            'engine': 'gemini',
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': f'草圖渲染失敗：{str(e)[:200]}'}), 500
    finally:
        if sketch_path and os.path.exists(sketch_path):
            try: os.unlink(sketch_path)
            except Exception: pass


@app.route('/admin/api/analyze-photo', methods=['POST'])
@admin_required
def admin_analyze_photo():
    """管理員 AJAX：上傳照片或指定既有 stone_id，用視覺 AI 產生 prompt"""
    from flask import jsonify
    photo_file = request.files.get('photo')
    stone_id = request.form.get('stone_id', type=int)

    tmp_path = None
    target_path = None
    try:
        if photo_file and photo_file.filename:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tf:
                photo_file.save(tf.name)
                tmp_path = tf.name
            target_path = tmp_path
        elif stone_id:
            conn = get_db()
            row = conn.execute('SELECT photo FROM stones WHERE id = ?', (stone_id,)).fetchone()
            conn.close()
            if row and row['photo']:
                target_path = os.path.join(app.config['UPLOAD_FOLDER'], row['photo'])
        if not target_path or not os.path.exists(target_path):
            return jsonify({'error': _('找不到照片')}), 400

        prompt = describe_stone_with_vision(target_path)
        if not prompt:
            return jsonify({'error': _('AI 分析失敗（請確認 Replicate 餘額充足）')}), 500
        return jsonify({'success': True, 'prompt': prompt})
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except Exception: pass


@app.route('/admin/api/reanalyze-one', methods=['POST'])
@admin_required
def admin_reanalyze_one():
    """管理員 AJAX：分析單一石材照片並把描述存回資料庫（供前端逐張呼叫，避開限速與逾時）。
    遇到 Replicate 429 限速時回傳 429 + retry_after，讓前端等候後重試。"""
    from flask import jsonify
    stone_id = request.form.get('stone_id', type=int)
    if not stone_id:
        return jsonify({'error': _('缺少 stone_id')}), 400
    conn = get_db()
    row = conn.execute('SELECT id, photo FROM stones WHERE id = ?', (stone_id,)).fetchone()
    if not row or not row['photo']:
        conn.close()
        return jsonify({'error': _('此石材沒有照片')}), 400
    path = os.path.join(app.config['UPLOAD_FOLDER'], row['photo'])
    if not os.path.exists(path):
        conn.close()
        return jsonify({'error': f'找不到照片檔案（{row["photo"]}）'}), 400

    prompt = describe_stone_with_vision(path)
    if not prompt:
        conn.close()
        reason = _LAST_VISION_ERROR or 'AI 回傳空白'
        # 限速 → 回 429，讓前端等待後重試
        if '429' in reason or 'throttl' in reason.lower() or 'rate limit' in reason.lower():
            return jsonify({'error': reason, 'throttled': True, 'retry_after': 12}), 429
        return jsonify({'error': reason}), 500

    conn.execute('UPDATE stones SET ai_prompt = ? WHERE id = ?', (prompt, stone_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'prompt': prompt})


@app.route('/admin/reanalyze-prompts', methods=['POST'])
@admin_required
def admin_reanalyze_prompts():
    """批次重新分析所有石材的 AI prompt（一次性升級舊資料）"""
    conn = get_db()
    stones = conn.execute('SELECT id, photo FROM stones WHERE photo IS NOT NULL AND photo != ""').fetchall()
    updated, failed = 0, 0
    first_error = ''
    for s in stones:
        path = os.path.join(app.config['UPLOAD_FOLDER'], s['photo'])
        if not os.path.exists(path):
            failed += 1
            if not first_error:
                first_error = f'石材 #{s["id"]} 找不到照片檔案（{s["photo"]}）'
            continue
        new_prompt = describe_stone_with_vision(path)
        if new_prompt:
            conn.execute('UPDATE stones SET ai_prompt = ? WHERE id = ?', (new_prompt, s['id']))
            updated += 1
        else:
            failed += 1
            if not first_error and _LAST_VISION_ERROR:
                first_error = f'石材 #{s["id"]}：{_LAST_VISION_ERROR}'
    conn.commit()
    conn.close()
    msg = f'AI Prompt 重新分析完成：{updated} 成功 / {failed} 失敗'
    if failed and first_error:
        msg += f'　｜ 失敗原因：{first_error}'
    flash(msg, 'success' if failed == 0 else 'error')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/showcase')
@admin_required
def admin_showcase():
    """展覽圖庫：用 Gemini 把石材生成在空間情境中，供 iPad 展覽模式使用。"""
    conn = get_db()
    stones = conn.execute(
        "SELECT id, stone_name, stone_type, photo FROM stones WHERE photo IS NOT NULL AND photo != '' ORDER BY id"
    ).fetchall()
    images = conn.execute('SELECT * FROM showcase_images ORDER BY created_at DESC, id DESC').fetchall()
    conn.close()
    # 預設 5 個情境，各自循環指派一塊石材
    plan = []
    for i, scene in enumerate(SHOWCASE_SCENES):
        plan.append({'scene_index': i, 'label': scene['label'],
                     'stone_id': stones[i % len(stones)]['id'] if stones else None})
    return render_template('admin_showcase.html', stones=stones, images=images,
                           scenes=SHOWCASE_SCENES, plan=plan,
                           gemini_enabled=bool(GEMINI_API_KEY))


@app.route('/admin/api/generate-showcase', methods=['POST'])
@admin_required
def admin_generate_showcase():
    from flask import jsonify
    if not GEMINI_API_KEY:
        return jsonify({'error': _('未設定 GEMINI_API_KEY，無法生成')}), 400
    scene_index = request.form.get('scene_index', type=int)
    stone_id = request.form.get('stone_id', type=int)
    if scene_index is None or not (0 <= scene_index < len(SHOWCASE_SCENES)) or not stone_id:
        return jsonify({'error': _('參數錯誤')}), 400
    conn = get_db()
    stone = conn.execute('SELECT * FROM stones WHERE id = ?', (stone_id,)).fetchone()
    conn.close()
    if not stone or not stone['photo']:
        return jsonify({'error': _('石材無照片')}), 400
    photo = os.path.join(app.config['UPLOAD_FOLDER'], stone['photo'])
    if not os.path.exists(photo):
        return jsonify({'error': _('找不到石材照片檔案')}), 400

    scene = SHOWCASE_SCENES[scene_index]
    img = generate_showcase_scene(photo, scene['prompt'])
    if img is None:
        reason = _LAST_SYNTH_ERROR or '未回傳影像'
        throttled = ('429' in reason) or ('RESOURCE_EXHAUSTED' in reason) or ('throttl' in reason.lower())
        return jsonify({'error': reason, 'throttled': throttled, 'retry_after': 15}), (429 if throttled else 500)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    fn = f'showcase_{secrets.token_hex(8)}.jpg'
    img.save(os.path.join(app.config['UPLOAD_FOLDER'], fn), 'JPEG', quality=92)
    name = (stone['stone_name'] if 'stone_name' in stone.keys() and stone['stone_name'] else stone['stone_type'])
    conn = get_db()
    conn.execute('INSERT INTO showcase_images (stone_id, stone_name, scene_label, image_file) VALUES (?, ?, ?, ?)',
                 (stone_id, name, scene['label'], fn))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'image_url': url_for('static', filename=f'uploads/{fn}'),
                    'scene_label': scene['label'], 'stone_name': name})


@app.route('/admin/showcase/<int:id>/delete', methods=['POST'])
@admin_required
def delete_showcase(id):
    conn = get_db()
    row = conn.execute('SELECT image_file FROM showcase_images WHERE id = ?', (id,)).fetchone()
    if row:
        delete_photo(row['image_file'])
        conn.execute('DELETE FROM showcase_images WHERE id = ?', (id,))
        conn.commit()
        flash(_('已刪除一張展覽圖'), 'success')
    conn.close()
    return redirect(url_for('admin_showcase'))


@app.route('/api/apply-stone', methods=['POST'])
def api_apply_stone():
    """接收設計圖 + 遮罩 + stone_id，呼叫 Replicate AI 合成新圖（僅限會員）"""
    from flask import jsonify
    if not session.get('customer_id'):
        return jsonify({'error': _('請先登入會員才能使用 AI 設計工具')}), 401
    if not (REPLICATE_API_TOKEN or GEMINI_API_KEY):
        return jsonify({'error': _('AI 功能尚未啟用（請設定 GEMINI_API_KEY 或 REPLICATE_API_TOKEN）')}), 503
    _q = ai_quota_check()
    if _q:
        return _q

    stone_id = request.form.get('stone_id', type=int)
    design   = request.files.get('design')
    mask     = request.files.get('mask')
    custom_prompt = request.form.get('prompt', '').strip()

    if not stone_id or not design or not mask:
        return jsonify({'error': _('缺少必要欄位（設計圖、遮罩、石材）')}), 400

    conn = get_db()
    stone = conn.execute('SELECT * FROM stones WHERE id = ?', (stone_id,)).fetchone()
    conn.close()
    if not stone:
        return jsonify({'error': _('找不到指定石材')}), 404

    display_name = (stone['stone_name'] if 'stone_name' in stone.keys() and stone['stone_name']
                    else stone['stone_type'])

    import tempfile
    design_path, mask_path = None, None
    try:
        # 設計圖：統一轉成 JPG（支援 HEIC）；遮罩來自 canvas 已是 PNG
        design_path = normalize_image_to_jpg_path(design, max_size=1536)
        if not design_path:
            return jsonify({'error': _('設計圖格式無法解析（支援 JPG / PNG / HEIC / WebP）')}), 400
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as mf:
            mask.save(mf.name)
            mask_path = mf.name

        # ── ① 首選：Gemini 參考圖編輯（直接用實際石材照片，最忠實自然）──
        gemini_err = ''
        stone_photo_path = (os.path.join(app.config['UPLOAD_FOLDER'], stone['photo'])
                            if stone['photo'] else None)
        if not GEMINI_API_KEY:
            gemini_err = '未設定 GEMINI_API_KEY'
        elif not (stone_photo_path and os.path.exists(stone_photo_path)):
            gemini_err = '此石材沒有照片，無法用 Gemini 參考圖合成'
        else:
            result_img = synthesize_with_gemini(design_path, mask_path, stone_photo_path)
            if result_img is not None:
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                filename = f'design_{secrets.token_hex(8)}.jpg'
                result_img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'JPEG', quality=92)
                design_id = _record_design(session['customer_id'], stone_id, display_name,
                                           filename, 'Gemini 參考圖合成（使用實際石材照片）')
                ai_usage_incr(session['customer_id'])
                local_url = url_for('static', filename=f'uploads/{filename}')
                return jsonify({
                    'success': True, 'result_url': local_url, 'local_url': local_url,
                    'saved': True, 'design_id': design_id,
                    'prompt': 'Gemini 直接參考此石材照片合成', 'stone_name': display_name,
                    'engine': 'gemini',
                })
            gemini_err = _LAST_SYNTH_ERROR or '未回傳影像'
            # Gemini 失敗：有 Replicate 就往下用 Flux 後備，否則回報錯誤
            if not REPLICATE_API_TOKEN:
                return jsonify({'error': f'Gemini 合成失敗：{gemini_err}'}), 500

        # ── ② 後備：Replicate Flux Fill（文字 prompt inpainting）──
        if not REPLICATE_API_TOKEN:
            return jsonify({'error': _('AI 合成暫時無法使用（Gemini 失敗且未設定 Replicate）')}), 503
        # 組合 prompt：使用者自訂 > 快取 ai_prompt > 視覺描述 > 通用後備
        prompt = resolve_ai_prompt(stone, custom_prompt)
        import replicate
        client = replicate.Client(api_token=REPLICATE_API_TOKEN)
        with open(design_path, 'rb') as dfh, open(mask_path, 'rb') as mfh:
            output = client.run(
                REPLICATE_MODEL,
                input={
                    'image': dfh,
                    'mask': mfh,
                    'prompt': prompt,
                    'output_format': 'jpg',
                    'safety_tolerance': 5,
                }
            )

        print(f'[Replicate output] type={type(output).__name__}, repr={output!r}')

        # 強化版 URL 萃取：兼容 str / list / FileOutput / 其它型別
        def extract_url(o):
            if o is None:
                return None
            if isinstance(o, str):
                return o if o.startswith('http') else None
            # FileOutput.url 是 str 屬性（新版 SDK）
            url_attr = getattr(o, 'url', None)
            if isinstance(url_attr, str) and url_attr.startswith('http'):
                return url_attr
            if callable(url_attr):
                try:
                    r = url_attr()
                    if isinstance(r, str) and r.startswith('http'):
                        return r
                except Exception:
                    pass
            # 最後的 fallback：str() 轉換
            s = str(o)
            return s if s.startswith('http') else None

        candidate = output[0] if isinstance(output, list) and output else output
        result_url = extract_url(candidate)

        if not result_url:
            return jsonify({
                'error': f'AI 完成但回傳格式無法解析（type={type(candidate).__name__}）。請查看 Railway logs。'
            }), 500

        print(f'[Replicate result_url] {result_url}')

        # 存入「我的設計」歷史（下載到 Volume，自動保留最近 HISTORY_LIMIT 張）
        saved_file, design_id = save_synthesis_history(
            session['customer_id'], stone_id, display_name, result_url, prompt)
        ai_usage_incr(session['customer_id'])
        local_url = url_for('static', filename=f'uploads/{saved_file}') if saved_file else None

        return jsonify({
            'success': True,
            'result_url': result_url,
            'local_url': local_url,
            'saved': bool(saved_file),
            'design_id': design_id,
            'prompt': prompt,
            'stone_name': display_name,
            'engine': 'flux',
            'gemini_error': gemini_err,
        })
    except Exception as e:
        import traceback
        print(f'[AI 合成錯誤] {e}')
        traceback.print_exc()
        return jsonify({'error': f'AI 合成失敗：{str(e)[:300]}'}), 500
    finally:
        for p in (design_path, mask_path):
            try:
                if p and os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass


# 不論是本機或雲端，啟動時都初始化資料庫
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5057))
    print("\n" + "="*50)
    print("  ReStone 循環石材服務平台 已啟動！")
    print("="*50)
    print(f"  前台瀏覽：http://127.0.0.1:{port}")
    print(f"  管理後台：http://127.0.0.1:{port}/admin/login")
    print("  預設帳號：admin")
    print("  預設密碼：admin123")
    print("="*50 + "\n")
    app.run(debug=False, host='0.0.0.0', port=port)
