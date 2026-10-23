@echo off
rem Starts the tier list server and a public link. Keep this window open while you play.
cd /d "%~dp0"
start "Tier list server" python server.py
timeout /t 2 >nul
echo Your public link is the https://....lhr.life address printed below.
ssh -o ServerAliveInterval=30 -R 80:127.0.0.1:8000 nokey@localhost.run
