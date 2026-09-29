# -*- coding: utf-8 -*-
"""
ReStone 測試資料：20 筆循環石材（含程式生成的紋理照片與英日文翻譯）

只由後台「產生測試資料／清除測試資料」按鈕呼叫。
  * 照片以 numpy / Pillow 在本機生成仿真紋理 —— 不呼叫任何 AI、不產生費用。
  * 每筆標記 is_test = 1，品名與廠商加上［測試］字樣；清除時連同照片檔一併刪除。
  * 廠商一律為虛構名稱，不掛真實合作廠商，避免被誤認為其實際庫存。
"""
import os
import secrets

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 800
TAG = {'zh': '［測試］', 'en': '[TEST] ', 'ja': '［テスト］'}

# 虛構廠商  (中文, English, 日本語)
VENDORS = {
    'hl': ('［測試］花蓮循環石材行', '[TEST] Hualien Circular Stone Co.', '［テスト］花蓮循環石材'),
    'tc': ('［測試］台中石材再生工坊', '[TEST] Taichung Stone Reuse Studio', '［テスト］台中石材リユース工房'),
    'np': ('［測試］北部裁切餘料中心', '[TEST] Northern Offcut Centre', '［テスト］北部端材センター'),
}


def _S(type_, name, vendor, color, dims, qty, unit, price, desc, tex, photos=1):
    return dict(type=type_, name=name, vendor=vendor, color=color, dims=dims,
                qty=qty, unit=unit, price=price, desc=desc, tex=tex, photos=photos)


def _M(base, veins, cloud=9, angle=None, amp=(40, 140), spread=0.15):
    return dict(kind='marble', base=base, veins=veins, cloud=cloud, angle=angle, amp=amp, spread=spread)


