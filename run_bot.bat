@echo off
chcp 65001 > nul
title Telegram Excel Bot
echo ==============================================
echo   Telegram Excel Bot Başladılır (@Anbarbotu_bot)
echo ==============================================
cd /d "%~dp0"
echo Lazımi kitabxanalar yoxlanılır...
py -m pip install -r requirements.txt --quiet
echo.

:loop
echo [%date% %time%] Bot işə salınır...
py bot.py
echo.
echo ⚠️ Bot dayandı və ya şəbəkə qırıldı. 5 saniyə sonra avtomatik yenidən başladılır...
timeout /t 5 > nul
goto loop

