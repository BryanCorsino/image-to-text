@echo off
cd C:\Users\bryan\OneDrive\Desktop\imagetotext\code_checker\

echo ========================================
echo Database Reset Tool
echo ========================================
echo.

echo Stopping Flask application...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

echo Deleting old database...
if exist instance\users.db (
    del instance\users.db
    echo ✅ Database deleted
) else (
    echo ℹ️ No database found
)

echo Deleting migrations folder...
if exist migrations (
    rmdir /s /q migrations
    echo ✅ Migrations folder deleted
)

echo.
echo ========================================
echo ✅ Reset complete!
echo ========================================
echo.
echo Starting fresh application...
echo.

python app.py
pause