# ─────────────────────────────────────────────────────────────
#  20 筆石材：4 種類 × 8 色系全覆蓋，含價格洽詢／低庫存／無尺寸等邊界情況
# ─────────────────────────────────────────────────────────────
TEST_STONES = [
    # ── 大理石 ──
    _S('大理石', ('卡拉拉白', 'Carrara White', 'カラーラホワイト'), 'np', 'white', (60, 60, 2), 24, '片', 1800,
       ('義大利卡拉拉白大理石的工程裁切餘料，灰色細紋清晰，邊角完整，適合檯面、桌板與小型家具。',
        'Offcuts from an Italian Carrara White marble project. Crisp grey veining and clean edges — '
        'suited to countertops, tabletops and small furniture.',
        'イタリア産カラーラホワイト大理石の施工端材。グレーの細い石目が美しく、エッジも良好。'
        'カウンターや天板、小型家具に最適です。'),
       _M((236, 234, 229), [((125, 126, 130), 9, (1.0, 2.6), (0.45, 0.95)),
                            ((160, 160, 164), 16, (0.5, 1.0), (0.25, 0.55))], cloud=7), photos=2),
    _S('大理石', ('雪花白', 'Snow White', 'スノーホワイト'), 'tc', 'white', (80, 40, 2), 12, '片', 1500,
       ('純白底色帶極淡灰紋，來自室內裝修工程的剩餘板材，表面拋光良好。',
        'Near-pure white with very faint grey veins. Surplus slabs from an interior fit-out, well polished.',
        'ほぼ純白の地にごく淡いグレーの石目。内装工事の余剰材で、研磨状態も良好です。'),
       _M((245, 244, 241), [((190, 190, 196), 6, (0.6, 1.6), (0.3, 0.6)),
                            ((214, 214, 218), 10, (0.4, 0.9), (0.2, 0.45))], cloud=8)),
    _S('大理石', ('銀狐', 'Silver Fox', 'シルバーフォックス'), 'np', 'gray', (120, 60, 2), 6, '片', 3200,
       ('灰底白色波浪紋理，紋路流動感強，整片大尺寸餘料，適合作為牆面主視覺或大型桌面。',
        'Grey ground with flowing, wave-like white veins. Large offcut slabs — ideal for a feature wall '
        'or a large tabletop.',
        'グレー地に白い波状の石目が流れるように走ります。大判の端材で、アクセントウォールや大型テーブルに最適。'),
       _M((170, 171, 174), [((240, 240, 238), 14, (1.2, 3.2), (0.55, 1.0)),
                            ((215, 215, 214), 18, (0.5, 1.0), (0.3, 0.6))], cloud=10, amp=(60, 170))),
    _S('大理石', ('西班牙米黃', 'Crema Marfil', 'クレママーフィル'), 'tc', 'beige', (60, 60, 2), 40, '片', 1200,
       ('溫潤米黃色，紋理柔和均勻，庫存量充足，適合大面積鋪設或一系列傢俱開發。',
        'Warm cream beige with soft, even patterning. Plenty in stock — good for large areas or a furniture series.',
        '温かみのあるクリームベージュで、柔らかく均一な模様。在庫が豊富で、広い面積や家具シリーズの開発に向いています。'),
       _M((224, 205, 170), [((186, 160, 118), 7, (1.2, 3.2), (0.4, 0.75)),
                            ((242, 232, 210), 10, (0.5, 1.2), (0.4, 0.75))], cloud=18)),
    _S('大理石', ('咖啡網紋', 'Emperador Dark', 'エンペラドールダーク'), 'hl', 'brown', (30, 60, 2), 18, '片', 900,
       ('深咖啡底色搭配淺色網狀紋理，小尺寸條板，適合杯墊、托盤等小物設計。',
        'Deep coffee brown with a light, net-like vein pattern. Small strip offcuts — great for coasters, '
        'trays and small objects.',
        '深いコーヒーブラウンに明るい網目状の石目。小さな短冊状の端材で、コースターやトレーなどの小物に最適です。'),
       _M((104, 74, 52), [((214, 192, 160), 26, (0.8, 2.2), (0.5, 1.0)),
                          ((150, 112, 82), 20, (0.6, 1.5), (0.4, 0.8))], cloud=14, spread=0.9)),
    _S('大理石', ('黑金花', 'Nero Portoro', 'ネロポルトロ'), 'np', 'black', (60, 30, 2), 8, '片', 2500,
       ('黑色底配金色與白色紋路，視覺華麗，適合高端家飾與精品展示台。',
        'Black ground with gold and white veining — striking and luxurious, suited to premium homeware '
        'and display plinths.',
        '黒地に金と白の石目が入る華やかな石材。高級インテリア小物やディスプレイ台に適しています。'),
       _M((28, 26, 26), [((196, 164, 104), 10, (0.9, 2.4), (0.6, 1.0)),
                         ((225, 220, 210), 8, (0.6, 1.6), (0.5, 0.95))], cloud=5)),
    _S('大理石', ('玫瑰紅', 'Rosso Levanto', 'ロッソレバント'), 'hl', 'red', (40, 40, 2), 10, '片', None,
       ('酒紅底色帶白色細紋，色彩鮮明，數量有限，價格請洽詢。',
        'Wine red with fine white veins and vivid colour. Limited quantity — price on request.',
        'ワインレッドの地に白い細い石目。色鮮やかで数量限定、価格はお問い合わせください。'),
       _M((148, 58, 55), [((226, 205, 196), 12, (0.8, 2.2), (0.55, 1.0)),
                          ((110, 40, 38), 10, (1.2, 3.0), (0.3, 0.6))], cloud=12)),
    _S('大理石', ('和平白', 'Hoping White', 'ホーピンホワイト'), 'hl', 'white', (100, 50, 3), 15, '片', 1000,
       ('花蓮和平礦區出產的台灣白色大理石，帶灰色條紋，在地石材、運輸碳排低。',
        'Taiwanese white marble from the Hoping quarry area in Hualien, with grey banding. Locally sourced, '
        'with low transport emissions.',
        '花蓮・和平地区産の台湾ホワイト大理石で、グレーの縞模様が入ります。地元産のため輸送時の CO₂ 排出が少ない石材です。'),
       _M((226, 226, 222), [((146, 148, 146), 7, (2.0, 5.0), (0.3, 0.6)),
                            ((175, 176, 174), 10, (0.7, 1.4), (0.3, 0.6))], cloud=9, angle=0.18)),
    # ── 花崗岩 ──
    _S('花崗岩', ('芝麻灰', 'Sesame Grey (G603)', 'セサミグレー（G603）'), 'tc', 'gray', (60, 60, 3), 60, '片', 600,
       ('黑白灰顆粒均勻分布的花崗岩，硬度高、耐磨，適合戶外鋪面與高使用頻率的檯面。',
        'Granite with an even salt-and-pepper speckle. Hard and hard-wearing — suited to outdoor paving '
        'and heavy-use worktops.',
        '白・グレー・黒の粒が均一に分布する御影石。硬く耐摩耗性に優れ、屋外の舗装や使用頻度の高い天板に適しています。'),
       dict(kind='granite', palette=[(214, 214, 211), (165, 165, 165), (78, 78, 80), (36, 36, 40)],
            weights=[.42, .30, .18, .10])),
    _S('花崗岩', ('中國黑', 'Shanxi Black', 'シャンシーブラック'), 'np', 'black', (60, 30, 3), 30, '片', 800,
       ('深黑色細顆粒花崗岩，質地緊密，適合現代極簡風格的家具與檯面。',
        'Deep black, fine-grained granite with a dense texture — well suited to minimalist contemporary '
        'furniture and worktops.',
        '深い黒色の細粒御影石で、緻密な質感。ミニマルでモダンな家具や天板に向いています。'),
       dict(kind='granite', palette=[(30, 30, 33), (46, 46, 50), (72, 72, 78), (112, 112, 118)],
            weights=[.50, .30, .14, .06])),
    _S('花崗岩', ('印度紅', 'Imperial Red', 'インペリアルレッド'), 'tc', 'red', (60, 60, 2), 20, '片', 1100,
       ('紅色系花崗岩，顆粒中夾雜黑色與淺色晶體，色彩溫暖，適合戶外家具與景觀設計。',
        'Red granite with black and pale crystals among the grains. Warm in colour — good for outdoor '
        'furniture and landscape design.',
        '赤系の御影石で、黒や淡色の結晶が混じります。温かみのある色合いで、屋外家具やランドスケープに適しています。'),
       dict(kind='granite', palette=[(152, 58, 48), (186, 84, 68), (58, 40, 40), (212, 184, 172)],
            weights=[.38, .30, .20, .12])),
    _S('花崗岩', ('黃金麻', 'Golden Sesame', 'ゴールデンセサミ'), 'hl', 'beige', (80, 80, 3), 2, '片', 1300,
       ('米黃底帶淺金色顆粒，庫存僅剩 2 片，適合單件作品或樣品製作。',
        'Cream ground with pale golden grains. Only 2 pieces left — best for a one-off piece or a prototype.',
        'クリーム地に淡い金色の粒。残り 2 枚のみのため、一点ものや試作に向いています。'),
       dict(kind='granite', palette=[(212, 188, 148), (184, 158, 118), (238, 228, 206), (96, 84, 72), (200, 160, 90)],
            weights=[.30, .25, .25, .10, .10])),
    _S('花崗岩', ('藍珍珠', 'Blue Pearl', 'ブルーパール'), 'np', 'multi', (50, 50, 2), 5, '片', 2800,
       ('藍灰色底帶珍珠光澤晶體，光線下會閃爍，屬進口高單價石材的剩料。',
        'Blue-grey with pearlescent crystals that shimmer in the light. Surplus from a premium imported stone.',
        '青みがかったグレーに真珠のような光沢をもつ結晶が輝きます。高価な輸入石材の余剰材です。'),
       dict(kind='granite', palette=[(66, 80, 100), (108, 124, 150), (38, 42, 52), (150, 166, 192), (92, 108, 134)],
            weights=[.28, .24, .20, .12, .16])),
    # ── 蛇紋石 ──
    _S('蛇紋石', ('花蓮蛇紋石', 'Hualien Serpentine', '花蓮サーペンティン'), 'hl', 'green', (60, 40, 2), 14, '片', 1600,
       ('台灣花蓮特有的綠色蛇紋石，帶深淺交錯的網狀紋理，展現在地石材特色。',
        'Green serpentine unique to Hualien, Taiwan, with an interlacing net of light and dark veins — '
        'a showcase of local stone.',
        '台湾・花蓮特有のグリーンの蛇紋石で、濃淡の網目状の石目が交差します。地元の石材の魅力を伝える素材です。'),
       dict(kind='serpentine', base=(72, 112, 86), dark=(28, 52, 38), light=(186, 212, 192)), photos=2),
    _S('蛇紋石', ('墨綠蛇紋石', 'Forest Green Serpentine', 'フォレストグリーン・サーペンティン'), 'hl', 'green',
       (100, 100, 2), 3, '片', 4500,
       ('深墨綠色大板餘料，紋理沉穩，適合大型桌面或空間主牆。',
        'Large, deep forest-green offcut slabs with a calm, dense pattern — suited to large tabletops '
        'or a feature wall.',
        '深い墨緑色の大判端材で、落ち着いた模様。大きなテーブル天板や空間のメインウォールに適しています。'),
       dict(kind='serpentine', base=(36, 64, 48), dark=(14, 30, 22), light=(116, 156, 126))),
    _S('蛇紋石', ('豐田玉紋石', 'Fengtian Jade Stone', '豊田玉紋石'), 'hl', 'green', (30, 30, 1.5), 50, '片', 700,
       ('花蓮豐田地區的淺綠色玉紋石，薄板小片，適合飾品、燈具與文創小物。',
        'Pale green jade-patterned stone from Fengtian, Hualien. Thin, small tiles — ideal for jewellery, '
        'lighting and creative small goods.',
        '花蓮・豊田地区産の淡い緑の玉紋石。薄く小さな板材で、アクセサリーや照明、クラフト小物に最適です。'),
       dict(kind='serpentine', base=(104, 150, 112), dark=(56, 92, 64), light=(208, 230, 206))),
    _S('蛇紋石', ('蛇紋石碎料', 'Serpentine Offcut Pieces', '蛇紋石の端材ピース'), 'tc', 'multi', None, 200, 'kg', 30,
       ('蛇紋石加工後的不規則碎料，以公斤計價，適合馬賽克拼貼、水磨石骨材與實驗性設計。',
        'Irregular serpentine pieces left after processing, sold by the kilo — for mosaics, terrazzo '
        'aggregate and experimental design.',
        '蛇紋石の加工後に出る不定形の端材。キロ単位で販売し、モザイクやテラゾーの骨材、実験的なデザインに適しています。'),
       dict(kind='pieces', palette=[(72, 112, 86), (36, 64, 48), (104, 150, 112), (214, 214, 211),
                                    (186, 212, 192), (28, 52, 38)])),
    # ── 化石 ──
    _S('化石', ('侏羅紀米黃', 'Jura Beige (Shell Fossil)', 'ジュラベージュ（貝化石）'), 'tc', 'beige', (60, 60, 2), 16, '片', 2200,
       ('米黃色石灰岩中可見清晰的貝殼化石，每片花紋獨一無二，適合具故事性的產品設計。',
        'Cream limestone with clearly visible shell fossils; every piece is unique — ideal for products '
        'with a story.',
        'クリーム色の石灰岩に貝の化石がはっきりと見られ、一枚ごとに模様が異なります。ストーリー性のある製品デザインに最適です。'),
       dict(kind='fossil', fossil='shell', base=(214, 196, 158), shell=(150, 124, 86))),
    _S('化石', ('海百合化石石', 'Crinoid Fossil Stone', 'ウミユリ化石石材'), 'np', 'gray', (40, 80, 2), 7, '片', 2600,
       ('深灰色底中散布海百合莖化石的圓形斷面，自然紋樣獨特，適合精品家飾。',
        'Dark grey stone scattered with round cross-sections of crinoid-stem fossils — a distinctive '
        'natural pattern for premium homeware.',
        'ダークグレーの地にウミユリの茎の化石の円形断面が散らばる、個性的な天然模様。高級インテリア小物に適しています。'),
       dict(kind='fossil', fossil='crinoid', base=(92, 90, 88), shell=(188, 182, 172))),
    _S('化石', ('菊石化石板', 'Ammonite Fossil Slab', 'アンモナイト化石スラブ'), 'hl', 'brown', (50, 50, 3), 1, '塊', None,
       ('含完整菊石化石的單塊板材，僅此一件，適合作為展示或收藏級作品，價格請洽詢。',
        'A single slab containing complete ammonite fossils — one of a kind, suited to display or '
        'collector-grade pieces. Price on request.',
        '完全なアンモナイトの化石を含む一点ものの板材。展示用やコレクション級の作品に適しています。価格はお問い合わせください。'),
       dict(kind='fossil', fossil='ammonite', base=(132, 102, 74), shell=(66, 48, 34))),
]


