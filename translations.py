# -*- coding: utf-8 -*-
"""
ReStone 多語系翻譯表（中文 / English / 日本語）

設計原則
  * 以「中文原文」當 key —— 翻譯缺漏時自動回退顯示中文，永不出現空白或亂碼。
  * 純字典、免編譯、不新增套件；要改字或加語言直接編輯下方 _T 即可。
  * 查表會自動忽略空白差異（模板換行縮排不影響命中）。
  * 資料庫內容（石材品名、廠商、描述、公告）維持原文，不在此表內。

新增一條翻譯：在 _T 加一行  '中文': ('English', '日本語'),
"""
import re

LANGS = {'zh': '中文', 'en': 'English', 'ja': '日本語'}
DEFAULT_LANG = 'zh'
HTML_LANG = {'zh': 'zh-TW', 'en': 'en', 'ja': 'ja'}

# ─────────────────────────────────────────────────────────────
#  中文原文: (English, 日本語)
# ─────────────────────────────────────────────────────────────
_T = {
    # ══ 品牌 / 導覽 / 頁尾 ══
    'ReStone 循環石材服務平台': ('ReStone Circular Stone Platform', 'ReStone 循環石材プラットフォーム'),
    '循環石材服務平台': ('Circular Stone Platform', '循環石材プラットフォーム'),
    '© ReStone 循環石材服務平台': ('© ReStone Circular Stone Platform', '© ReStone 循環石材プラットフォーム'),
    'ReStone 循環石材服務平台 — 支持循環經濟，讓石材物盡其用':
        ('ReStone Circular Stone Platform — making every stone count',
         'ReStone 循環石材プラットフォーム — 石材を活かしきる'),
    'ReStone 循環石材服務平台 ·Powered by AI Vision Search':
        ('ReStone Circular Stone Platform · Powered by AI Vision Search',
         'ReStone 循環石材プラットフォーム · Powered by AI Vision Search'),
    '支持循環經濟 · 讓石材物盡其用':
        ('Supporting the circular economy — making every stone count',
         'サーキュラーエコノミーを支え、石材を活かしきる'),
    '支持循環經濟，讓石材物盡其用':
        ('Supporting the circular economy — making every stone count',
         'サーキュラーエコノミーを支え、石材を活かしきる'),
    '管理後台': ('Admin', '管理画面'),
    '後台': ('Admin', '管理画面'),
    '◈ ReStone 後台': ('◈ ReStone Admin', '◈ ReStone 管理画面'),
    '登入': ('Sign in', 'ログイン'),
    '登出': ('Sign out', 'ログアウト'),
    '登出 →': ('Sign out →', 'ログアウト →'),
    '免費註冊': ('Sign up free', '無料登録'),
    '註冊': ('Sign up', '新規登録'),
    '系統管理': ('Admin', '管理画面'),
    '← 返回首頁': ('← Home', '← ホーム'),
    '返回首頁': ('Home', 'ホーム'),
    '首頁': ('Home', 'ホーム'),
    '← 返回列表': ('← Back to list', '← 一覧へ戻る'),
    '← 返回石材列表': ('← Back to stone list', '← 石材一覧へ戻る'),
    '← 返回庫存': ('← Back to inventory', '← 在庫へ戻る'),
    '← 返回前台瀏覽': ('← View public site', '← 公開サイトへ'),
    '← 設計工具': ('← Design Tools', '← デザインツール'),
    '我的設計': ('My Designs', 'マイデザイン'),
    '我的帳號': ('My Account', 'マイアカウント'),
    '設計工具': ('Design Tools', 'デザインツール'),
    '瀏覽石材': ('Browse stones', '石材を見る'),
    '看石材': ('View stone', '石材を見る'),
    '前往': ('Go', '開く'),
    '查看全部 →': ('View all →', 'すべて見る →'),

    # ══ 首頁 ══
    '即時庫存系統 · LIVE INVENTORY': ('LIVE INVENTORY', 'リアルタイム在庫 · LIVE INVENTORY'),
    '探索可再利用的優質石材，連結設計師與供應商，':
        # 結尾空格：手機版取消 <br> 換行後，英文兩段才不會黏成 "suppliersfor"（桌機的行尾空白會被忽略）
        ('Discover reusable premium stone. Connecting designers and suppliers ',
         '再利用できる上質な石材を探す。デザイナーとサプライヤーをつなぎ、'),
    '共同支持循環經濟與永續設計':
        ('for a circular economy and sustainable design.',
         '循環型経済とサステナブルデザインを支えます。'),
    '石材項目': ('Stones', '石材点数'),
    '石材種類': ('Categories', '石材の種類'),
    '累積減碳 CO₂e': ('CO₂e saved', 'CO₂e 削減量'),
    '最新消息': ('News', 'お知らせ'),
    '置頂': ('Pinned', '固定'),
    '全部種類': ('All types', 'すべての種類'),
    '搜尋': ('Search', '検索'),
    '以圖搜圖': ('Image Search', '画像で検索'),
    '× 清除篩選': ('× Clear filters', '× 条件をクリア'),
    '顏色：': ('Colour:', 'カラー：'),
    '全部': ('All', 'すべて'),
    '暫無照片': ('No photo', '写真なし'),
    '價格洽詢': ('Price on request', '価格はお問い合わせ'),
    '洽詢': ('On request', 'お問い合わせ'),
    '搜尋石材種類、廠商名稱...': ('Search stone type or supplier…', '石材の種類・サプライヤー名で検索…'),
    '上傳圖片找相似石材': ('Upload a photo to find similar stone', '画像をアップロードして似た石材を探す'),
    'AI 設計工具：材質模擬、草圖渲染':
        ('AI design tools: material simulation, sketch rendering',
         'AI デザインツール：マテリアル合成・スケッチレンダリング'),
    '沒有找到符合的石材': ('No matching stone found', '該当する石材が見つかりません'),

    # ══ 設計工具 Studio ══
    '設計工具 — ReStone': ('Design Tools — ReStone', 'デザインツール — ReStone'),
    '選擇一個工具開始：用 AI 把循環石材帶進你的設計。':
        ('Pick a tool to begin — bring circular stone into your design with AI.',
         'ツールを選んで開始 — AI で循環石材をデザインに取り込みます。'),
    '材質模擬': ('Material Simulation', 'マテリアル合成'),
    '上傳設計圖或空間照片，圈選要替換的區域（牆面、桌面、家具表面），AI 把循環石材的真實紋理套用上去，即時預覽完成效果。':
        ('Upload a design or room photo, brush over the surface to replace (wall, worktop, furniture), '
         'and AI applies the real stone texture — preview instantly.',
         'デザイン画や空間写真をアップロードし、置き換える範囲（壁・天板・家具表面）をブラシで指定すると、'
         'AI が循環石材の実際のテクスチャを適用します。'),
    '開始模擬 →': ('Start →', '開始する →'),
    '牆面模擬': ('Wall Simulation', 'ウォールシミュレーション'),
    '點選牆面四個角、輸入牆面尺寸，以正確的透視與比例即時貼上循環石材，並同步顯示用片數、庫存與減碳效益。':
        ('Mark the wall’s four corners and enter its size. Stone is applied with correct perspective '
         'and scale, with tile count, stock and carbon savings shown live.',
         '壁の四隅を指定し寸法を入力すると、正しい遠近と比率で石材を貼り付け、'
         '必要枚数・在庫・CO₂ 削減量を同時に表示します。'),
    '草圖渲染': ('Sketch Rendering', 'スケッチレンダリング'),
    '上傳手繪草圖或概念線稿，選一塊循環石材，再補一句產品描述，AI 生成寫實的產品渲染圖——概念秒變提案。':
        ('Upload a hand sketch or line art, choose a stone, add a short description, and AI produces '
         'a photoreal product render — concept to proposal in seconds.',
         '手描きスケッチや線画をアップロードし、石材を選んで一言説明を加えると、'
         'AI がリアルな製品レンダリングを生成します。'),
    '開始渲染 →': ('Start →', '開始する →'),
    '更多 AI 應用': ('More AI Tools', 'その他の AI 機能'),
    'AI 配石推薦、多材質並排比較、空間風格分析等更多功能持續開發中，讓循環石材的設計應用更完整。敬請期待。':
        ('Stone recommendations, side-by-side material comparison and space style analysis are in development. Coming soon.',
         '石材レコメンド、複数マテリアルの比較、空間スタイル分析などを開発中です。ご期待ください。'),
    '開發中': ('In development', '開発中'),
    '使用 AI 工具需先登入會員（保護運算資源）；瀏覽功能無需登入。':
        ('Sign in to use the AI tools (to protect compute resources). Browsing needs no account.',
         'AI ツールのご利用には会員登録が必要です（計算資源保護のため）。閲覧は登録不要です。'),
    'AI 設計工具': ('AI Design Tools', 'AI デザインツール'),
    'AI 視覺搜尋': ('AI Visual Search', 'AI ビジュアル検索'),
    'AI 功能尚未啟用': ('AI features not enabled', 'AI 機能は未設定です'),

    # ══ 材質模擬 / 設計工具頁 ══
    '材質模擬 — AI 設計工具 — ReStone': ('Material Simulation — AI Design Tools — ReStone',
                                          'マテリアル合成 — AI デザインツール — ReStone'),
    '上傳設計圖 → 圈選要替換的區域（牆面 / 桌面 / 地板）→ 從石材庫挑材料 → AI 一鍵合成':
        ('Upload a design → brush the area to replace (wall / worktop / floor) → pick a stone → AI composites it',
         'デザイン画をアップロード → 置き換える範囲（壁・天板・床）を指定 → 石材を選択 → AI が合成'),
    '上傳設計圖並圈選要替換的區域': ('Upload a design and brush the area to replace',
                                     'デザイン画をアップロードし置き換える範囲を指定'),
    '點此選擇 / 拖曳上傳設計圖': ('Click or drag to upload a design', 'クリックまたはドラッグでデザイン画をアップロード'),
    '用筆刷塗選牆面、家具桌面或產品表面': ('Brush over a wall, tabletop or product surface',
                                           'ブラシで壁・天板・製品表面を塗ってください'),
    '筆刷大小': ('Brush size', 'ブラシサイズ'),
    '清除筆跡': ('Clear brush', 'ブラシをクリア'),
    '↻ 重新上傳': ('↻ Re-upload', '↻ 再アップロード'),
    '選擇要套用的石材': ('Choose a stone to apply', '適用する石材を選択'),
    '選擇循環石材': ('Choose circular stone', '循環石材を選択'),
    '套用石材': ('Apply stone', '石材を適用'),
    '設計生成': ('Generate design', 'デザイン生成'),
    'AI 合成結果': ('AI result', 'AI 合成結果'),
    'AI 合成設計': ('AI composite design', 'AI 合成デザイン'),
    '模擬結果': ('Simulation result', 'シミュレーション結果'),
    '渲染結果': ('Render result', 'レンダリング結果'),
    '↓ 下載': ('↓ Download', '↓ ダウンロード'),
    '↻ 還原': ('↻ Reset', '↻ 元に戻す'),
    '請先登入會員': ('Please sign in first', 'まずログインしてください'),
    '才能使用。': ('to use this feature.', 'をご利用ください。'),
    '⚠ 此功能需要 Gemini（尚未設定 GEMINI_API_KEY），目前無法使用。':
        ('⚠ This feature requires Gemini (GEMINI_API_KEY is not set) and is currently unavailable.',
         '⚠ この機能には Gemini が必要です（GEMINI_API_KEY 未設定）。現在ご利用いただけません。'),
    '。請先在 Railway 設定環境變數': ('. Please set the environment variable on Railway',
                                       '。Railway で環境変数を設定してください'),
    '，平台會自動重啟並開通此功能。': (', the platform will restart automatically and enable this feature.',
                                       '。プラットフォームが自動的に再起動し、この機能が有効になります。'),

    # ══ 牆面模擬 ══
    '牆面模擬 — ReStone': ('Wall Simulation — ReStone', 'ウォールシミュレーション — ReStone'),
    '點選牆面四角 → 選循環石材 → 輸入牆面尺寸 → 透視與比例正確的即時模擬（免費・秒出圖）':
        ('Mark the wall’s four corners → pick a stone → enter wall size → instant simulation with correct '
         'perspective and scale (free, seconds)',
         '壁の四隅を指定 → 石材を選択 → 壁寸法を入力 → 正しい遠近・比率で即時シミュレーション（無料・数秒）'),
    '上傳空間照片，依序點選牆面四個角': ('Upload a room photo, then mark the wall’s four corners in order',
                                         '空間写真をアップロードし、壁の四隅を順に指定'),
    '點擊或拖曳上傳室內空間照片': ('Click or drag to upload a room photo', 'クリックまたはドラッグで空間写真をアップロード'),
    '請點選牆面的': ('Please mark the wall’s', '次の角をタップ：'),
    '① 左上角': ('① top-left corner', '① 左上'),
    '↻ 重設角點': ('↻ Reset corners', '↻ 四隅をリセット'),
    '選石材・輸入牆面尺寸': ('Pick stone · enter wall size', '石材を選択・壁寸法を入力'),
    '牆面寬度（cm）': ('Wall width (cm)', '壁の幅（cm）'),
    '牆面高度（cm）': ('Wall height (cm)', '壁の高さ（cm）'),
    '顯示石材拼縫線（更真實，並呈現分割計畫）':
        ('Show joint lines (more realistic, and shows the tiling plan)',
         '目地線を表示（よりリアルで割付計画も確認可能）'),
    '依牆面與石材的實際尺寸計算拼貼比例，並以透視投影貼合四角——比例與透視皆為幾何精準。若牆前有家具遮擋，可在結果使用「AI 擬真強化」修正。':
        ('Tiling is computed from the real wall and stone dimensions and mapped onto the four corners by '
         'perspective projection — scale and perspective are geometrically exact. If furniture blocks the wall, '
         'use “AI photoreal enhance” on the result.',
         '壁と石材の実寸から割付比率を算出し、透視投影で四隅に貼り付けます（比率・遠近とも幾何学的に正確）。'
         '壁の前に家具がある場合は、結果に「AI フォトリアル強化」をご利用ください。'),

    # ══ 草圖渲染 ══
    '草圖渲染 — ReStone': ('Sketch Rendering — ReStone', 'スケッチレンダリング — ReStone'),
    '草圖渲染：把概念變成循環石材產品': ('Sketch Rendering: turn concepts into circular stone products',
                                         'スケッチレンダリング：コンセプトを循環石材製品へ'),
    '上傳設計草圖 → 選一塊循環石材 → 補一句描述 → AI 生成寫實產品渲染圖':
        ('Upload a sketch → pick a stone → add a description → AI generates a photoreal product render',
         'スケッチをアップロード → 石材を選択 → 説明を追加 → AI がリアルな製品レンダリングを生成'),
    '上傳設計草圖': ('Upload sketch', 'スケッチをアップロード'),
    '點擊或拖曳上傳草圖': ('Click or drag to upload a sketch', 'クリックまたはドラッグでスケッチをアップロード'),
    '手繪線稿、概念圖皆可（JPG / PNG / HEIC）': ('Hand sketches or concept art (JPG / PNG / HEIC)',
                                                  '手描き線画・コンセプト画（JPG / PNG / HEIC）'),
    '草圖預覽': ('Sketch preview', 'スケッチプレビュー'),
    '產品類型 / 補充描述（選填，但建議填）': ('Product type / description (optional, recommended)',
                                              '製品タイプ・補足説明（任意・推奨）'),
    '例：方正極簡邊桌、圓形吊燈底座、洗手檯面…':
        ('e.g. minimal square side table, round pendant lamp base, washbasin top…',
         '例：ミニマルな角形サイドテーブル、円形ペンダント照明のベース、洗面カウンター…'),
    '描述越具體，AI 越能抓對造型與風格。': ('The more specific the description, the better AI matches form and style.',
                                            '説明が具体的なほど、AI が形状とスタイルを正確に再現します。'),

    # ══ 以圖搜圖 ══
    '以圖搜圖 — ReStone': ('Image Search — ReStone', '画像検索 — ReStone'),
    '上傳一張參考圖片，AI 將為你在資料庫中找出紋理與色彩最相似的石材':
        ('Upload a reference photo and AI will find the stones with the closest texture and colour',
         '参考画像をアップロードすると、AI がテクスチャと色が最も近い石材を探します'),
    '點擊或拖曳上傳參考圖片': ('Click or drag to upload a reference photo',
                               'クリックまたはドラッグで参考画像をアップロード'),
    '支援 JPG／PNG／HEIC（iPhone）／GIF／WEBP，最大 32MB':
        ('JPG / PNG / HEIC (iPhone) / GIF / WEBP, up to 32MB', 'JPG／PNG／HEIC（iPhone）／GIF／WEBP、最大 32MB'),
    '支援 JPG、PNG、HEIC（iPhone）、GIF、WEBP，最大 32MB':
        ('JPG, PNG, HEIC (iPhone), GIF, WEBP, up to 32MB', 'JPG、PNG、HEIC（iPhone）、GIF、WEBP、最大 32MB'),
    '在圖片上': ('On the image, ', '画像上で'),   # 結尾空格：後面緊接粗體文字
    '拖曳框出石材區域': ('drag to frame the stone area', 'ドラッグで石材の範囲を囲む'),
    '，只比對框內（避免背景干擾）': (' — only the framed area is matched (avoids background interference)',
                                     ' — 枠内のみ照合します（背景の影響を回避）'),
    '清除圈選': ('Clear selection', '選択をクリア'),
    '更換圖片': ('Change image', '画像を変更'),
    '開始搜尋相似石材': ('Search similar stones', '似た石材を検索'),
    '參考圖': ('Reference', '参考画像'),
    '✓ 已排除背景，只比對你圈選的區域': ('✓ Background excluded — only your selected area was matched',
                                          '✓ 背景を除外し、選択範囲のみを照合しました'),
    '偵測到主要色系：': ('Detected dominant colour:', '検出された主要カラー：'),
    '無法判定主色（可能為多彩石材）': ('Dominant colour undetermined (may be multi-coloured stone)',
                                       '主要カラーを判定できません（多色石材の可能性）'),
    'AI 推薦結果': ('AI results', 'AI 検索結果'),
    '⚠有': ('⚠ ', '⚠ '),
    '資料庫中可能尚未為現有石材建立 AI 索引，請通知管理員執行索引':
        ('Some stones may not be AI-indexed yet — please ask the administrator to run indexing',
         '一部の石材が未インデックスの可能性があります。管理者にインデックス実行をご依頼ください'),

    # ══ 石材詳細頁 ══
    '詳細資料': ('Details', '詳細'),
    '基本資訊': ('Basic information', '基本情報'),
    '尺寸規格': ('Dimensions', '寸法'),
    '寬度': ('Width', '幅'),
    '厚度': ('Thickness', '厚さ'),
    '高度 / 長度': ('Height / Length', '高さ・長さ'),
    '高度／長度': ('Height / Length', '高さ・長さ'),
    '尺寸 (cm)': ('Size (cm)', 'サイズ（cm）'),
    '廠商資訊': ('Supplier', 'サプライヤー'),
    '廠商名稱': ('Supplier name', 'サプライヤー名'),
    '廠商': ('Supplier', 'サプライヤー'),
    '顏色標籤': ('Colour tag', 'カラータグ'),
    '顏色': ('Colour', 'カラー'),
    '單價': ('Unit price', '単価'),
    '目前庫存': ('In stock', '在庫'),
    '庫存數量': ('Stock quantity', '在庫数'),
    '庫存與價格': ('Stock & price', '在庫と価格'),
    '備註說明': ('Notes', '備考'),
    '備註': ('Notes', '備考'),
    '點擊放大': ('Click to enlarge', 'クリックで拡大'),
    '點擊任意處關閉 · 按 ESC 離開': ('Click anywhere to close · press ESC to exit',
                                     'どこかをクリックで閉じる · ESC で終了'),
    '套用到我的設計': ('Apply to my design', 'マイデザインに適用'),
    '將此石材紋理套用到你的設計圖（牆面、桌面、產品表面）。':
        ('Apply this stone’s texture to your design (wall, worktop, product surface).',
         'この石材のテクスチャをデザインに適用（壁・天板・製品表面）。'),
    '上傳室內 / 家具 / 產品設計圖，用筆刷圈選牆面、桌面或表面區域，AI 會用此石材紋理自動合成新圖。':
        ('Upload an interior, furniture or product design, brush the wall, worktop or surface area, '
         'and AI composites a new image using this stone’s texture.',
         'インテリア・家具・製品のデザイン画をアップロードし、壁・天板・表面をブラシで指定すると、'
         'AI がこの石材のテクスチャで新しい画像を合成します。'),
    '開啟 AI 設計工具 →': ('Open AI Design Tools →', 'AI デザインツールを開く →'),
    '會員專屬': ('Members only', '会員限定'),
    '用量計算機': ('Quantity Calculator', '数量計算'),
    '輸入您的空間尺寸，自動計算所需石材數量與預估費用':
        ('Enter your space dimensions to calculate the stone quantity and estimated cost',
         '空間の寸法を入力すると、必要な石材数量と概算費用を自動計算します'),
    '空間長度（公尺）': ('Room length (m)', '空間の長さ（m）'),
    '空間寬度（公尺）': ('Room width (m)', '空間の幅（m）'),
    '損耗率（%）': ('Waste allowance (%)', 'ロス率（%）'),
    '10%（一般）': ('10% (standard)', '10%（標準）'),
    '15%（複雜空間）': ('15% (complex space)', '15%（複雑な空間）'),
    '20%（異形切割）': ('20% (irregular cuts)', '20%（異形カット）'),
    '需鋪面積（m²）': ('Area to cover (m²)', '施工面積（m²）'),
    '預估費用（NT$）': ('Estimated cost (NT$)', '概算費用（NT$）'),
    '永續貢獻': ('Sustainability Impact', 'サステナビリティ貢献'),
    'SUSTAINABILITY IMPACT · 選用此循環石材，您將：':
        ('SUSTAINABILITY IMPACT · By choosing this circular stone, you avoid:',
         'SUSTAINABILITY IMPACT · この循環石材を選ぶことで：'),
    '的二氧化碳排放（相當於以下情境）': ('of CO₂ emissions (equivalent to)', 'の CO₂ 排出を削減（以下に相当）'),
    '棵成樹一年吸收量': ('mature trees’ annual absorption', '本の成木が 1 年に吸収する量'),
    '公里汽車排放量': ('km of car emissions', 'km の自動車排出量'),
    '度電的排放量': ('kWh of electricity emissions', 'kWh の電力排出量'),
    '計算基準：': ('Basis:', '算定基準：'),
    '（University of Bath, UK）· 範疇：cradle-to-gate（開採至出廠）· 換算係數：1 棵成樹/年 ≈ 21 kg CO₂、汽車 ≈ 120 g/km、台電 ≈ 0.495 kg/kWh':
        ('(University of Bath, UK) · Scope: cradle-to-gate · Factors: 1 mature tree/yr ≈ 21 kg CO₂, '
         'car ≈ 120 g/km, Taipower ≈ 0.495 kg/kWh',
         '（University of Bath, UK）· 範囲：cradle-to-gate · 換算係数：成木 1 本/年 ≈ 21 kg CO₂、'
         '自動車 ≈ 120 g/km、台湾電力 ≈ 0.495 kg/kWh'),
    '聯繫廠商 / 詢問訂購': ('Contact supplier / Enquire', 'サプライヤーへ問い合わせ'),
    '詢問訂購為會員專屬功能': ('Enquiries are a members-only feature', 'お問い合わせは会員限定機能です'),
    '登入會員即可向廠商詢問此石材，並可在「我的帳號」中追蹤詢問狀態':
        ('Sign in to enquire about this stone and track your enquiry status in “My Account”',
         'ログインすると、この石材について問い合わせでき、「マイアカウント」で状況を確認できます'),
    '登入會員 →': ('Sign in →', 'ログイン →'),
    '註冊新帳號': ('Create an account', '新規アカウント作成'),
    '訊息內容': ('Message', 'メッセージ'),
    '請描述您的需求、使用場景或其他問題...':
        ('Describe your requirements, intended use or any questions…',
         'ご要望・用途・ご質問などをご記入ください…'),
    '詢問數量': ('Quantity', '数量'),
    '送出詢問': ('Send enquiry', '問い合わせを送信'),
    '你可能也喜歡': ('You may also like', 'こちらもおすすめ'),

    # ══ 會員：登入 / 註冊 / 帳號 ══
    '會員登入 — ReStone': ('Member Sign In — ReStone', '会員ログイン — ReStone'),
    '會員登入': ('Member Sign In', '会員ログイン'),
    '登入以查看您的詢問紀錄': ('Sign in to view your enquiries', 'ログインしてお問い合わせ履歴を確認'),
    '會員註冊': ('Create Account', '会員登録'),
    '會員註冊 — ReStone': ('Create Account — ReStone', '会員登録 — ReStone'),
    '建立帳號': ('Create account', 'アカウント作成'),
    '建立帳號以追蹤您的詢問紀錄': ('Create an account to track your enquiries',
                                   'アカウントを作成してお問い合わせを管理'),
    '已有帳號？': ('Already have an account?', 'すでにアカウントをお持ちですか？'),
    '還沒有帳號？立即註冊 →': ('No account yet? Sign up →', 'アカウントをお持ちでない方はこちら →'),
    '密碼': ('Password', 'パスワード'),
    '輸入密碼': ('Enter password', 'パスワードを入力'),
    '確認密碼': ('Confirm password', 'パスワード（確認）'),
    '再次輸入密碼': ('Re-enter password', 'パスワードを再入力'),
    '至少 6 個字元': ('At least 6 characters', '6 文字以上'),
    '或': ('or', 'または'),
    '姓名': ('Name', 'お名前'),
    '姓名 *': ('Name *', 'お名前 *'),
    '您的姓名': ('Your name', 'お名前'),
    '電話': ('Phone', '電話番号'),
    '公司名稱': ('Company', '会社名'),
    '聯絡地址': ('Address', 'ご住所'),
    '聯絡人': ('Contact', 'ご担当者'),
    '帳號': ('Account', 'アカウント'),
    '選填': ('Optional', '任意'),
    '（選填）': ('(optional)', '（任意）'),
    '例：0912-345-678': ('e.g. 0912-345-678', '例：0912-345-678'),
    '例：○○設計工作室': ('e.g. ABC Design Studio', '例：○○デザインスタジオ'),
    '例：台北市信義區○○路○段○號': ('e.g. No. 1, Sec. 1, XX Rd., Xinyi Dist., Taipei',
                                     '例：台北市信義区○○路○段○号'),
    'Email（登入帳號，不可修改）': ('Email (sign-in ID, cannot be changed)',
                                    'メール（ログイン ID・変更不可）'),
    '基本資料': ('Profile', '基本情報'),
    '儲存變更': ('Save changes', '変更を保存'),
    '我的帳號 — ReStone': ('My Account — ReStone', 'マイアカウント — ReStone'),
    '我的設計 — ReStone': ('My Designs — ReStone', 'マイデザイン — ReStone'),
    '詢問紀錄': ('Enquiries', 'お問い合わせ履歴'),
    '最近設計': ('Recent designs', '最近のデザイン'),
    '尚無詢問紀錄': ('No enquiries yet', 'お問い合わせはまだありません'),
    '尚無設計紀錄': ('No designs yet', 'デザインはまだありません'),
    '並送出詢問後，紀錄會顯示在這裡': ('once you send an enquiry, it will appear here',
                                       'お問い合わせを送信すると、ここに表示されます'),
    '，用循環石材設計後作品會顯示在這裡': (' — designs made with circular stone will appear here',
                                            ' — 循環石材で制作した作品がここに表示されます'),
    '，用循環石材設計後，作品會自動保存在這裡':
        (' — designs made with circular stone are saved here automatically',
         ' — 循環石材で制作した作品は自動的にここへ保存されます'),
    '提案 PDF': ('Proposal PDF', '提案 PDF'),
    '修改密碼': ('Change password', 'パスワード変更'),
    '目前密碼': ('Current password', '現在のパスワード'),
    '輸入目前密碼': ('Enter current password', '現在のパスワードを入力'),
    '新密碼': ('New password', '新しいパスワード'),
    '確認新密碼': ('Confirm new password', '新しいパスワード（確認）'),
    '再次輸入新密碼': ('Re-enter new password', '新しいパスワードを再入力'),
    '更新密碼': ('Update password', 'パスワードを更新'),

    # ══ 狀態 / 通用 ══
    '狀態': ('Status', 'ステータス'),
    '待回覆': ('Pending', '未対応'),
    '已回覆': ('Replied', '返信済み'),
    '已結案': ('Closed', '完了'),
    '顯示中': ('Visible', '表示中'),
    '已隱藏': ('Hidden', '非表示'),
    '一般': ('Standard', '一般'),
    '身分': ('Tier', '区分'),
    '無限制': ('Unlimited', '無制限'),
    '無限制（全站）': ('Unlimited (site-wide)', '無制限（サイト全体）'),
    '今日生圖': ('Today’s generations', '本日の生成数'),
    '設為 VIP': ('Make VIP', 'VIP にする'),
    '改回一般': ('Revert to standard', '一般に戻す'),
    '共': ('Total', '合計'),
    '件': ('items', '件'),
    '片': ('pcs', '枚'),
    '塊': ('pcs', '個'),
    '張': ('images', '枚'),
    '噸': ('t', 't'),
    '坪': ('ping', '坪'),
    '石材': ('Stone', '石材'),
    '圖片': ('Image', '画像'),
    '預覽': ('Preview', 'プレビュー'),
    '數量': ('Quantity', '数量'),
    '單位': ('Unit', '単位'),
    '時間': ('Time', '日時'),
    '更新': ('Update', '更新'),
    '更新時間': ('Updated', '更新日時'),
    '註冊時間': ('Registered', '登録日'),
    '標題': ('Title', 'タイトル'),
    '內容': ('Content', '内容'),
    '公告': ('Announcement', 'お知らせ'),
    '訊息': ('Message', 'メッセージ'),
    '情境': ('Scene', 'シーン'),
    '操作': ('Actions', '操作'),
    '編輯': ('Edit', '編集'),
    '刪除': ('Delete', '削除'),
    '取消': ('Cancel', 'キャンセル'),
    '取消編輯': ('Cancel editing', '編集をキャンセル'),
    '確認刪除': ('Confirm delete', '削除を確認'),
    '管理': ('Manage', '管理'),
    '系統': ('System', 'システム'),
    '管理員': ('Administrator', '管理者'),

    # ══ 後台 ══
    '管理後台 — ReStone 循環石材服務平台': ('Admin — ReStone Circular Stone Platform',
                                             '管理画面 — ReStone 循環石材プラットフォーム'),
    '管理員登入 — ReStone 循環石材服務平台': ('Admin Sign In — ReStone Circular Stone Platform',
                                               '管理者ログイン — ReStone 循環石材プラットフォーム'),
    '修改密碼 — ReStone 循環石材服務平台': ('Change Password — ReStone Circular Stone Platform',
                                             'パスワード変更 — ReStone 循環石材プラットフォーム'),
    '請輸入您的管理員帳號與密碼': ('Enter your admin username and password',
                                   '管理者アカウントとパスワードを入力してください'),
    '輸入管理員帳號': ('Enter admin username', '管理者アカウントを入力'),
    '登入後台': ('Sign in to admin', '管理画面へログイン'),
    '修改管理員密碼': ('Change admin password', '管理者パスワードの変更'),
    '石材管理': ('Stones', '石材管理'),
    '石材庫存管理': ('Stone inventory', '石材在庫管理'),
    '石材項目總數': ('Total stones', '石材点数'),
    '所有石材庫存': ('All stone inventory', 'すべての石材在庫'),
    '新增石材': ('Add stone', '石材を追加'),
    '＋ 新增石材': ('+ Add stone', '＋ 石材を追加'),
    '詢問管理': ('Enquiries', 'お問い合わせ管理'),
    '詢問管理 — ReStone': ('Enquiries — ReStone', 'お問い合わせ管理 — ReStone'),
    '所有詢問記錄': ('All enquiries', 'すべてのお問い合わせ'),
    '目前尚無詢問記錄': ('No enquiries yet', 'お問い合わせはまだありません'),
    '會員管理': ('Members', '会員管理'),
    '會員管理 — ReStone': ('Members — ReStone', '会員管理 — ReStone'),
    '所有會員': ('All members', 'すべての会員'),
    '尚無會員資料': ('No members yet', '会員はまだいません'),
    '最新消息 — ReStone 管理後台': ('News — ReStone Admin', 'お知らせ — ReStone 管理画面'),
    '所有公告': ('All announcements', 'すべてのお知らせ'),
    '顯示於首頁': ('Show on homepage', 'トップページに表示'),
    '公告內容，可換行分段…': ('Announcement content, line breaks allowed…', 'お知らせ本文（改行可）…'),
    '例如：本平台將於文博會展出': ('e.g. We will exhibit at the Creative Expo',
                                   '例：文化創意博覧会に出展します'),
    '尚無任何公告，使用上方表單新增第一則。': ('No announcements yet — use the form above to add the first one.',
                                                'お知らせはまだありません。上のフォームから追加してください。'),
    '首頁只顯示「已勾選顯示」的最新 3 則，置頂者優先。':
        ('The homepage shows the 3 most recent visible announcements, pinned ones first.',
         'トップページには「表示」にした最新 3 件を表示します（固定分を優先）。'),
    '前台預覽': ('View site', '公開サイト'),
    '↓ 匯出 Excel': ('↓ Export Excel', '↓ Excel 書き出し'),
    '重新索引照片': ('Re-index photos', '写真を再インデックス'),
    '為現有照片建立 AI 索引': ('Build AI index for existing photos', '既存写真の AI インデックスを作成'),
    '用 AI 重新分析照片': ('Re-analyse photos with AI', 'AI で写真を再分析'),
    '重新分析 Prompt': ('Re-analyse prompts', 'プロンプトを再分析'),
    '用視覺 AI 逐張重寫所有石材的 Prompt': ('Rewrite every stone’s prompt with vision AI',
                                             'ビジョン AI で全石材のプロンプトを書き換え'),
    '沒有可分析的石材（需有照片）': ('No stones to analyse (photos required)',
                                     '分析できる石材がありません（写真が必要）'),
    '目前沒有石材資料，請點擊「新增石材」開始建立庫存':
        ('No stones yet — click “Add stone” to start building your inventory',
         '石材データがありません。「石材を追加」から在庫を登録してください'),
    '確定要刪除這筆石材資料嗎？此操作無法復原。':
        ('Delete this stone? This cannot be undone.', 'この石材を削除しますか？この操作は取り消せません。'),
    '透過後台管理石材庫存、新增與編輯石材資料，讓設計師隨時掌握最新庫存現況。':
        ('Manage stone inventory here — add and edit stones so designers always see current stock.',
         '管理画面で石材在庫を管理し、デザイナーが常に最新の在庫を確認できるようにします。'),
    '展覽圖庫': ('Showcase Gallery', '展示ギャラリー'),
    '展覽圖庫 — ReStone 後台': ('Showcase Gallery — ReStone Admin', '展示ギャラリー — ReStone 管理画面'),
    '展覽圖': ('Showcase image', '展示画像'),
    '已生成圖庫': ('Generated gallery', '生成済みギャラリー'),
    '生成計畫（5 個情境）': ('Generation plan (5 scenes)', '生成プラン（5 シーン）'),
    '生成這張': ('Generate', 'この画像を生成'),
    '全部生成（5 張）': ('Generate all (5)', 'すべて生成（5 枚）'),
    '用 Gemini 生成展覽用情境圖': ('Generate exhibition scenes with Gemini', 'Gemini で展示用シーンを生成'),
    '用 Gemini 把每塊石材直接生成在精緻的空間情境中（免遮罩、一步到位），供 iPad 展覽模式秒選秒看。':
        ('Gemini places each stone directly into a refined interior scene (no masking, one step), '
         'ready for instant browsing in iPad exhibition mode.',
         'Gemini が各石材を洗練された空間シーンに直接生成します（マスク不要・ワンステップ）。'
         'iPad 展示モードで瞬時に閲覧できます。'),
    '每張間隔約 15 秒以符合速率；生成成功會即時出現在下方圖庫。每張約 NT$1.2。':
        ('About 15 seconds between images to respect rate limits; results appear in the gallery below. '
         'Roughly NT$1.2 per image.',
         'レート制限のため約 15 秒間隔で生成します。成功した画像は下のギャラリーに表示されます。1 枚あたり約 NT$1.2。'),
    '尚未生成任何展覽圖，點上方「全部生成」開始。':
        ('No showcase images yet — click “Generate all” above to start.',
         '展示画像はまだありません。上の「すべて生成」から開始してください。'),
    '⚠ 尚未設定 GEMINI_API_KEY，無法生成。請先在 Railway 設定金鑰。':
        ('⚠ GEMINI_API_KEY is not set, so generation is unavailable. Please set the key on Railway.',
         '⚠ GEMINI_API_KEY が未設定のため生成できません。Railway でキーを設定してください。'),

    # ══ 石材表單 ══
    '石材種類 / 分類': ('Stone type / category', '石材の種類・分類'),
    '請選擇石材種類': ('Select a stone type', '石材の種類を選択'),
    '石材名稱 / 品名': ('Stone name', '石材名'),
    '輸入此石材的具體品名（前台會顯示為主標題）':
        ('Enter this stone’s specific name (shown as the main title on the public site)',
         'この石材の具体的な名称を入力（公開サイトの見出しに表示されます）'),
    '（選填，例：帝諾、卡拉拉白、銀狐）': ('(optional, e.g. Dino, Carrara White, Silver Fox)',
                                          '（任意、例：ディーノ、カラーラホワイト、シルバーフォックス）'),
    '請選擇廠商': ('Select a supplier', 'サプライヤーを選択'),
    '石材的特色、狀況說明、注意事項...': ('Characteristics, condition, things to note…',
                                          '特徴・状態・注意事項など…'),
    '選擇顏色': ('Choose colour', 'カラーを選択'),
    '（不選則由 AI 從照片自動偵測）': ('(leave blank and AI will detect it from the photo)',
                                       '（未選択の場合、AI が写真から自動判定します）'),
    'AI 設計工具 Prompt': ('AI design tool prompt', 'AI デザインツール用プロンプト'),
    '（設計工具合成時使用）': ('(used when compositing in the design tools)',
                              '（デザインツールでの合成時に使用）'),
    '新增石材時若留空，系統會自動用視覺 AI 分析照片寫描述。也可手動編輯，例：「':
        ('Leave blank when adding and the system will describe the photo using vision AI. '
         'You may also edit it manually, e.g. “',
         '未入力の場合、ビジョン AI が写真から自動で記述します。手動編集も可能です。例：「'),
    '例：deep green serpentine with white veining, polished glossy surface':
        ('e.g. deep green serpentine with white veining, polished glossy surface',
         '例：deep green serpentine with white veining, polished glossy surface'),
    '石材照片（最多 3 張）': ('Stone photos (up to 3)', '石材写真（最大 3 枚）'),
    '（建議上傳）': ('(recommended)', '（推奨）'),
    '目前照片（上傳新照片將取代此圖）': ('Current photo (uploading a new one replaces it)',
                                         '現在の写真（新規アップロードで置き換わります）'),
    '支援 PNG / JPG / HEIC（iPhone），建議 1024×1024 以上':
        ('PNG / JPG / HEIC (iPhone), 1024×1024 or larger recommended',
         'PNG / JPG / HEIC（iPhone）、1024×1024 以上を推奨'),
    'JPG / PNG / HEIC（iPhone 照片可直接上傳）': ('JPG / PNG / HEIC (iPhone photos supported)',
                                                  'JPG / PNG / HEIC（iPhone の写真もそのまま可）'),
    '(NT$，留空表示洽詢)': ('(NT$, leave blank for “on request”)', '（NT$、空欄で「お問い合わせ」）'),
    '（可即時編輯）': ('(editable)', '（編集可能）'),
    '例：2': ('e.g. 2', '例：2'),
    '例：10': ('e.g. 10', '例：10'),
    '例：50': ('e.g. 50', '例：50'),
    '例：60': ('e.g. 60', '例：60'),
    '例：120': ('e.g. 120', '例：120'),
    '例：1200': ('e.g. 1200', '例：1200'),
    '例：4.0': ('e.g. 4.0', '例：4.0'),
    '例：5.0': ('e.g. 5.0', '例：5.0'),
    '筆石材仍使用舊版比對方式（準確率較低）。 管理員可至後台點擊「重新索引照片」升級為新版視覺特徵，搜尋會更準。':
        ('stones still use the old matching method (lower accuracy). An administrator can click '
         '“Re-index photos” in the admin area to upgrade them to the new visual features for better results.',
         '件の石材が旧方式で照合されています（精度が低め）。管理画面の「写真を再インデックス」で'
         '新しい視覚特徴に更新すると、検索精度が向上します。'),
    '筆石材尚未建立 AI 索引（不會出現在搜尋結果中）。 管理員可至後台點擊「重新索引照片」一次性處理所有舊資料。':
        ('stones are not AI-indexed yet (they will not appear in search results). An administrator can '
         'click “Re-index photos” in the admin area to process all existing data at once.',
         '件の石材が未インデックスです（検索結果に表示されません）。管理画面の「写真を再インデックス」で'
         '既存データを一括処理できます。'),
    # ══ 補完：夾變數的句子、JS 訊息、Python 提示（第二輪多語化）══
    '共 {n} 筆': ('{n} total', '全 {n} 件'),
    '共 {n} 位': ('{n} members', '全 {n} 名'),
    '共 {n} 則': ('{n} total', '全 {n} 件'),
    '顯示': ('Show', '表示'),
    '隱藏': ('Hide', '非表示'),
    '失敗': ('Failed', '失敗'),
    '未知錯誤': ('Unknown error', '不明なエラー'),
    '網路錯誤': ('Network error', 'ネットワークエラー'),
    '網路錯誤：': ('Network error: ', 'ネットワークエラー：'),
    '網路請求失敗：': ('Network request failed: ', '通信に失敗しました：'),
    '未回傳影像': ('no image returned', '画像が返されませんでした'),
    '未填寫': ('not specified', '未記入'),
    '照片 {n}': ('Photo {n}', '写真 {n}'),
    '處理中…': ('Processing…', '処理中…'),
    '處理中...': ('Processing…', '処理中…'),
    '開啟原圖': ('Open image', '元画像を開く'),
    '↓ 下載圖片': ('↓ Download image', '↓ 画像をダウンロード'),
    '設計提案 PDF': ('Design proposal PDF', 'デザイン提案 PDF'),
    '石材合成': ('Stone composite', '石材合成'),
    'iPhone HEIC 格式正在轉檔': ('Converting iPhone HEIC photo', 'iPhone の HEIC 写真を変換中'),
    'iPhone 照片格式轉換失敗：': ('Could not convert the iPhone photo: ', 'iPhone 写真の変換に失敗しました：'),
    '伺服器回應異常（HTTP {status}）': ('Unexpected server response (HTTP {status})', 'サーバーの応答が異常です（HTTP {status}）'),
    '伺服器回應異常（HTTP {status}）：': ('Unexpected server response (HTTP {status}): ', 'サーバーの応答が異常です（HTTP {status}）：'),
    '伺服器處理逾時或發生錯誤，請稍候再試一次': ('The server timed out or hit an error — please try again shortly', 'サーバーがタイムアウトしたかエラーが発生しました。しばらくしてから再度お試しください'),
    '伺服器錯誤 HTTP {status}': ('Server error HTTP {status}', 'サーバーエラー HTTP {status}'),
    '搜尋「{q}」：': ('Search “{q}”: ', '「{q}」の検索結果：'),
    '{n} 筆結果': ('{n} results', '{n} 件'),
    '顯示全部': ('Showing all', '全'),
    '筆石材': ('stones', '件の石材を表示'),
    '減碳 {v} CO₂e': ('Saves {v} CO₂e', 'CO₂e {v} 削減'),
    '{unit} 庫存': ('{unit} in stock', '{unit} 在庫'),
    '找不到符合的石材': ('No matching stones', '該当する石材が見つかりません'),
    '尚無石材資料': ('No stones yet', '石材データはまだありません'),
    '請嘗試其他搜尋條件': ('Try different search terms', '別の条件で検索してください'),
    '請等待管理員新增庫存': ('Please check back once stock has been added', '在庫が登録されるまでお待ちください'),
    '將「{name}」套用到你的設計圖': ('Apply “{name}” to your design', '「{name}」をデザインに適用'),
    '需要數量（{unit}）': ('Quantity needed ({unit})', '必要数量（{unit}）'),
    '減少 {v}': ('{v}', '{v}'),
    '庫存 {n}': ('Stock {n}', '在庫 {n}'),
    '石材尺寸 {w}×{h} cm，含 {waste}% 損耗，共需 {qty} {unit}': ('Stone size {w}×{h} cm, incl. {waste}% waste — {qty} {unit} needed', '石材サイズ {w}×{h} cm、ロス {waste}% を含め、計 {qty} {unit} 必要です'),
    '圈選範圍分析結果': ('Selected-area analysis', '選択範囲の解析結果'),
    '參考圖片分析結果': ('Reference image analysis', '参考画像の解析結果'),
    '找到 {n} 筆相似石材（依相似度排序）': ('{n} similar stones found (sorted by similarity)', '似た石材が {n} 件見つかりました（類似度順）'),
    '開始 AI 搜尋': ('Start AI search', 'AI 検索を開始'),
    'AI 分析中...': ('Analysing…', 'AI 解析中…'),
    '已圈選': ('Selected', '画面の'),
    '約 {pct}%': ('about {pct}%', '約 {pct}%'),
    '的畫面範圍，只比對框內區域': (' of the image — only this area is matched', 'を選択。枠内のみ照合します'),
    '詢問數量：{n}': ('Quantity: {n}', '数量：{n}'),
    '送出時間：{d}': ('Sent: {d}', '送信日：{d}'),
    '最新 {n} 張': ('Latest {n}', '最新 {n} 件'),
    '{name} 透過 AI 設計工具合成的作品，方便回顧設計發展、做出決定。': ('Designs {name} created with the AI design tools — review how ideas developed and decide with confidence.', '{name} さんが AI デザインツールで作成した作品です。デザインの変遷を振り返り、判断に役立ててください。'),
    '系統自動保留最近 {limit} 張（目前 {n} 張）；超過時最舊的會自動清除': ('The latest {limit} are kept automatically (currently {n}); older ones are removed beyond that', '最新 {limit} 件まで自動保存されます（現在 {n} 件）。それを超えると古いものから削除されます'),
    '確定刪除這張設計嗎？刪除後無法復原。': ('Delete this design? This cannot be undone.', 'このデザインを削除しますか？元に戻せません。'),
    'AI 正在合成中… 通常需要 15–40 秒': ('AI is compositing… usually 15–40 seconds', 'AI 合成中… 通常 15〜40 秒かかります'),
    '準備中': ('Preparing', '準備中'),
    '匯出遮罩': ('Exporting mask', 'マスクを書き出し中'),
    '遮罩匯出失敗（請確認有塗選區域）': ('Could not export the mask (make sure you brushed an area)', 'マスクを書き出せませんでした（範囲を塗ったか確認してください）'),
    '組合表單': ('Preparing request', 'リクエストを準備中'),
    '傳送請求': ('Sending request', 'リクエストを送信中'),
    '解析回應': ('Reading response', '応答を解析中'),
    '驗證圖片網址': ('Checking image URL', '画像 URL を確認中'),
    '回傳的圖片網址無效：': ('Invalid image URL returned: ', '返された画像 URL が無効です：'),
    '顯示結果': ('Showing result', '結果を表示中'),
    '✓ 已自動存入「我的設計」': ('✓ Saved to “My Designs”', '✓「マイデザイン」に自動保存しました'),
    '引擎：Gemini 參考圖合成（使用實際石材照片）': ('Engine: Gemini reference compositing (using the actual stone photo)', 'エンジン：Gemini 参照合成（実際の石材写真を使用）'),
    '引擎：Flux（文字生成）': ('Engine: Flux (text-to-image)', 'エンジン：Flux（テキスト生成）'),
    '\u3000｜ Gemini 未啟用原因：': ('  |  Gemini unavailable: ', '\u3000｜ Gemini を使えなかった理由：'),
    '使用石材 · ': ('Stone used · ', '使用した石材 · '),
    'Gemini 參考圖合成（使用實際石材照片）': ('Gemini reference compositing (using the actual stone photo)', 'Gemini 参照合成（実際の石材写真を使用）'),
    'Gemini 直接參考此石材照片合成': ('Composited by Gemini directly from this stone’s photo', 'Gemini がこの石材の写真を直接参照して合成'),
    'Gemini 合成失敗：{e}': ('Gemini compositing failed: {e}', 'Gemini 合成に失敗しました：{e}'),
    'AI 合成失敗：{e}': ('AI compositing failed: {e}', 'AI 合成に失敗しました：{e}'),
    'AI 渲染中… 通常需要 15–30 秒': ('AI is rendering… usually 15–30 seconds', 'AI レンダリング中… 通常 15〜30 秒かかります'),
    '產品渲染圖': ('Product render', '製品レンダリング'),
    '✓ 已自動存入「我的設計」 · 引擎：Gemini 草圖渲染': ('✓ Saved to “My Designs” · Engine: Gemini sketch rendering', '✓「マイデザイン」に自動保存しました · エンジン：Gemini スケッチレンダリング'),
    '草圖渲染（{hint}）': ('Sketch rendering ({hint})', 'スケッチレンダリング（{hint}）'),
    '草圖渲染失敗：{e}': ('Sketch rendering failed: {e}', 'スケッチレンダリングに失敗しました：{e}'),
    '尺寸未填': ('Size not set', 'サイズ未記入'),
    '① 左上': ('① top-left corner', '① 左上'),
    '② 右上': ('② top-right corner', '② 右上'),
    '③ 右下': ('③ bottom-right corner', '③ 右下'),
    '④ 左下': ('④ bottom-left corner', '④ 左下'),
    '✓ 四角完成（可直接拖曳圓點微調）': ('✓ All four corners set (drag the dots to fine-tune)', '✓ 四隅を指定しました（点をドラッグして微調整できます）'),
    '計算透視與拼貼中… 數秒內完成': ('Calculating perspective and tiling… done in seconds', '遠近と割付を計算中… 数秒で完了します'),
    '牆面模擬結果': ('Wall simulation result', 'ウォールシミュレーション結果'),
    '拼貼計畫': ('Tiling plan', '割付計画'),
    '橫 {x} × 直 {y} ＝ {n} 片': ('{x} across × {y} down = {n} pcs', '横 {x} × 縦 {y} ＝ {n} 枚'),
    '石材規格': ('Stone size', '石材サイズ'),
    '庫存檢查': ('Stock check', '在庫チェック'),
    '{n} 片 ✓ 足夠': ('{n} pcs ✓ enough', '{n} 枚 ✓ 足ります'),
    '{n} 片 ⚠ 不足（差 {short} 片）': ('{n} pcs ⚠ short by {short} pcs', '{n} 枚 ⚠ 不足（{short} 枚足りません）'),
    '減碳效益': ('Carbon savings', 'CO₂ 削減効果'),
    '{c} CO₂e ≈ {trees} 棵樹年吸碳': ('{c} CO₂e ≈ {trees} trees’ annual absorption', '{c} CO₂e ≈ 成木 {trees} 本の年間吸収量'),
    'AI 擬真強化': ('AI photoreal enhance', 'AI フォトリアル強化'),
    '✓ 已自動存入「我的設計」（{stone}）· 引擎：本地透視貼合（免費・即時）': ('✓ Saved to “My Designs” ({stone}) · Engine: local perspective mapping (free, instant)', '✓「マイデザイン」に自動保存しました（{stone}）· エンジン：ローカル透視マッピング（無料・即時）'),
    'AI 強化中… 15–40 秒': ('Enhancing with AI… 15–40 s', 'AI 強化中… 15〜40 秒'),
    '✓ 已強化': ('✓ Enhanced', '✓ 強化しました'),
    'AI 強化失敗：': ('AI enhancement failed: ', 'AI 強化に失敗しました：'),
    'AI 強化失敗：{e}': ('AI enhancement failed: {e}', 'AI 強化に失敗しました：{e}'),
    '牆面模擬失敗：{e}': ('Wall simulation failed: {e}', 'ウォールシミュレーションに失敗しました：{e}'),
    '牆面模擬（{w}×{h}m・{x}×{y} 片）': ('Wall simulation ({w}×{h} m · {x}×{y} pcs)', 'ウォールシミュレーション（{w}×{h} m・{x}×{y} 枚）'),
    '・AI 擬真強化': (' · AI photoreal enhance', '・AI フォトリアル強化'),
    '（未填尺寸，估算值）': (' (size not set — estimated)', '（サイズ未記入・推定値）'),
    '歡迎回來，{name}！': ('Welcome back, {name}!', 'おかえりなさい、{name} さん！'),
    '今日 AI 生圖已達上限（每人每日 {n} 張），請明天再試。': ('You have reached today’s AI image limit ({n} per person per day). Please try again tomorrow.', '本日の AI 画像生成の上限（1 日 {n} 枚）に達しました。明日またお試しください。'),
    'PDF 生成失敗：{e}': ('PDF generation failed: {e}', 'PDF の生成に失敗しました：{e}'),
    '≈ {n} 棵樹一年吸收量': ('≈ {n} mature trees’ annual absorption', '≈ 成木 {n} 本の年間吸収量'),
    '將為所有現有石材重新計算 AI 圖片索引（顏色與相似度比對用），可能需要幾秒鐘。是否繼續？': ('This recalculates the AI image index (colour and similarity matching) for all stones and may take a few seconds. Continue?', 'すべての石材の AI 画像インデックス（カラー・類似度照合用）を再計算します。数秒かかる場合があります。続行しますか？'),
    '確定要刪除「{name}」嗎？此操作無法復原。': ('Delete “{name}”? This cannot be undone.', '「{name}」を削除しますか？この操作は取り消せません。'),
    '限速重試多次仍失敗（請考慮為 Replicate 儲值到 $5 以上）': ('Still rate-limited after several retries (consider topping up Replicate to $5 or more)', '何度か再試行しましたが制限が続いています（Replicate の残高を $5 以上にすることをご検討ください）'),
    '將用視覺 AI 逐張重新分析 {n} 張石材照片，每張間隔約 12 秒以符合 Replicate 限速，預計約 {min} 分鐘。期間請勿關閉此頁。是否繼續？': ('Vision AI will re-analyse {n} stone photos one by one, about 12 seconds apart to respect Replicate’s rate limit — roughly {min} minutes. Please keep this page open. Continue?', 'ビジョン AI で石材写真 {n} 枚を 1 枚ずつ再分析します。Replicate の制限に合わせて約 12 秒間隔で実行するため、約 {min} 分かかります。このページを閉じないでください。続行しますか？'),
    '分析中… {i}/{n}': ('Analysing… {i}/{n}', '分析中… {i}/{n}'),
    '重新分析中：{i}/{n}（成功 {ok}、失敗 {fail}）…': ('Re-analysing: {i}/{n} ({ok} succeeded, {fail} failed)…', '再分析中：{i}/{n}（成功 {ok}、失敗 {fail}）…'),
    '石材 #{id}：{reason}': ('Stone #{id}: {reason}', '石材 #{id}：{reason}'),
    ' 重新分析完成：{ok} 成功 / {fail} 失敗': (' Re-analysis complete: {ok} succeeded / {fail} failed', ' 再分析完了：成功 {ok} 件 / 失敗 {fail} 件'),
    '\u3000｜ 失敗原因：{e}': ('  |  Reason: {e}', '\u3000｜ 失敗理由：{e}'),
    '（重新整理頁面即可在各石材看到新描述）': (' (refresh the page to see the new descriptions)', '（ページを再読み込みすると新しい説明が表示されます）'),
    'AI Prompt 重新分析完成：{ok} 成功 / {fail} 失敗': ('AI prompt re-analysis complete: {ok} succeeded / {fail} failed', 'AI プロンプトの再分析完了：成功 {ok} 件 / 失敗 {fail} 件'),
    '找不到照片檔案（{f}）': ('Photo file not found ({f})', '写真ファイルが見つかりません（{f}）'),
    '「一般」會員每日最多生成 {n} 張 AI 圖（材質模擬、草圖渲染、牆面 AI 增強）；「VIP」會員不受數量限制。點「設為 VIP」即可升級，隨時可改回一般。': ('“Standard” members can generate up to {n} AI images per day (material simulation, sketch rendering, AI wall enhancement); “VIP” members have no limit. Click “Make VIP” to upgrade — you can switch back at any time.', '「一般」会員は 1 日最大 {n} 枚の AI 画像を生成できます（マテリアル合成・スケッチレンダリング・壁の AI 強化）。「VIP」会員は無制限です。「VIP にする」で昇格でき、いつでも一般に戻せます。'),
    '已將「{name}」設為 VIP 會員（不限生圖數量）': ('“{name}” is now a VIP member (unlimited AI images)', '「{name}」を VIP 会員にしました（AI 画像生成は無制限）'),
    '已將「{name}」設為一般會員': ('“{name}” is now a standard member', '「{name}」を一般会員にしました'),
    '編輯公告': ('Edit announcement', 'お知らせを編集'),
    '新增公告': ('Add announcement', 'お知らせを追加'),
    '更新公告': ('Update announcement', 'お知らせを更新'),
    '取消置頂': ('Unpin', '固定を解除'),
    '確定刪除這則公告？此動作無法復原。': ('Delete this announcement? This cannot be undone.', 'このお知らせを削除しますか？元に戻せません。'),
    '刪除這張展覽圖？': ('Delete this showcase image?', 'この展示画像を削除しますか？'),
    '限速，等待重試…': ('Rate-limited — waiting to retry…', '制限中。再試行を待っています…'),
    '限速重試多次仍失敗': ('Still rate-limited after several retries', '何度か再試行しましたが制限が続いています'),
    '剛生成': ('just created', '生成したばかり'),
    '生成中…': ('Generating…', '生成中…'),
    '✓ 完成': ('✓ Done', '✓ 完了'),
    '生成中… {i}/{n}（成功 {ok}、失敗 {fail}）': ('Generating… {i}/{n} ({ok} succeeded, {fail} failed)', '生成中… {i}/{n}（成功 {ok}、失敗 {fail}）'),
    '完成：{ok} 成功 / {fail} 失敗': ('Done: {ok} succeeded / {fail} failed', '完了：成功 {ok} 件 / 失敗 {fail} 件'),
    '現代客廳特色牆': ('Modern living-room feature wall', 'モダンなリビングのアクセントウォール'),
    '餐廳餐桌桌面': ('Dining table top', 'ダイニングテーブルの天板'),
    '廚房中島檯面': ('Kitchen island worktop', 'キッチンアイランドの天板'),
    '旅店接待櫃台': ('Hotel reception desk', 'ホテルの受付カウンター'),
    '衛浴洗手檯面': ('Bathroom vanity top', '洗面カウンター'),
    '編輯石材': ('Edit stone', '石材を編集'),
    '{v}（既有資料）': ('{v} (existing)', '{v}（既存データ）'),
    '石材描述（英文，留空會自動從照片生成）': ('Stone description (English — leave blank to generate from the photo)', '石材の説明（英語。空欄の場合は写真から自動生成）'),
    '主要照片': ('Main photo', 'メイン写真'),
    '目前照片 {n}': ('Current photo {n}', '現在の写真 {n}'),
    '點擊選擇{label}': ('Click to choose: {label}', 'クリックして選択：{label}'),
    'AI 分析中…(約 10 秒)': ('Analysing… (about 10 s)', 'AI 解析中…（約 10 秒）'),
    '✓ 已更新（請按下方「儲存」生效）': ('✓ Updated (click “Save” below to apply)', '✓ 更新しました（下の「保存」で反映されます）'),
    '「{name}」已成功新增！': ('“{name}” has been added.', '「{name}」を追加しました。'),
    ' 已自動偵測顏色為「{color}」': (' Colour auto-detected as “{color}”.', ' カラーを「{color}」と自動判定しました。'),
    '⚠ 以下照片上傳失敗（已保留原檔案）：{files}': ('⚠ These photos failed to upload (existing files kept): {files}', '⚠ 次の写真のアップロードに失敗しました（元のファイルは保持）：{files}'),
    '「{name}」資料已更新！': ('“{name}” has been updated.', '「{name}」を更新しました。'),
    '✅ 已重新索引 {n} 筆石材（含新版視覺特徵），自動補上 {c} 筆顏色標籤': ('✅ Re-indexed {n} stones (with the new visual features); filled in {c} colour tags', '✅ 石材 {n} 件を再インデックスしました（新しい視覚特徴を含む）。カラータグを {c} 件自動補完しました'),

    # ══ 手機版導覽 ══
    '選單': ('Menu', 'メニュー'),
    '{name} 的帳號': ('{name}’s account', '{name} さんのアカウント'),

    # ══ 測試資料 ══
    '測試': ('Test', 'テスト'),
    '測試資料': ('Test data', 'テストデータ'),
    '目前': ('Currently', '現在'),
    '筆': ('records', '件'),
    '一鍵產生 20 筆循環石材（含照片、英日文翻譯、以圖搜圖索引），涵蓋 4 種石材與 8 個色系。照片由程式生成，不呼叫 AI、不產生費用。':
        ('Create 20 circular-stone records in one click (with photos, English/Japanese translations and '
         'image-search index), covering 4 stone types and 8 colour groups. Photos are generated by code — '
         'no AI calls and no cost.',
         'ワンクリックで循環石材 20 件を作成します（写真・英日翻訳・画像検索インデックス付き）。'
         '4 種類の石材と 8 つのカラーを網羅。写真はプログラムで生成し、AI は使用せず費用もかかりません。'),
    '產生 20 筆測試資料': ('Create 20 test records', 'テストデータを 20 件作成'),
    '產生中…': ('Creating…', '作成中…'),
    '清除測試資料': ('Clear test data', 'テストデータを削除'),
    '將以新的 20 筆替換現有測試資料，確定？': ('This will replace the existing test data with 20 new records. Continue?',
                                               '既存のテストデータを新しい 20 件に置き換えます。よろしいですか？'),
    '確定清除所有測試資料？照片也會一併刪除，無法復原。':
        ('Clear all test data? Photos will be deleted too. This cannot be undone.',
         'すべてのテストデータを削除しますか？写真も削除され、元に戻せません。'),
    '已產生 {n} 筆測試資料': ('Created {n} test records', 'テストデータを {n} 件作成しました'),
    '（已替換先前的 {n} 筆）': (' (replaced the previous {n})', '（以前の {n} 件を置き換えました）'),
    '已清除 {n} 筆測試資料（含照片）': ('Cleared {n} test records (including photos)',
                                        'テストデータを {n} 件削除しました（写真を含む）'),
    '產生測試資料失敗': ('Failed to create test data', 'テストデータの作成に失敗しました'),

    # ══ 多語內容管理 ══
    '多語內容（英文／日文）': ('Translations (English / Japanese)', '多言語コンテンツ（英語／日本語）'),
    '用 AI 翻譯': ('Translate with AI', 'AI で翻訳'),
    '留空則該語言顯示中文原文。AI 翻譯為草稿，可自行修改後再儲存。':
        ('Leave blank to show the Chinese original in that language. AI output is a draft — edit it before saving.',
         '空欄の場合、その言語では中国語原文を表示します。AI の翻訳は下書きです。編集してから保存してください。'),
    '品名（英文）': ('Stone name (English)', '石材名（英語）'),
    '品名（日文）': ('Stone name (Japanese)', '石材名（日本語）'),
    '廠商（英文）': ('Supplier (English)', 'サプライヤー（英語）'),
    '廠商（日文）': ('Supplier (Japanese)', 'サプライヤー（日本語）'),
    '備註（英文）': ('Notes (English)', '備考（英語）'),
    '備註（日文）': ('Notes (Japanese)', '備考（日本語）'),
    '翻譯中…': ('Translating…', '翻訳中…'),
    '已填入，請確認後儲存': ('Filled in — review and save', '入力しました。確認して保存してください'),
    '翻譯失敗': ('Translation failed', '翻訳に失敗しました'),
    '尚未設定 GEMINI_API_KEY，無法自動翻譯':
        ('GEMINI_API_KEY is not set, so automatic translation is unavailable',
         'GEMINI_API_KEY が未設定のため自動翻訳できません'),
    '此石材沒有可翻譯的文字內容': ('This stone has no text to translate', 'この石材には翻訳できるテキストがありません'),
    '翻譯失敗，請稍後再試': ('Translation failed, please try again later', '翻訳に失敗しました。しばらくしてからお試しください'),
    '找不到該公告': ('Announcement not found', 'お知らせが見つかりません'),

    # ══ 石材種類（固定清單）══
    '大理石': ('Marble', '大理石'),
    '花崗岩': ('Granite', '花崗岩'),
    '蛇紋石': ('Serpentine', '蛇紋石'),
    '化石': ('Fossil Stone', '化石'),

    # ══ 顏色標籤（固定清單）══
    '白色系': ('White', 'ホワイト系'),
    '灰色系': ('Grey', 'グレー系'),
    '黑色系': ('Black', 'ブラック系'),
    '米色系': ('Beige', 'ベージュ系'),
    '棕色系': ('Brown', 'ブラウン系'),
    '綠色系': ('Green', 'グリーン系'),
    '紅色系': ('Red', 'レッド系'),
    '其他': ('Other', 'その他'),

    # ══ 系統提示訊息（flash / API 錯誤）══
    '請先登入會員帳號': ('Please sign in first', 'まずログインしてください'),
    '請先登入會員才能使用 AI 設計工具': ('Please sign in to use the AI design tools',
                                          'AI デザインツールのご利用にはログインが必要です'),
    '請先登入會員才能使用牆面模擬': ('Please sign in to use wall simulation',
                                      'ウォールシミュレーションのご利用にはログインが必要です'),
    '請先登入會員才能使用草圖渲染': ('Please sign in to use sketch rendering',
                                      'スケッチレンダリングのご利用にはログインが必要です'),
    '姓名與 Email 為必填欄位': ('Name and email are required', 'お名前とメールアドレスは必須です'),
    '姓名、Email 及密碼為必填': ('Name, email and password are required',
                                 'お名前・メールアドレス・パスワードは必須です'),
    '姓名為必填欄位': ('Name is required', 'お名前は必須です'),
    '石材種類為必填欄位': ('Stone type is required', '石材の種類は必須です'),
    '標題為必填': ('Title is required', 'タイトルは必須です'),
    '兩次密碼不一致': ('Passwords do not match', 'パスワードが一致しません'),
    '密碼至少需要 6 個字元': ('Password must be at least 6 characters', 'パスワードは 6 文字以上で入力してください'),
    '新密碼至少需要 6 個字元': ('New password must be at least 6 characters',
                                 '新しいパスワードは 6 文字以上で入力してください'),
    '新密碼與確認密碼不符': ('New password and confirmation do not match',
                             '新しいパスワードと確認用パスワードが一致しません'),
    '目前密碼不正確': ('Current password is incorrect', '現在のパスワードが正しくありません'),
    '密碼已成功更新！': ('Password updated.', 'パスワードを更新しました。'),
    '此 Email 已被註冊': ('This email is already registered', 'このメールアドレスは登録済みです'),
    'Email 或密碼錯誤': ('Incorrect email or password', 'メールアドレスまたはパスワードが正しくありません'),
    '帳號或密碼錯誤，請重試': ('Incorrect username or password, please try again',
                               'アカウントまたはパスワードが正しくありません。再度お試しください'),
    '註冊成功！歡迎加入 ReStone！': ('Welcome to ReStone — your account is ready.',
                                     'ご登録ありがとうございます。ReStone へようこそ。'),
    '基本資料已更新': ('Profile updated', '基本情報を更新しました'),
    '詢問已送出！廠商將盡快與您聯繫。': ('Enquiry sent — the supplier will contact you shortly.',
                                         'お問い合わせを送信しました。サプライヤーより追ってご連絡します。'),
    '詢問狀態已更新': ('Enquiry status updated', 'お問い合わせのステータスを更新しました'),
    '石材已成功刪除': ('Stone deleted', '石材を削除しました'),
    '已刪除該張設計': ('Design deleted', 'デザインを削除しました'),
    '已刪除一張展覽圖': ('Showcase image deleted', '展示画像を削除しました'),
    '公告已新增': ('Announcement added', 'お知らせを追加しました'),
    '公告已更新': ('Announcement updated', 'お知らせを更新しました'),
    '公告已刪除': ('Announcement deleted', 'お知らせを削除しました'),
    '找不到該石材': ('Stone not found', '石材が見つかりません'),
    '找不到指定石材': ('Stone not found', '指定された石材が見つかりません'),
    '找不到該設計': ('Design not found', 'デザインが見つかりません'),
    '找不到照片': ('Photo not found', '写真が見つかりません'),
    '找不到石材照片檔案': ('Stone photo file not found', '石材の写真ファイルが見つかりません'),
    '找不到石材或石材沒有照片': ('Stone not found, or it has no photo', '石材が見つからないか、写真がありません'),
    '此石材沒有照片': ('This stone has no photo', 'この石材には写真がありません'),
    '此石材沒有照片，無法做材質渲染': ('This stone has no photo, so material rendering is unavailable',
                                       'この石材には写真がないため、マテリアルレンダリングできません'),
    '石材無照片': ('Stone has no photo', '石材に写真がありません'),
    '石材照片檔案不存在': ('Stone photo file does not exist', '石材の写真ファイルが存在しません'),
    '設計圖檔不存在': ('Design file does not exist', 'デザインファイルが存在しません'),
    '參數錯誤': ('Invalid parameters', 'パラメータが不正です'),
    '缺少 design_id': ('Missing design_id', 'design_id がありません'),
    '缺少 stone_id': ('Missing stone_id', 'stone_id がありません'),
    '缺少必要欄位（設計圖、遮罩、石材）': ('Missing required fields (design, mask, stone)',
                                           '必須項目が不足しています（デザイン画・マスク・石材）'),
    '缺少必要欄位（草圖、石材）': ('Missing required fields (sketch, stone)',
                                   '必須項目が不足しています（スケッチ・石材）'),
    '缺少必要欄位（空間照片、石材）': ('Missing required fields (room photo, stone)',
                                       '必須項目が不足しています（空間写真・石材）'),
    '請上傳有效的圖片（JPG／PNG／GIF／WEBP）': ('Please upload a valid image (JPG / PNG / GIF / WEBP)',
                                                 '有効な画像をアップロードしてください（JPG／PNG／GIF／WEBP）'),
    '無法讀取此圖片，請改用 JPG 或 PNG 格式': ('Could not read this image — please use JPG or PNG',
                                                'この画像を読み込めません。JPG または PNG をご利用ください'),
    '無法分析此圖片，請改用其他圖': ('Could not analyse this image — please try another',
                                     'この画像を解析できません。別の画像をお試しください'),
    '照片格式無法解析（支援 JPG / PNG / HEIC / WebP）':
        ('Unsupported photo format (JPG / PNG / HEIC / WebP supported)',
         '対応していない写真形式です（JPG / PNG / HEIC / WebP に対応）'),
    '草圖格式無法解析（支援 JPG / PNG / HEIC / WebP）':
        ('Unsupported sketch format (JPG / PNG / HEIC / WebP supported)',
         '対応していないスケッチ形式です（JPG / PNG / HEIC / WebP に対応）'),
    '設計圖格式無法解析（支援 JPG / PNG / HEIC / WebP）':
        ('Unsupported design format (JPG / PNG / HEIC / WebP supported)',
         '対応していないデザイン形式です（JPG / PNG / HEIC / WebP に対応）'),
    '⚠ 主照片上傳失敗，請檢查檔案格式（PNG/JPG/HEIC/GIF/WebP）或檔案大小（≤32MB）':
        ('⚠ Main photo upload failed — check the format (PNG/JPG/HEIC/GIF/WebP) or size (≤32MB)',
         '⚠ メイン写真のアップロードに失敗しました。形式（PNG/JPG/HEIC/GIF/WebP）またはサイズ（32MB 以下）をご確認ください'),
    '牆面四角座標無效，請重新點選': ('Invalid wall corner coordinates — please mark them again',
                                     '壁の四隅の座標が無効です。もう一度指定してください'),
    '請輸入合理的牆面尺寸（寬 50–2000cm、高 50–1000cm）':
        ('Please enter a valid wall size (width 50–2000cm, height 50–1000cm)',
         '有効な壁寸法を入力してください（幅 50〜2000cm、高さ 50〜1000cm）'),
    'AI 功能尚未啟用（請設定 GEMINI_API_KEY 或 REPLICATE_API_TOKEN）':
        ('AI features are not enabled (set GEMINI_API_KEY or REPLICATE_API_TOKEN)',
         'AI 機能が有効ではありません（GEMINI_API_KEY または REPLICATE_API_TOKEN を設定してください）'),
    'AI 擬真強化需要 Gemini（請設定 GEMINI_API_KEY）':
        ('AI photoreal enhancement requires Gemini (set GEMINI_API_KEY)',
         'AI フォトリアル強化には Gemini が必要です（GEMINI_API_KEY を設定してください）'),
    '草圖渲染需要 Gemini（請設定 GEMINI_API_KEY）':
        ('Sketch rendering requires Gemini (set GEMINI_API_KEY)',
         'スケッチレンダリングには Gemini が必要です（GEMINI_API_KEY を設定してください）'),
    'AI 合成暫時無法使用（Gemini 失敗且未設定 Replicate）':
        ('AI compositing is temporarily unavailable (Gemini failed and Replicate is not configured)',
         'AI 合成は一時的にご利用いただけません（Gemini が失敗し、Replicate も未設定です）'),
    'AI 分析失敗（請確認 Replicate 餘額充足）': ('AI analysis failed (check your Replicate balance)',
                                                 'AI 解析に失敗しました（Replicate の残高をご確認ください）'),
    '未設定 GEMINI_API_KEY，無法生成': ('GEMINI_API_KEY is not set, so generation is unavailable',
                                        'GEMINI_API_KEY が未設定のため生成できません'),
    '請先登入會員': ('Please sign in first', 'まずログインしてください'),
    'HEIC 轉檔模組載入中，請稍候再試': ('HEIC converter is loading, please try again shortly',
                                        'HEIC 変換モジュールを読み込み中です。少々お待ちください'),
}

