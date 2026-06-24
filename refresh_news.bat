@echo off
cd /d "C:\Users\12\Desktop\OpenCode\news-site"
"C:\Users\12\AppData\Local\Programs\Python\Python312\python.exe" update_news.py --once
echo Build done. Pushing to GitHub...
git add index.html latest_news.json
git commit -m "auto: daily news update %date% %time%"
git push
echo Done. GitHub Actions will deploy automatically.
