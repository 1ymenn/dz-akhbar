@echo off
cd /d "C:\Users\12\Desktop\OpenCode\news-site"
"C:\Users\12\AppData\Local\Programs\Python\Python312\python.exe" update_news.py --once
echo Build done. GitHub Actions will deploy automatically.
echo Done.
