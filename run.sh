#!/bin/bash
echo ""
echo "=============================="
echo "  石材循環資料庫 — 啟動中..."
echo "=============================="
echo ""

# 檢查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 找不到 Python3，請先安裝 Python："
    echo "   https://www.python.org/downloads/"
    read -p "按 Enter 關閉..."
    exit 1
fi

# 安裝依賴套件（只在第一次執行）
if [ ! -d "venv" ]; then
    echo "📦 第一次執行，正在安裝必要套件..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q flask werkzeug
    echo "✅ 套件安裝完成！"
else
    source venv/bin/activate
fi

echo ""
echo "🚀 啟動伺服器..."
echo "   前台：http://127.0.0.1:5000"
echo "   後台：http://127.0.0.1:5000/admin/login"
echo ""
echo "   按 Ctrl+C 可停止伺服器"
echo ""

python3 app.py
