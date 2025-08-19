#!/usr/bin/env python3
"""
Place&Play Telegram Bot - Основной файл
Автоматически получает токены и обрабатывает верификацию
"""
import os
import logging
import requests
import time
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv('config.env')

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
PLACE_AND_PLAY_API_BASE_URL = os.getenv('PLACE_AND_PLAY_API_BASE_URL', 'http://95.46.96.94:8080/PlaceAndPlay/api')
PLACE_AND_PLAY_LOGIN_EMAIL = os.getenv('PLACE_AND_PLAY_LOGIN_EMAIL', 'telegrambot@gmail.com')
PLACE_AND_PLAY_LOGIN_PASSWORD = os.getenv('PLACE_AND_PLAY_LOGIN_PASSWORD', 'TelegramBotPlaceAndPlay')

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в config.env")

class PlaceAndPlayBot:
    def __init__(self):
        self.api_base_url = PLACE_AND_PLAY_API_BASE_URL
        self.login_email = PLACE_AND_PLAY_LOGIN_EMAIL
        self.login_password = PLACE_AND_PLAY_LOGIN_PASSWORD
        
        # Защита от DDoS
        self.attempts = defaultdict(list)  # chat_id -> список попыток
        self.max_attempts = 5  # максимум попыток
        self.block_duration = 600  # блокировка на 10 минут (600 секунд)
        
    def get_auth_tokens(self):
        """Получает accessToken и refreshToken через API login"""
        try:
            login_url = f"{self.api_base_url}/auth/login"
            login_data = {
                "phoneNumber": self.login_email,
                "password": self.login_password
            }
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'PlaceAndPlay-TelegramBot/1.0',
                'isUser': 'true',
                'language': 'ru'
            }
            
            logger.info("Получение токенов аутентификации...")
            response = requests.post(login_url, json=login_data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get("status") == 200 and "result" in response_data:
                    tokens = response_data["result"]
                    access_token = tokens.get("accessToken")
                    refresh_token = tokens.get("refreshToken")
                    
                    if access_token and refresh_token:
                        logger.info("Токены аутентификации успешно получены")
                        return {
                            "success": True, 
                            "access_token": access_token, 
                            "refresh_token": refresh_token
                        }
                    else:
                        logger.error("Токены не найдены в ответе API")
                        return {"success": False, "error": "TOKENS_NOT_FOUND", "message": f"Токены не найдены в ответе: {response_data}"}
                else:
                    logger.error(f"Неверный формат ответа API: {response_data}")
                    return {"success": False, "error": "INVALID_RESPONSE", "message": f"Неверный формат ответа: {response_data}"}
            else:
                logger.error(f"Ошибка API login: {response.status_code} - {response.text}")
                return {"success": False, "error": "LOGIN_API_ERROR", "message": f"HTTP {response.status_code}: {response.text}"}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при получении токенов: {str(e)}")
            return {"success": False, "error": "NETWORK_ERROR", "message": f"Ошибка сети: {str(e)}"}
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении токенов: {str(e)}")
            return {"success": False, "error": "UNKNOWN_ERROR", "message": f"Неожиданная ошибка: {str(e)}"}

    def check_ddos_protection(self, chat_id: int) -> dict:
        """Проверяет защиту от DDoS для конкретного чата"""
        current_time = time.time()
        chat_attempts = self.attempts[chat_id]
        
        # Удаляем старые попытки (старше 10 минут)
        chat_attempts = [attempt for attempt in chat_attempts if current_time - attempt < self.block_duration]
        self.attempts[chat_id] = chat_attempts
        
        # Проверяем количество попыток
        if len(chat_attempts) >= self.max_attempts:
            # Пользователь заблокирован
            oldest_attempt = min(chat_attempts)
            time_until_unblock = self.block_duration - (current_time - oldest_attempt)
            minutes = int(time_until_unblock // 60)
            seconds = int(time_until_unblock % 60)
            
            return {
                "blocked": True,
                "time_until_unblock": time_until_unblock,
                "minutes": minutes,
                "seconds": seconds
            }
        
        return {"blocked": False}

    def record_attempt(self, chat_id: int):
        """Записывает попытку для конкретного чата"""
        current_time = time.time()
        self.attempts[chat_id].append(current_time)
        logger.info(f"Записана попытка для чата {chat_id}. Всего попыток: {len(self.attempts[chat_id])}")

    def request_verification_code(self, phone_number, access_token, refresh_token):
        """Запрашивает код верификации через внешний API"""
        try:
            verification_url = f"{self.api_base_url}/auth/phoneNumberVerification"
            headers = {
                'accessToken': access_token,
                'refreshToken': refresh_token,
                'User-Agent': 'PlaceAndPlay-TelegramBot/1.0',
                'isUser': 'true',
                'language': 'ru'
            }
            
            logger.info(f"Запрос кода верификации для номера: {phone_number}")
            params = {"phoneNumber": phone_number}
            response = requests.get(verification_url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"Получен ответ API: {response_data}")
                
                # Проверяем разные форматы ответа
                code = None
                
                # Формат 1: с result
                if response_data.get("status") == 200 and "result" in response_data:
                    result = response_data["result"]
                    code = result.get("code")
                # Формат 2: прямой ответ с code
                elif "code" in response_data:
                    code = response_data.get("code")
                # Формат 3: проверяем все возможные поля
                else:
                    # Ищем code в любом месте ответа
                    for key, value in response_data.items():
                        if key == "code" and value:
                            code = value
                            break
                        elif isinstance(value, dict) and "code" in value:
                            code = value["code"]
                            break
                
                if code:
                    logger.info(f"Код верификации получен: {code}")
                    return {"success": True, "code": code}
                else:
                    logger.error(f"Код не найден в ответе API: {response_data}")
                    # Возвращаем полный ответ API для диагностики
                    return {"success": False, "error": "CODE_NOT_FOUND", "message": f"Код не найден. Ответ API: {response_data}"}
            else:
                logger.error(f"Ошибка API верификации: {response.status_code} - {response.text}")
                return {"success": False, "error": "API_ERROR", "message": response.text}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при запросе кода: {str(e)}")
            return {"success": False, "error": "NETWORK_ERROR", "message": f"Ошибка сети: {str(e)}"}
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе кода: {str(e)}")
            return {"success": False, "error": "UNKNOWN_ERROR", "message": f"Неожиданная ошибка: {str(e)}"}

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        chat_id = update.effective_chat.id
        logger.info(f"Пользователь {user.first_name} (ID: {user.id}) нажал START")

        if context.args and len(context.args) > 0:
            phone_number = context.args[0]
            if not phone_number.startswith('+'):
                phone_number = f'+{phone_number}'
            logger.info(f"/start с параметром: {phone_number} для чата {chat_id}")
            class FakeMessage:
                def __init__(self, text, chat_id, user):
                    self.text = text
                    self.chat = type('obj', (object,), {'id': chat_id})
                    self.from_user = user
                async def reply_text(self, *args, **kwargs):
                    return await update.message.reply_text(*args, **kwargs)
            fake_update = Update(
                update.update_id,
                message=FakeMessage(phone_number, chat_id, user)
            )
            await self.handle_phone_number(fake_update, context)
            return

        welcome_message = (
            "🎉 <b>Добро пожаловать в Place&Play!</b>\n\n"
            "📱 <b>Для продолжения поделитесь своим номером телефона</b>\n"
            "Нажмите кнопку ниже, чтобы отправить контакт.\n\n"
            "🛡️ <b>Безопасность:</b> Ваш номер используется только для верификации."
        )
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            welcome_message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        logger.info(f"Приветственное сообщение отправлено в чат {chat_id}")

    async def handle_phone_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE, silent_processing=False):
        """Обработчик введенного номера телефона"""
        phone_number = update.message.text.strip()
        chat_id = update.effective_chat.id
        
        logger.info(f"Получен номер: {phone_number} в чате {chat_id}")
        
        # Проверка DDoS защиты
        ddos_check = self.check_ddos_protection(chat_id)
        if ddos_check["blocked"]:
            minutes = ddos_check["minutes"]
            seconds = ddos_check["seconds"]
            logger.warning(f"Пользователь {chat_id} заблокирован DDoS защитой. Разблокировка через {minutes:02d}:{seconds:02d}")
            await update.message.reply_text(
                f"🚫 <b>Доступ заблокирован</b>\n\n"
                f"⚠️ Превышен лимит попыток\n"
                f"⏰ Разблокировка через: <code>{minutes:02d}:{seconds:02d}</code>\n\n"
                f"🆘 <b>Поддержка:</b> @abramov_1",
                parse_mode='HTML'
            )
            return
        
        # Проверка формата номера
        if not phone_number.startswith('+') or len(phone_number) < 10:
            await update.message.reply_text(
                "❌ <b>Неверный формат номера</b>\n\n"
                "📱 <b>Требования:</b>\n"
                "• Должен начинаться с '+'\n"
                "• Минимум 10 цифр\n\n"
                "💡 <b>Пример:</b> <code>+998998888931</code>\n\n"
                "🆘 <b>Поддержка:</b> @abramov_1",
                parse_mode='HTML'
            )
            return
        
        # Записываем попытку
        self.record_attempt(chat_id)
        current_attempts = len(self.attempts[chat_id])
        logger.info(f"Попытка {current_attempts}/{self.max_attempts} для чата {chat_id}")
        
        # Отправляем сообщение о начале обработки
        processing_msg = await update.message.reply_text(
            "🔄 <b>Обрабатываю запрос...</b>\n\n"
            "📱 <b>Номер:</b> <code>{}</code>\n"
            "🛡️ <b>Попытка:</b> {}/{}".format(phone_number, current_attempts, self.max_attempts),
            parse_mode='HTML'
        )
        
        try:
            # Шаг 1: Получаем токены аутентификации
            logger.info("Шаг 1: Получение токенов аутентификации...")
            tokens_result = self.get_auth_tokens()
            
            if not tokens_result.get("success"):
                # Удаляем сообщение о обработке
                await processing_msg.delete()
                
                # Показываем детали ошибки получения токенов
                token_error = tokens_result.get("error", "UNKNOWN_ERROR")
                token_message = tokens_result.get("message", "Неизвестная ошибка")
                
                error_message = f"""❌ <b>Ошибка получения токенов</b>\n\n📱 <b>Номер:</b> <code>{phone_number}</code>\n🛡️ <b>Попытка:</b> {current_attempts}/{self.max_attempts}\n\n🚨 <b>Тип ошибки:</b> {token_error}\n📝 <b>Детали:</b> {token_message}\n\n🔄 Попробуйте позже\n🆘 <b>Поддержка:</b> @abramov_1""".strip()
                
                await update.message.reply_text(error_message, parse_mode='HTML')
                return
            
            access_token = tokens_result["access_token"]
            refresh_token = tokens_result["refresh_token"]
            logger.info("Токены получены успешно, переходим к запросу кода...")
            
            # Обновляем сообщение о процессе
            await processing_msg.edit_text(
                "🔄 <b>Получаю код верификации...</b>\n\n"
                "📱 <b>Номер:</b> <code>{}</code>\n"
                "🛡️ <b>Попытка:</b> {}/{}".format(phone_number, current_attempts, self.max_attempts),
                parse_mode='HTML'
            )
            
            # Шаг 2: Запрашиваем код верификации с полученными токенами
            logger.info("Шаг 2: Запрос кода верификации...")
            verification_result = self.request_verification_code(phone_number, access_token, refresh_token)
            
            if verification_result.get("success") and verification_result.get("code"):
                # Удаляем сообщение о обработке
                await processing_msg.delete()
                
                code = verification_result["code"]
                current_attempts = len(self.attempts[chat_id])
                # Форматируем номер с пробелами для красоты
                pretty_phone = phone_number
                if phone_number.startswith('+') and len(phone_number) == 13:
                    pretty_phone = f"+{phone_number[1:4]} {phone_number[4:6]} {phone_number[6:9]} {phone_number[9:11]} {phone_number[11:13]}"
                success_message = f"""
🔐 <b>Ваш код:</b> <code>{code}</code>\n\n📱 <b>Для номера:</b> <code>{pretty_phone}</code>\n🛡️ <b>Попытка:</b> {current_attempts}/{self.max_attempts}\n\n💡 <i>Введите код в приложении Place&Play</i>
            """.strip()
                await update.message.reply_text(success_message, parse_mode='HTML')
                logger.info(f"Код верификации успешно отправлен для {phone_number}")
                
            else:
                # Удаляем сообщение о обработке
                await processing_msg.delete()
                
                error_text = verification_result.get("message", "Неизвестная ошибка")
                error_type = verification_result.get("error", "UNKNOWN_ERROR")
                
                if error_type == "AUTH_ERROR":
                    error_message = f"""❌ <b>Ошибка аутентификации</b>\n\n📱 <b>Номер:</b> <code>{phone_number}</code>\n🛡️ <b>Попытка:</b> {current_attempts}/{self.max_attempts}\n\n🔄 Попробуйте позже\n🆘 <b>Поддержка:</b> @abramov_1""".strip()
                else:
                    # Показываем реальный ответ от API
                    api_response = verification_result.get("message", "Неизвестная ошибка")
                    # Ограничиваем длину ответа API для удобства чтения
                    if len(api_response) > 200:
                        api_response = api_response[:200] + "..."
                    
                    error_message = f"""❌ <b>Ошибка при запросе кода</b>\n\n📱 <b>Номер:</b> <code>{phone_number}</code>\n🛡️ <b>Попытка:</b> {current_attempts}/{self.max_attempts}\n\n🚨 <b>Ответ API:</b>\n<code>{api_response}</code>\n\n🔄 Попробуйте позже\n🆘 <b>Поддержка:</b> @abramov_1""".strip()
                
                await update.message.reply_text(error_message, parse_mode='HTML')
                logger.warning(f"Ошибка при получении кода для {phone_number}: {error_text}")
                
        except Exception as e:
            # Удаляем сообщение о обработке
            await processing_msg.delete()
            
            # Очищаем сообщение об ошибке от HTML-подобных символов
            error_details = str(e).replace('<', '&lt;').replace('>', '&gt;')
            
            error_message = f"""❌ <b>Внутренняя ошибка</b>\n\n📱 <b>Номер:</b> <code>{phone_number}</code>\n🛡️ <b>Попытка:</b> {current_attempts}/{self.max_attempts}\n\n🔄 Попробуйте позже\n🆘 <b>Поддержка:</b> @abramov_1""".strip()
            
            await update.message.reply_text(error_message, parse_mode='HTML')
            logger.error(f"Неожиданная ошибка для {phone_number}: {str(e)}")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback кнопок"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "example_number":
            await query.edit_message_text(
                "📱 <b>Пример номера телефона:</b>\n\n"
                "<code>+998998888931</code>\n\n"
                "💡 <b>Скопируйте и отправьте в чат</b>\n\n"
                "🆘 <b>Поддержка:</b> @abramov_1",
                parse_mode='HTML'
            )
        elif query.data == "help_info":
            # Показываем краткую справку
            help_short = """
❓ <b>Краткая справка</b>

📱 <b>Как использовать:</b>
1️⃣ Отправьте номер телефона
2️⃣ Получите код верификации
3️⃣ Введите код в приложении

💬 <b>Команды:</b>
• /start - Начать заново
• /help - Подробная справка
• /support - Поддержка

🆘 <b>Проблемы?</b>
Обратитесь в поддержку: @abramov_1
            """.strip()
            
            await query.edit_message_text(help_short, parse_mode='HTML')
            
        elif query.data == "status_info":
            # Показываем информацию о статусе для всех пользователей
            current_time = time.time()
            total_chats = len(self.attempts)
            active_chats = 0
            
            for chat_id, attempts in self.attempts.items():
                recent_attempts = [attempt for attempt in attempts if current_time - attempt < self.block_duration]
                if recent_attempts:
                    active_chats += 1
            
            status_info = f"""
📊 <b>Статус системы</b>

🛡️ <b>DDoS защита:</b>
• Максимум попыток: {self.max_attempts}
• Время блокировки: {self.block_duration//60} минут

📈 <b>Статистика:</b>
• Активных чатов: {active_chats}
• Всего зарегистрированных: {total_chats}

⏰ <b>Время:</b> {time.strftime('%H:%M:%S')}

💡 <b>Статус:</b> Система работает ✅

🆘 <b>Поддержка:</b> @abramov_1
            """.strip()
            
            await query.edit_message_text(status_info, parse_mode='HTML')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🔍 <b>Справка по использованию</b>

📱 <b>Пошаговая инструкция:</b>
1️⃣ Нажмите /start для начала работы
2️⃣ Нажмите кнопку <b>Поделиться номером</b> и отправьте свой контакт
3️⃣ Дождитесь автоматической обработки
4️⃣ Получите код верификации
5️⃣ Введите код в приложении Place&Play

🎯 <b>Основные команды:</b>
• /start - Начать процесс верификации
• /help - Показать эту справку
• /support - Связаться с поддержкой

💡 <b>Автоматизация:</b>
• Получение токенов доступа
• Запрос кода верификации
• Обработка ошибок

🚨 <b>Решение проблем:</b>
• Поделитесь номером только через кнопку
• Убедитесь в регистрации в Place&Play
• Попробуйте позже или обратитесь в поддержку

🛡️ <b>Система защиты:</b>
• Максимум 5 попыток верификации
• Блокировка на 10 минут при превышении лимита
• Автоматическая разблокировка

🆘 <b>Поддержка:</b>
• Telegram: @abramov_1
• Команда: /support
        """.strip()
        await update.message.reply_text(help_text, parse_mode='HTML')

    async def support_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /support"""
        support_text = """
🆘 <b>Поддержка Place&Play</b>

📞 <b>Связаться с поддержкой:</b>
• Telegram: @abramov_1
• Описание: Техническая поддержка и помощь пользователям

💬 <b>Что можно уточнить:</b>
• Проблемы с верификацией
• Ошибки в работе бота
• Вопросы по использованию
• Технические проблемы
• Проблемы с API

🔗 <b>Нажмите на ссылку:</b>
<a href="https://t.me/abramov_1">@abramov_1</a>

⏰ <b>Время ответа:</b>
• Обычно в течение 1-2 часов
• В рабочее время быстрее

💡 <b>Совет:</b>
Опишите проблему подробно для быстрого решения
        """.strip()
        
        await update.message.reply_text(support_text, parse_mode='HTML', disable_web_page_preview=True)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status (для администраторов)"""
        # Проверяем, является ли пользователь администратором (можно настроить по chat_id)
        user_id = update.effective_user.id
        admin_ids = [177046812]  # Добавьте сюда ID администраторов
        
        if user_id not in admin_ids:
            await update.message.reply_text(
                "🚫 <b>Доступ запрещен</b>\n\n"
                "⚠️ Эта команда доступна только администраторам",
                parse_mode='HTML'
            )
            return
        
        # Собираем статистику DDoS защиты
        total_chats = len(self.attempts)
        blocked_chats = 0
        total_attempts = 0
        
        current_time = time.time()
        for chat_id, attempts in self.attempts.items():
            # Удаляем старые попытки
            recent_attempts = [attempt for attempt in attempts if current_time - attempt < self.block_duration]
            self.attempts[chat_id] = recent_attempts
            
            if len(recent_attempts) >= self.max_attempts:
                blocked_chats += 1
            
            total_attempts += len(recent_attempts)
        
        status_text = f"""
📊 <b>Статус DDoS защиты</b>

🛡️ <b>Настройки защиты:</b>
• Максимум попыток: {self.max_attempts}
• Время блокировки: {self.block_duration//60} минут

📈 <b>Текущая статистика:</b>
• Активных чатов: {total_chats}
• Заблокированных чатов: {blocked_chats}
• Всего попыток: {total_attempts}

⏰ <b>Время:</b>
• Текущее время: {time.strftime('%H:%M:%S')}
• Дата: {time.strftime('%d.%m.%Y')}

🆘 <b>Поддержка:</b> @abramov_1
        """.strip()
        
        await update.message.reply_text(status_text, parse_mode='HTML')

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        error_msg = str(context.error) if context.error else "Неизвестная ошибка"
        logger.error(f"Ошибка бота: {error_msg}")
        
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ <b>Произошла ошибка</b>\n\n"
                    "🚨 Что-то пошло не так при обработке запроса\n\n"
                    "🔄 Попробуйте позже или используйте /start\n\n"
                    "🆘 <b>Поддержка:</b> @abramov_1",
                    parse_mode='HTML'
                )
            except Exception as e:
                # Если не удалось отправить HTML сообщение, отправляем обычный текст
                logger.error(f"Не удалось отправить сообщение об ошибке: {e}")
                try:
                    await update.effective_message.reply_text(
                        "❌ Произошла ошибка\n\n"
                        "🚨 Что-то пошло не так при обработке вашего запроса\n\n"
                        "🔄 Попробуйте позже или используйте /start\n"
                        "🆘 Поддержка: @abramov_1"
                    )
                except Exception as e2:
                    logger.error(f"Не удалось отправить даже обычное сообщение: {e2}")

    async def share_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет кнопку для запроса контакта пользователя"""
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "Пожалуйста, поделитесь своим номером телефона, нажав на кнопку ниже:",
            reply_markup=reply_markup
        )

    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        contact = update.message.contact
        chat_id = update.effective_chat.id
        phone_number = contact.phone_number
        if not phone_number.startswith('+'):
            phone_number = f'+{phone_number}'
        phone_number = phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        from telegram import ReplyKeyboardRemove
        # 1. Сообщение о получении номера
        await update.message.reply_text(
            "Спасибо! Ваш номер получен и отправлен на верификацию.",
            reply_markup=ReplyKeyboardRemove()
        )
        # 2. Запускаем процесс верификации и отправляем результат отдельным сообщением
        class FakeMessage:
            def __init__(self, text, chat_id, user):
                self.text = text
                self.chat = type('obj', (object,), {'id': chat_id})
                self.from_user = user
            async def reply_text(self, *args, **kwargs):
                return await update.message.reply_text(*args, **kwargs)
        fake_update = Update(
            update.update_id,
            message=FakeMessage(phone_number, chat_id, update.effective_user)
        )
        # handle_phone_number теперь не отправляет промежуточные сообщения, а только финальный результат
        await self.handle_phone_number(fake_update, context, silent_processing=True)

    async def whoami_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        chat_id = update.effective_chat.id
        username = user.username or '(нет)'
        first_name = user.first_name or ''
        last_name = user.last_name or ''
        msg = (
            "🆔 <b>Ваши данные Telegram</b>\n\n"
            f"<b>Chat ID:</b> <code>{chat_id}</code>\n"
            f"<b>Username:</b> @{username}\n"
            f"<b>Имя:</b> {first_name}\n"
            f"<b>Фамилия:</b> {last_name}\n\n"
            "<i>Используйте эти данные для интеграции с Place&Play API или поддержки.</i>"
        )
        await update.message.reply_text(msg, parse_mode='HTML')

def main():
    """Основная функция запуска бота"""
    logger.info("🚀 Запуск Place&Play Telegram Bot...")
    
    # Создаем экземпляр бота
    bot = PlaceAndPlayBot()
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("support", bot.support_command))
    application.add_handler(CommandHandler("status", bot.status_command))
    application.add_handler(CommandHandler("share", bot.share_command))
    application.add_handler(CommandHandler("whoami", bot.whoami_command))
    application.add_handler(MessageHandler(filters.CONTACT, bot.handle_contact))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: update.message.reply_text("❌ В этом боте можно использовать только команды. Для начала нажмите /start или /share.")))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(bot.error_handler)
    
    # Запускаем бота
    logger.info("✅ Place&Play Telegram Bot запущен и готов к работе!")
    logger.info(f"🔗 Токен: {TELEGRAM_BOT_TOKEN[:10]}...")
    logger.info(f"🌐 Place&Play API: {PLACE_AND_PLAY_API_BASE_URL}")
    logger.info(f"🛡️ DDoS защита: максимум {bot.max_attempts} попыток, блокировка на {bot.block_duration//60} минут")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    main()
