#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

# --- 新增這行：讓伺服器自動生成資料庫遷移檔 ---
python manage.py makemigrations analyzer

python manage.py migrate
