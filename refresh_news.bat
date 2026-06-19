@echo off
cd /d "C:\Users\12\Desktop\OpenCode\news-site"
"C:\Users\12\AppData\Local\Programs\Python\Python312\python.exe" update_news.py --once
echo Deploying...
npx.cmd surge --project ./ --domain https://dz-akhbar.surge.sh
echo Done.