# ─────────────────────────────────────────────────────────────
#  紋理生成（numpy / Pillow，全本機運算）
# ─────────────────────────────────────────────────────────────
def _noise(rng, cells):
    g = rng.integers(0, 256, (cells, cells), dtype=np.uint8)
    im = Image.fromarray(g, 'L').resize((SIZE, SIZE), Image.BICUBIC)
    return np.asarray(im, np.float32) / 127.5 - 1.0


def _grid():
    ys, xs = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    return xs, ys


def _smooth1d(rng, n, sigma):
    """一維平滑隨機曲線（白噪音 × 高斯核），標準化為單位標準差。"""
    pad = int(sigma * 4) + 1
    x = rng.normal(0, 1, n + 2 * pad)
    t = np.arange(-pad, pad + 1)
    k = np.exp(-0.5 * (t / sigma) ** 2)
    y = np.convolve(x, k / k.sum(), mode='valid')
    return y / (y.std() + 1e-9)


def _vein_mask(rng, n, width, strength, amp=(40, 140), spread=0.15, angle=None, branch=0.4):
    """自然大理石脈紋：分形蜿蜒路徑、沿線粗細與濃淡變化、柔和光暈、隨機分岔。回傳 0–1 遮罩。"""
    xs, ys = _grid()
    base_th = rng.uniform(-0.8, 0.8) if angle is None else angle
    N = 512
    mask = np.zeros((SIZE, SIZE), np.float32)
    for _ in range(n):
        th = base_th + rng.normal(0, spread)
        U = xs * np.cos(th) + ys * np.sin(th)
        V = -xs * np.sin(th) + ys * np.cos(th)
        gu = np.linspace(U.min(), U.max(), N)
        # 三個尺度疊加：大幅蜿蜒 + 中段抖動 + 細微毛邊
        off = (rng.uniform(*amp) * _smooth1d(rng, N, 60)
               + rng.uniform(5, 14) * _smooth1d(rng, N, 10)
               + rng.uniform(0.6, 1.8) * _smooth1d(rng, N, 2))
        w0, s0 = rng.uniform(*width), rng.uniform(*strength)
        wid = w0 * np.clip(0.9 + 0.6 * _smooth1d(rng, N, 25), 0.15, 2.0)      # 粗細變化
        stg = s0 * np.clip(0.75 + 0.45 * _smooth1d(rng, N, 40), 0.05, 1.0)    # 濃淡、時隱時現
        v0 = rng.uniform(V.min(), V.max())
        paths = [(off, wid, stg)]
        if rng.random() < branch:                    # 分岔：從某點起逐漸偏離主脈
            ub = rng.uniform(0.2, 0.7) * N
            idx = np.arange(N)
            div = np.where(idx > ub, (idx - ub) * rng.uniform(-0.9, 0.9), 0)
            ramp = np.clip((idx - ub) / 40, 0, 1)
            paths.append((off + div + 6 * _smooth1d(rng, N, 12), wid * 0.6, stg * 0.8 * ramp))
        for po, pw, ps in paths:
            d = V - (v0 + np.interp(U, gu, po))
            w = np.interp(U, gu, pw)
            st = np.interp(U, gu, ps)
            m = st * (np.exp(-(d / w) ** 2) + 0.22 * np.exp(-(d / (w * 3.5)) ** 2))   # 主線 + 光暈
            mask = np.maximum(mask, m)
    return np.clip(mask, 0, 1)


