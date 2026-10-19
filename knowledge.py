# -*- coding: utf-8 -*-
"""
ReStone 知識庫：文件解析、切段、關鍵字檢索、向量工具（純函式，不呼叫任何付費 API）

流程
  上傳文件 → extract_pages() 抽出文字 → make_chunks() 切成約 500 字的段落
  → （app.py）用 Gemini Embedding 建立向量 → 提問時 rank_chunks() 混合
    「關鍵字分數」與「向量相似度」找出最相關的段落，交給 AI 回答。

支援格式：PDF（pypdf）、Word .docx（python-docx）、純文字 .txt、Markdown .md
"""
import math
import re

import numpy as np

KB_EXTENSIONS = {'pdf', 'docx', 'txt', 'md'}

CHUNK_TARGET = 500     # 每段目標字數
CHUNK_MAX = 700        # 單段上限（過長的段落會再依句子切開）
CHUNK_OVERLAP = 80     # 相鄰段落重疊字數，避免答案剛好被切在兩段之間

_CJK = r'㐀-䶿一-鿿぀-ヿ豈-﫿'
_CJK_RE = re.compile(f'[{_CJK}]')
_SENT_END = '。！？；：.!?;:」』）)'


class ExtractError(Exception):
    """文件無法讀取（加密、損毀、格式不支援）。訊息為中文，由呼叫端翻譯。"""


# ─── 文字抽取 ───────────────────────────────────────────────

def extract_pages(path, ext):
    """回傳 [(頁碼或 None, 文字), ...]。PDF 保留頁碼，方便回答時標示出處。"""
    ext = ext.lower()
    if ext == 'pdf':
        return _extract_pdf(path)
    if ext == 'docx':
        return [(None, _extract_docx(path))]
    if ext in ('txt', 'md'):
        return [(None, _read_text_file(path))]
    raise ExtractError('不支援的檔案格式')


def _extract_pdf(path):
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted:
            try:
                reader.decrypt('')
            except Exception:
                raise ExtractError('PDF 有密碼保護，無法讀取')
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                txt = page.extract_text() or ''
            except Exception:
                txt = ''
            pages.append((i, _join_wrapped_lines(txt)))
        return pages
    except ExtractError:
        raise
    except Exception as e:
        print(f'[知識庫] PDF 讀取失敗：{type(e).__name__}: {str(e)[:200]}')
        raise ExtractError('PDF 讀取失敗，檔案可能已損毀')


def _extract_docx(path):
    try:
        import docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        d = docx.Document(path)
    except Exception as e:
        print(f'[知識庫] Word 讀取失敗：{type(e).__name__}: {str(e)[:200]}')
        raise ExtractError('Word 檔讀取失敗，請確認是 .docx 格式')
    parts = []
    # 依文件原本順序讀段落與表格（表格每列以 | 連接）
    for el in d.element.body.iterchildren():
        tag = el.tag.rsplit('}', 1)[-1]
        if tag == 'p':
            t = Paragraph(el, d).text.strip()
            if t:
                parts.append(t)
        elif tag == 'tbl':
            for row in Table(el, d).rows:
                cells = []
                for c in row.cells:
                    ct = c.text.strip()
                    if ct and (not cells or cells[-1] != ct):   # 合併儲存格會重複出現
                        cells.append(ct)
                if cells:
                    parts.append(' | '.join(cells))
    return '\n\n'.join(parts)


def _read_text_file(path):
    raw = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-8', 'cp950', 'big5', 'gb18030'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='ignore')


def _join_wrapped_lines(text):
    """PDF 每行都會斷行：把同一段落內被折行的文字接回來（中文直接相接、英文補空白）。"""
    lines = [ln.strip() for ln in text.replace('\r', '').split('\n')]
    out = []
    buf, n_lines = '', 0
    for ln in lines:
        if not ln:
            if buf:
                out.append(buf)
                buf, n_lines = '', 0
            continue
        if not buf:
            buf, n_lines = ln, 1
            continue
        n_lines += 1
        if n_lines == 2 and len(buf) <= 24 and buf[-1] not in _SENT_END + '，、,':
            out.append(buf)          # 短短一行、沒有標點：視為標題，自成一段
            buf, n_lines = ln, 1
        elif ln[0] in '•-–·●■□◆▪' or re.match(r'^(\d+[.、)]|[一二三四五六七八九十]+[、.])', ln):
            out.append(buf)          # 新的條列項目
            buf, n_lines = ln, 1
        elif _CJK_RE.match(buf[-1]) or _CJK_RE.match(ln[0]):
            buf += ln
        else:
            buf += ' ' + ln
    if buf:
        out.append(buf)
    return '\n\n'.join(out)


# ─── 切段 ─────────────────────────────────────────────────

def _split_long(par):
    """把超過上限的段落依句子切開；單句仍過長就硬切。"""
    if len(par) <= CHUNK_MAX:
        return [par]
    sents = re.split(r'(?<=[。！？!?；;])\s*|(?<=\.)\s+', par)
    pieces, cur = [], ''
    for s in sents:
        if not s:
            continue
        while len(s) > CHUNK_MAX:
            pieces.append(s[:CHUNK_MAX])
            s = s[CHUNK_MAX:]
        if len(cur) + len(s) > CHUNK_TARGET and cur:
            pieces.append(cur)
            cur = s
        else:
            cur = (cur + ' ' + s) if (cur and not _CJK_RE.search(cur[-1:])) else cur + s
    if cur:
        pieces.append(cur)
    return pieces