# 兩段式：完整表 + 忽略空白差異的索引（模板換行縮排不影響命中）
TRANSLATIONS = {
    'en': {k: v[0] for k, v in _T.items()},
    'ja': {k: v[1] for k, v in _T.items()},
}
_WS = re.compile(r'\s+')
def _norm(s):
    return _WS.sub(' ', s).strip()
_NORM = {lang: {_norm(k): v for k, v in d.items()} for lang, d in TRANSLATIONS.items()}


def translate(text, lang=DEFAULT_LANG):
    """把中文原文翻成指定語言；找不到對應時回退為原文。"""
    if not text or lang == DEFAULT_LANG:
        return text
    d = TRANSLATIONS.get(lang)
    if not d:
        return text
    if text in d:
        return d[text]
    return _NORM[lang].get(_norm(text), text)


def fill(text, **kw):
    """把 {name} 這類佔位符換成實際值（用字串替換，不受文字中其他括號影響）。"""
    for k, v in kw.items():
        text = text.replace('{' + k + '}', str(v))
    return text


def js_table(keys, lang=DEFAULT_LANG):
    """前端 JS 用的翻譯表：只輸出該頁 JS 用到的條目，中文模式回傳空表（直接顯示原文）。"""
    if lang == DEFAULT_LANG:
        return {}
    return {k: translate(k, lang) for k in keys}


def coverage():
    return {lang: len(d) for lang, d in TRANSLATIONS.items()}
