@echo off
chcp 65001 >nul
echo ================================
echo Мониторинг жалоб Radmir Games
echo ================================
echo.

REM Проверяем, установлен ли requests
python -c "import requests" 2>nul
if errorlevel 1 (
    echo Устанавливаю зависимости...
    python -m pip install requests beautifulsoup4 lxml
    echo.
)

echo Запуск мониторинга...
echo.
python monitor.py
