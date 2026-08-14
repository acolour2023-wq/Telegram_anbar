@echo off
chcp 65001 > nul
title Hugging Face 1-Klik Avtomatik Yeniləmə
echo ===================================================
echo   Hugging Face (7/24 Server) Avtomatik Yenilənir...
echo ===================================================
cd /d "%~dp0"
echo Lazımi vasitələr yoxlanılır...
py -m pip install huggingface_hub --quiet
echo.
py upload_to_hf.py
echo.
echo Yenilənmə tamamlandı! Bu pəncərəni bağlaya bilərsiniz.
pause
