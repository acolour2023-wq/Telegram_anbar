@echo off
chcp 65001 > nul
title Telegram Excel Bot
echo ==============================================
echo   Telegram Excel Bot Başladılır (@Anbarbotu_bot)
echo ==============================================
cd /d "%~dp0"
echo Lazımi kitabxanalar yoxlanılır...
py -m pip install -r requirements.txt
echo.
echo Bot işə salınır. Dayandırmaq üçün Ctrl+C sıxın.
py bot.py
pause
