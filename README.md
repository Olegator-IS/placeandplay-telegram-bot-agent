# 🚀 Place&Play Telegram Bot Agent

![Place&Play Logo](https://placeandplay.uz/assets/logo.svg)

## Описание

**Place&Play Telegram Bot Agent** — это интеграционный агент для автоматизации верификации и уведомлений организаций через Telegram. Позволяет быстро получать коды подтверждения, отправлять уведомления о новых событиях и интегрироваться с вашим API.

---

## Возможности

- 🤖 Автоматическая верификация пользователей через Telegram
- 🔔 Уведомления о новых событиях и регистрациях
- 🛡️ DDoS-защита (лимит попыток, блокировка)
- 📱 Получение chat_id и username пользователя
- 📝 Гибкая настройка через config.env
- 🧩 Простая интеграция с FastAPI

---

## Быстрый старт

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/Olegator-IS/placeandplay-telegram-bot-agent.git
cd placeandplay-telegram-bot-agent
```

### 2. Настройте переменные окружения
Отредактируйте файл `config.env`:
```
TELEGRAM_BOT_TOKEN=ваш_токен_бота
PLACE_AND_PLAY_API_BASE_URL=...
PLACE_AND_PLAY_LOGIN_EMAIL=...
PLACE_AND_PLAY_LOGIN_PASSWORD=...
```

### 3. Установите зависимости
```bash
pip install -r requirements_api.txt
```

### 4. Запустите API и бота
```bash
python place_and_play_api_server.py
# В новом терминале:
python telegram_bot.py
```

### 5. Docker (опционально)
```bash
docker compose -f docker-compose.bot.yml up -d --build
```

---

## Примеры API

- **Отправить уведомление:**
  ```http
  POST /api/v1/sendNotification
  {
    "message": "Вы получили новый ивент",
    "chatId": 123456789
  }
  ```
- **Получить chat_id по username:**
  ```http
  POST /api/v1/getChatId
  {
    "username": "your_username"
  }
  ```

---

## Поддержка

- Telegram: [@abramov_1](https://t.me/abramov_1)
- Email: support@placeandplay.uz

---

## Лицензия

MIT License