def _overlap_tail(text):
    """取上一段結尾約 CHUNK_OVERLAP 字，盡量從句首開始。"""
    if len(text) <= CHUNK_OVERLAP:
        return ''
    tail = text[-CHUNK_OVERLAP:]
    m = re.search(r'[。！？!?；;.]\s*', tail)
    if m and m.end() < len(tail) - 10:
        tail = tail[m.end():]
    return tail.strip()


def make_chunks(pages):
    """[(page, text)] → [{'seq', 'page', 'content'}]。段落依目標長度合併，相鄰段落少量重疊。"""
    chunks = []
    cur, cur_page = '', None
    for page, text in pages:
        # 換頁時若手上的段落已有一定長度就先收尾，讓出處頁碼更準確
        if cur and page != cur_page and len(cur) >= 150:
            chunks.append({'page': cur_page, 'content': cur})
            cur, cur_page = '', None
        pars = [p.strip() for p in re.split(r'\n\s*\n|\n', text or '') if p.strip()]
        for par in pars:
            par = re.sub(r'[ \t　]+', ' ', par)
            for piece in _split_long(par):
                if cur and len(cur) + len(piece) + 1 > CHUNK_TARGET:
                    chunks.append({'page': cur_page, 'content': cur})
                    tail = _overlap_tail(cur)
                    cur, cur_page = (tail + '\n' + piece) if tail else piece, page
                else:
                    if not cur:
                        cur_page = page
                    cur = (cur + '\n' + piece) if cur else piece
    if cur.strip():
        chunks.append({'page': cur_page, 'content': cur})
    # 太短的雜訊段（頁碼、頁首）略過
    chunks = [c for c in chunks if len(re.sub(r'\s', '', c['content'])) >= 8]
    for i, c in enumerate(chunks):
        c['seq'] = i
    return chunks


# ─── 關鍵字檢索（免費、不需 API）──────────────────────────────

_STOP = {
    '什麼', '怎麼', '如何', '可以', '請問', '哪些', '哪個', '是否', '有沒', '沒有', '一下', '我們',
    '你們', '他們', '這個', '那個', '這種', '那種', '需要', '想要', '推薦', '一個', '的是', '是什',
    '麼是', '有什', '嗎？', '適合', '比較', '差別', '關於', '應該', '時候', '要怎', '怎樣',
    'the', 'and', 'for', 'what', 'how', 'which', 'are', 'can', 'does', 'with', 'you', 'is',
    'any', 'about', 'should', 'there', 'that', 'this', 'from', 'have',
}


_STOP_CHARS = set('的了嗎呢吧啊麼嘛喔哪')


def query_terms(text, synonyms=None):
    """問題 → 檢索詞：中文取二字詞組（bigram），英文取單字；可帶入同義詞展開。"""
    text = (text or '').lower()
    terms = set()
    for run in re.findall(f'[{_CJK}]+', text):
        if len(run) == 1:
            continue
        for i in range(len(run) - 1):
            terms.add(run[i:i + 2])
    for w in re.findall(r'[a-z0-9][a-z0-9\-]{1,}', text):
        terms.add(w)
    if synonyms:
        for key, alts in synonyms.items():
            if key.lower() in text:
                for a in alts:
                    a = a.lower()
                    if len(a) >= 2:
                        terms.add(a)
    return {t for t in terms if t not in _STOP and not _STOP_CHARS.intersection(t)}


def keyword_scores(query, texts, synonyms=None):
    """以 IDF 加權計算每段的關鍵字分數（越罕見的詞越重要）。回傳與 texts 同長度的 list。"""
    terms = query_terms(query, synonyms)
    if not terms or not texts:
        return [0.0] * len(texts)
    low = [t.lower() for t in texts]
    n = len(low)
    scores = [0.0] * n
    for term in terms:
        hits = [i for i, t in enumerate(low) if term in t]
        if not hits:
            continue
        idf = math.log(1 + n / len(hits))
        for i in hits:
            scores[i] += idf
    return scores


# ─── 向量工具 ────────────────────────────────────────────────

def pack_vector(vec):
    v = np.asarray(vec, dtype=np.float32)
    norm = float(np.linalg.norm(v))
    if norm > 0:
        v = v / norm          # 存單位向量：相似度直接用內積
    return v.tobytes()


def unpack_vector(blob):
    return np.frombuffer(blob, dtype=np.float32)


def rank_chunks(kw_scores, vec_scores=None, top_k=6, rrf_k=60, vec_pool=30):
    """混合排序（Reciprocal Rank Fusion）：關鍵字命中與語意相近都會被找出來。

    kw_scores: 每段的關鍵字分數；vec_scores: 每段與問題的向量相似度（None 表示無向量）。
    回傳最相關段落的索引 list。
    """
    fused = {}
    kw_order = sorted((i for i, s in enumerate(kw_scores) if s > 0), key=lambda i: -kw_scores[i])
    for rank, i in enumerate(kw_order[:vec_pool]):
        fused[i] = fused.get(i, 0.0) + 1.0 / (rrf_k + rank + 1)
    if vec_scores is not None and len(vec_scores):
        vs = np.asarray(vec_scores)
        vec_order = [int(i) for i in np.argsort(-vs) if vs[i] > -1][:vec_pool]   # -1 = 該段沒有向量
        for rank, i in enumerate(vec_order):
            fused[i] = fused.get(i, 0.0) + 1.0 / (rrf_k + rank + 1)
    return [i for i, _ in sorted(fused.items(), key=lambda kv: -kv[1])][:top_k]
