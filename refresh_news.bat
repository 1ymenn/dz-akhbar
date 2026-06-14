@echo off
cd /d "%~dp0"
echo ============================================
echo        NewsHub - Refresh News
echo ============================================
echo.
echo Fetching latest news from all sources...
echo.
python update_news.py
echo.
echo Opening website...
start index.html
echo Done!
pause
