@echo off
echo ====================================
echo Study Tracker - Quick Reset Stats
echo ====================================
echo.
echo WARNING: This will delete ALL your study history!
echo.
pause

cd /d "%~dp0"
call .venv\Scripts\activate
python -c "from BackEnd.core.paths import db_path, user_data_dir; import os; db = db_path(); todos = user_data_dir() / 'todos.json'; [os.remove(f) if f.exists() else None for f in [db, todos]]; print('✓ All stats reset to 0!')"

echo.
echo Stats have been reset!
echo Next time you open the app, everything will be fresh.
echo.
pause
