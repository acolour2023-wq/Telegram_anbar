@echo off
chcp 65001 > nul
title Render Və GitHub Avtomatik Yeniləmə
echo ===================================================
echo   GitHub / Render (7/24 Server) Avtomatik Yenilənir...
echo ===================================================
cd /d "%~dp0"
echo Dəyişikliklər yoxlanılır və GitHub-a göndərilir...
git add .
git commit -m "Excel ve Bot yenilendi - %date% %time%"
git push origin main
echo.
echo ✅ Bütün dəyişikliklər GitHub-a yükləndi!
echo 🚀 Render 1-2 dəqiqə ərzində avtomatik olaraq yeni kodu və Excel faylını işə salacaq.
pause