def _soften(mask, r=0.8):
    im = Image.fromarray((np.clip(mask, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, np.float32) / 255.0


def _marble(rng, t):
    a = np.empty((SIZE, SIZE, 3), np.float32)
    a[:] = t['base']
    a += (_noise(rng, 5) * t['cloud'] + _noise(rng, 22) * t['cloud'] * 0.4)[..., None]
    for color, n, width, strength in t['veins']:
        m = _soften(_vein_mask(rng, n, width, strength, t['amp'], t['spread'], t['angle']), 0.6)[..., None]
        a = a * (1 - m) + np.array(color, np.float32) * m
    return a


def _granite(rng, t):
    pal = np.array(t['palette'], np.float32)
    p = np.array(t['weights'], np.float64)
    p /= p.sum()
    g = SIZE // 3
    idx = rng.choice(len(pal), size=(g, g), p=p)
    base = Image.fromarray(pal[idx].astype(np.uint8)).resize((SIZE, SIZE), Image.NEAREST)
    img = base.filter(ImageFilter.GaussianBlur(0.9))
    d = ImageDraw.Draw(img)
    for _ in range(SIZE * SIZE // 650):          # 不規則多邊形晶體
        cx, cy = rng.uniform(0, SIZE, 2)
        r = rng.uniform(3, 11)
        k = int(rng.integers(4, 7))
        ang = np.sort(rng.uniform(0, 2 * np.pi, k))
        pts = [(cx + r * rng.uniform(.6, 1.2) * np.cos(q), cy + r * rng.uniform(.6, 1.2) * np.sin(q)) for q in ang]
        col = np.clip(pal[rng.choice(len(pal), p=p)] + rng.normal(0, 8, 3), 0, 255)
        d.polygon(pts, fill=tuple(int(c) for c in col))
    a = np.asarray(img.filter(ImageFilter.GaussianBlur(0.6)), np.float32)
    return a + rng.normal(0, 6, (SIZE, SIZE, 3))


def _serpentine(rng, t):
    a = np.empty((SIZE, SIZE, 3), np.float32)
    a[:] = t['base']
    a += (_noise(rng, 4) * 22 + _noise(rng, 14) * 12 + _noise(rng, 40) * 5)[..., None]
    patch = np.clip(_noise(rng, 7) * 1.4, 0, 1)[..., None]
    a = a * (1 - 0.5 * patch) + np.array(t['dark'], np.float32) * 0.5 * patch
    md = _soften(_vein_mask(rng, 14, (0.8, 2.4), (0.4, 0.9), (30, 110), spread=0.7), 0.6)[..., None]
    a = a * (1 - md) + np.array(t['dark'], np.float32) * md
    ml = _soften(_vein_mask(rng, 7, (0.5, 1.4), (0.5, 0.95), (25, 90), spread=0.6), 0.5)[..., None]
    return a * (1 - ml) + np.array(t['light'], np.float32) * ml


def _fossil(rng, t):
    a = np.empty((SIZE, SIZE, 3), np.float32)
    a[:] = t['base']
    a += (_noise(rng, 6) * 10 + _noise(rng, 30) * 4)[..., None]
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img, 'RGBA')
    sc = tuple(t['shell'])
    kind = t['fossil']
    if kind == 'shell':
        for _ in range(55):                          # 貝殼斷面（較深的填色）
            cx, cy = rng.uniform(0, SIZE, 2)
            w = rng.uniform(10, 30)
            h = w * rng.uniform(.3, .55)
            d.ellipse([cx - w, cy - h, cx + w, cy + h], fill=sc + (int(rng.uniform(60, 110)),))
        for _ in range(130):                         # 破碎貝殼弧線
            cx, cy = rng.uniform(0, SIZE, 2)
            w = rng.uniform(10, 40)
            h = w * rng.uniform(.25, .6)
            st = rng.uniform(0, 360)
            d.arc([cx - w, cy - h, cx + w, cy + h], st, st + rng.uniform(100, 300),
                  fill=sc + (int(rng.uniform(170, 240)),), width=int(rng.integers(2, 4)))
    elif kind == 'crinoid':
        for _ in range(120):
            cx, cy = rng.uniform(0, SIZE, 2)
            r = rng.uniform(3, 11)
            n = int(rng.integers(1, 6))
            dx, dy = rng.normal(0, 1, 2)
            nn = max(np.hypot(dx, dy), 1e-6)
            for i in range(n):                       # 莖節成串
                x, y = cx + dx / nn * i * r * 1.9, cy + dy / nn * i * r * 1.9
                al = int(rng.uniform(150, 230))
                d.ellipse([x - r, y - r, x + r, y + r], outline=sc + (al,), width=2)
                d.ellipse([x - r * .25, y - r * .25, x + r * .25, y + r * .25], fill=sc + (al,))
    else:                                            # ammonite
        for _ in range(3):
            cx, cy = rng.uniform(140, SIZE - 140, 2)
            rmax = rng.uniform(70, 125)
            b = 0.19
            th = np.linspace(0, 4.4 * np.pi, 420)
            rr = rmax * np.exp(b * (th - th[-1]))
            rot = rng.uniform(0, 2 * np.pi)
            pts = list(zip(cx + rr * np.cos(th + rot), cy + rr * np.sin(th + rot)))
            d.line(pts, fill=sc + (235,), width=4)
            for k in range(0, len(th), 14):          # 縫合線
                x0, y0 = pts[k]
                x1 = cx + rr[k] * 0.72 * np.cos(th[k] + rot)
                y1 = cy + rr[k] * 0.72 * np.sin(th[k] + rot)
                d.line([(x0, y0), (x1, y1)], fill=sc + (150,), width=2)
        for _ in range(40):
            cx, cy = rng.uniform(0, SIZE, 2)
            w = rng.uniform(5, 16)
            st = rng.uniform(0, 360)
            d.arc([cx - w, cy - w * .5, cx + w, cy + w * .5], st, st + 200, fill=sc + (150,), width=2)
    return np.asarray(img.filter(ImageFilter.GaussianBlur(0.6)), np.float32)


def _pieces(rng, t):
    img = Image.new('RGB', (SIZE, SIZE), (46, 48, 46))
    d = ImageDraw.Draw(img)
    pal = np.array(t['palette'], np.float32)
    n = 7
    cell = SIZE / n
    for i in range(n):
        for j in range(n):
            cx = (i + .5) * cell + rng.uniform(-.15, .15) * cell
            cy = (j + .5) * cell + rng.uniform(-.15, .15) * cell
            k = int(rng.integers(4, 7))
            ang = np.sort(rng.uniform(0, 2 * np.pi, k))
            r = cell * rng.uniform(.40, .54)
            pts = [(cx + r * rng.uniform(.75, 1.05) * np.cos(q), cy + r * rng.uniform(.75, 1.05) * np.sin(q)) for q in ang]
            col = np.clip(pal[rng.integers(0, len(pal))] + rng.normal(0, 10, 3), 0, 255)
            d.polygon(pts, fill=tuple(int(c) for c in col))
    a = np.asarray(img, np.float32)
    return a + (_noise(rng, 18) * 10 + _noise(rng, 60) * 5)[..., None]


def _finish(rng, a):
    """模擬拍攝：輕微光線漸層、暗角與感光雜訊。"""
    xs, ys = _grid()
    xs /= SIZE
    ys /= SIZE
    gx, gy = rng.uniform(-1, 1, 2)
    light = 1 + 0.07 * ((xs - .5) * gx + (ys - .5) * gy)
    vign = 1 - 0.24 * ((xs - .5) ** 2 + (ys - .5) ** 2)
    a = a * (light * vign)[..., None] + rng.normal(0, 2, (SIZE, SIZE, 3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


_GEN = {'marble': _marble, 'granite': _granite, 'serpentine': _serpentine,
        'fossil': _fossil, 'pieces': _pieces}


def make_photo(index, tex, variant=0):
    """同一筆石材的不同 variant 代表同批次的另一片板材（紋理相似、不完全相同）。"""
    rng = np.random.default_rng(1000 + index * 97 + variant * 7919)
    return _finish(rng, _GEN[tex['kind']](rng, tex))


# ─────────────────────────────────────────────────────────────
#  資料庫操作
# ─────────────────────────────────────────────────────────────
def count(conn):
    try:
        return conn.execute('SELECT COUNT(*) FROM stones WHERE is_test = 1').fetchone()[0]
    except Exception:
        return 0


def clear(conn, delete_photo):
    """刪除所有測試石材與其照片檔，回傳刪除筆數。"""
    rows = conn.execute('SELECT id, photo, photo2, photo3 FROM stones WHERE is_test = 1').fetchall()
    for r in rows:
        for f in ('photo', 'photo2', 'photo3'):
            if r[f]:
                delete_photo(r[f])
    conn.execute('DELETE FROM stones WHERE is_test = 1')
    conn.commit()
    return len(rows)


def seed(conn, upload_folder, analyze, prompt_for):
    """建立 20 筆測試石材（照片、以圖搜圖索引、英日文翻譯皆齊全），回傳建立筆數。

    analyze    : app.analyze_image_full    —— 本機計算顏色／雜湊／視覺特徵
    prompt_for : app.generate_ai_prompt    —— 純模板，不呼叫 AI
    """
    os.makedirs(upload_folder, exist_ok=True)
    created = 0
    for i, s in enumerate(TEST_STONES):
        photos = []
        for v in range(s['photos']):
            fn = f'test_{secrets.token_hex(8)}.jpg'
            make_photo(i, s['tex'], v).save(os.path.join(upload_folder, fn), 'JPEG', quality=88)
            photos.append(fn)
        _, phash, rgb, feats = analyze(os.path.join(upload_folder, photos[0]))
        w, h, t = s['dims'] if s['dims'] else (None, None, None)
        zh, en, ja = s['name']
        vz, ve, vj = VENDORS[s['vendor']]
        dz, de, dj = s['desc']
        conn.execute(
            '''INSERT INTO stones
               (stone_type, stone_name, photo, photo2, width, height, thickness, quantity, unit, price,
                vendor, description, color, image_hash, dominant_rgb, features, ai_prompt,
                stone_name_en, stone_name_ja, description_en, description_ja, vendor_en, vendor_ja, is_test)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)''',
            (s['type'], TAG['zh'] + zh, photos[0], photos[1] if len(photos) > 1 else None,
             w, h, t, s['qty'], s['unit'], s['price'],
             vz, dz, s['color'], phash, rgb, feats, prompt_for(s['type'], s['color'], dz),
             TAG['en'] + en, TAG['ja'] + ja, de, dj, ve, vj))
        created += 1
    conn.commit()
    return created
