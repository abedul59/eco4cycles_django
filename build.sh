#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input

# --- 強制建立 migrations 結構，避免 Django 找不到 App 模組 ---
mkdir -p analyzer/migrations
touch analyzer/migrations/__init__.py

# --- 產生並執行資料庫遷移 ---
python manage.py makemigrations analyzer
python manage.py migrate
