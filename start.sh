#!/bin/bash
echo "✅ Таблицы users и dialogs готовы."
gunicorn app:app --timeout 300
