# 🚀 Place&Play Telegram Bot - Инструкция по запуску

## 📁 **Структура файлов:**
```
place-and-play-agent/
├── telegram_bot.py          # Основной файл бота
├── place_and_play_agent.py  # Логика агента
├── place_and_play_api_server.py  # FastAPI сервер
├── config.env               # Конфигурация
├── Dockerfile.bot           # Docker для бота
├── docker-compose.bot.yml   # Docker Compose для бота
└── requirements_api.txt     # Зависимости Python
```

## 🎯 **Как работает бот:**

1. **Пользователь нажимает /start** → Бот показывает приветствие
2. **Пользователь отправляет номер телефона** → Бот валидирует формат
3. **Бот автоматически:**
   - Получает токены доступа через API login
   - Запрашивает код верификации с полученными токенами
   - Отправляет код пользователю в Telegram
4. **Пользователь вводит код в приложении Place&Play**

## 🚀 **Способы запуска:**

### **Вариант 1: Локальный запуск (для тестирования)**

```bash
# 1. Установите зависимости
pip install -r requirements_api.txt

# 2. Запустите агента
python place_and_play_api_server.py

# 3. В новом терминале запустите бота
python telegram_bot.py
```

### **Вариант 2: Docker (рекомендуется для продакшена)**

```bash
# 1. Запустите бота и агента вместе
docker compose -f docker-compose.bot.yml up -d --build

# 2. Проверьте статус
docker compose -f docker-compose.bot.yml ps

# 3. Посмотрите логи
docker logs -f place-and-play-bot
docker logs -f place-and-play-api
```

### **Вариант 3: Только бот в Docker (если агент уже запущен)**

```bash
# 1. Запустите только бота
docker build -f Dockerfile.bot -t place-and-play-bot .
docker run -d --name place-and-play-bot --env-file config.env place-and-play-bot

# 2. Проверьте логи
docker logs -f place-and-play-bot
```

## ⚙️ **Настройка config.env:**

```bash
# Отредактируйте config.env
nano config.env

# Убедитесь, что указаны:
TELEGRAM_BOT_TOKEN=ваш_токен_бота
AGENT_API_URL=http://localhost:8000  # Для локального запуска
# или
AGENT_API_URL=http://95.46.96.94:8000  # Для сервера
```

## 🔍 **Проверка работы:**

### **1. Проверьте агента:**
```bash
curl http://localhost:8000/health
curl http://localhost:8000/
```

### **2. Проверьте бота:**
- Откройте Telegram
- Найдите вашего бота
- Нажмите `/start`
- Должно появиться приветствие

### **3. Проверьте логи:**
```bash
# Логи бота
docker logs -f place-and-play-bot

# Логи агента
docker logs -f place-and-play-api
```

## 🚨 **Устранение проблем:**

### **Бот не отвечает на /start:**
1. Проверьте, что бот запущен: `docker ps`
2. Проверьте логи: `docker logs place-and-play-bot`
3. Убедитесь, что токен правильный в `config.env`

### **Ошибка подключения к агенту:**
1. Проверьте, что агент запущен: `docker ps`
2. Проверьте URL в `AGENT_API_URL`
3. Проверьте сеть Docker: `docker network ls`

### **Ошибка получения токенов:**
1. Проверьте логи агента
2. Убедитесь, что API Place&Play доступен
3. Проверьте логин/пароль в `config.env`

## 📱 **Тестирование:**

1. **Отправьте /start** → Должно появиться приветствие
2. **Отправьте номер телефона** → Должен начаться процесс обработки
3. **Дождитесь результата** → Получите код верификации или ошибку

## 🔄 **Перезапуск:**

```bash
# Остановить
docker compose -f docker-compose.bot.yml down

# Запустить заново
docker compose -f docker-compose.bot.yml up -d --build
```

## 📞 **Поддержка:**

При возникновении проблем:
1. Проверьте логи контейнеров
2. Убедитесь, что все переменные окружения настроены
3. Проверьте доступность внешних API
4. Убедитесь, что порты не заняты другими сервисами
