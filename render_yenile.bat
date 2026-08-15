@echo off
chcp 65001 > nul
title Render Ve GitHub Avtomatik Yenileme
echo ===================================================
echo   GitHub Ve Render Server Avtomatik Yenilenir...
echo ===================================================
cd /d "%~dp0"
echo.
echo Deyisiklikler yoxlanilir ve GitHub-a gonderilir...
git add .
git commit -m "Excel ve Bot yenilendi"
git push origin main
echo.
echo ===================================================
echo   Butun deyisiklikler GitHub-a yuklendi!
echo   Render 1-2 deqiqe erzinde botu yenileyecek.
echo ===================================================
pause
