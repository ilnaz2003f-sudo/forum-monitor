# Мониторинг жалоб — Radmir Forums

Работает на **GitHub Actions** — ПК не нужен, проверяет автоматически.

## Быстрый старт

### 1. Создай бота в Telegram
Напиши `@BotFather`:
```
/newbot
```
Следуй инструкциям → получи **токен**.

### 2. Узнай свой Chat ID
Напиши `@userinfobot` → получи **ID**.

### 3. Создай репозиторий
```powershell
cd C:\Users\ilnaz\forum_monitor
git init
git add .
git commit -m "init"
```
Создай новый репозиторий на github.com и запушь:
```powershell
git remote add origin https://github.com/ТВОЙ_НИК/forum-monitor.git
git branch -M main
git push -u origin main
```

### 4. Добавь секреты
В репозитории: **Settings → Secrets and variables → Actions → New repository secret**

| Имя | Значение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от @BotFather |
| `TELEGRAM_CHAT_ID` | Твой Chat ID |

### 5. Готово!

- Запускается **каждые 2 часа** автоматически
- Можно запустить вручную: вкладка **Actions** → **Monitor Radmir Forums** → **Run workflow**

## Настройка расписания

В `.github/workflows/monitor.yml` измени cron:

| Частота | Значение |
|---|---|
| Каждый час | `0 * * * *` |
| Каждые 2 часа (текущее) | `0 */2 * * *` |
| Каждые 6 часов | `0 */6 * * *` |
| Раз в день в 9:00 | `0 9 * * *` |

## Как это работает

1. GitHub Actions запускает `monitor.py` по расписанию
2. Скрипт проходит все страницы форума
3. Если найдена жалоба старше **20 часов** — отправляет уведомление в Telegram
4. Если тем не найдено — сохраняет `forum_page.html` для отладки (пришли его мне, подстрою парсер)
