"""
Place&Play Agent - Агент для интеграции с существующим API верификации
"""
import os
import logging
import requests
import jwt
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv('config.env')

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PlaceAndPlayAgent:
    """Агент для работы с Place&Play API верификации"""
    
    def __init__(self):
        """Инициализация агента"""
        self.api_base_url = os.getenv('PLACE_AND_PLAY_API_BASE_URL', 'http://95.46.96.94:8080/PlaceAndPlay/api')
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.login_email = os.getenv('PLACE_AND_PLAY_LOGIN_EMAIL')
        self.login_password = os.getenv('PLACE_AND_PLAY_LOGIN_PASSWORD')
        self.jwt_secret = os.getenv('JWT_SECRET', secrets.token_urlsafe(32))
        
        if not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN не найден в config.env")
        if not self.api_base_url:
            raise ValueError("PLACE_AND_PLAY_API_BASE_URL не найден в config.env")
        
        logger.info(f"Place&Play Agent инициализирован. API: {self.api_base_url}")

    def generate_verification_link(self, phone_number: str, access_token: str, refresh_token: str, bot_username: str) -> Dict:
        """
        Генерирует ссылку для верификации номера телефона
        
        Args:
            phone_number: Номер телефона для верификации
            access_token: Токен доступа пользователя
            refresh_token: Токен обновления пользователя
            bot_username: Username бота (без @)
            
        Returns:
            Словарь с ссылкой и токеном
        """
        try:
            # Создаем JWT токен с данными пользователя
            payload = {
                'phone_number': phone_number,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'exp': datetime.utcnow() + timedelta(hours=24),  # Токен действителен 24 часа
                'iat': datetime.utcnow(),
                'type': 'verification'
            }
            
            jwt_token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
            
            # Формируем ссылку для бота
            bot_link = f"https://t.me/{bot_username}?start={jwt_token}"
            
            logger.info(f"Сгенерирована ссылка верификации для номера: {phone_number}")
            
            return {
                "success": True,
                "verification_link": bot_link,
                "jwt_token": jwt_token,
                "phone_number": phone_number,
                "expires_at": payload['exp'].isoformat(),
                "message": "Ссылка для верификации сгенерирована"
            }
            
        except Exception as e:
            logger.error(f"Ошибка при генерации ссылки верификации: {str(e)}")
            return {
                "success": False,
                "error": "LINK_GENERATION_ERROR",
                "message": f"Ошибка при генерации ссылки: {str(e)}"
            }

    def validate_verification_token(self, jwt_token: str) -> Dict:
        """
        Валидирует JWT токен верификации
        
        Args:
            jwt_token: JWT токен для валидации
            
        Returns:
            Результат валидации с данными пользователя
        """
        try:
            # Декодируем JWT токен
            payload = jwt.decode(jwt_token, self.jwt_secret, algorithms=['HS256'])
            
            # Проверяем тип токена
            if payload.get('type') != 'verification':
                return {
                    "success": False,
                    "error": "INVALID_TOKEN_TYPE",
                    "message": "Неверный тип токена"
                }
            
            # Проверяем срок действия
            if datetime.utcnow() > datetime.fromisoformat(payload['exp'].isoformat()):
                return {
                    "success": False,
                    "error": "TOKEN_EXPIRED",
                    "message": "Токен истек"
                }
            
            logger.info(f"JWT токен успешно валидирован для номера: {payload['phone_number']}")
            
            return {
                "success": True,
                "phone_number": payload['phone_number'],
                "access_token": payload['access_token'],
                "refresh_token": payload['refresh_token'],
                "expires_at": payload['exp'].isoformat(),
                "message": "Токен валиден"
            }
            
        except jwt.ExpiredSignatureError:
            return {
                "success": False,
                "error": "TOKEN_EXPIRED",
                "message": "Токен истек"
            }
        except jwt.InvalidTokenError:
            return {
                "success": False,
                "error": "INVALID_TOKEN",
                "message": "Неверный токен"
            }
        except Exception as e:
            logger.error(f"Ошибка при валидации токена: {str(e)}")
            return {
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": f"Ошибка валидации: {str(e)}"
            }

    def process_verification_from_token(self, jwt_token: str, chat_id: int) -> Dict:
        """
        Обрабатывает верификацию по JWT токену
        
        Args:
            jwt_token: JWT токен верификации
            chat_id: ID чата в Telegram
            
        Returns:
            Результат обработки верификации
        """
        try:
            logger.info(f"Обработка верификации по токену для чата {chat_id}")
            
            # Валидируем токен
            token_validation = self.validate_verification_token(jwt_token)
            if not token_validation["success"]:
                error_message = f"""
❌ <b>Ошибка валидации токена</b>

🚨 Проблема: {token_validation['message']}

🔄 <b>Получите новую ссылку для верификации</b>
                """.strip()
                
                self.send_telegram_message(chat_id, error_message)
                return token_validation
            
            # Получаем данные из токена
            phone_number = token_validation["phone_number"]
            access_token = token_validation["access_token"]
            refresh_token = token_validation["refresh_token"]
            
            logger.info(f"Токен валиден. Номер: {phone_number}")
            
            # Запрашиваем код верификации
            api_result = self.request_verification_code(phone_number, access_token, refresh_token)
            
            if api_result.get("success") and api_result.get("code"):
                code = api_result["code"]
                message = (
                    "🔐 <b>Ваш код подтверждения</b>\n\n"
                    f"📱 Номер: <code>{phone_number}</code>\n"
                    f"🔢 Код: <code>{code}</code>\n\n"
                    "⚠️ <i>Никому не передавайте этот код</i>\n"
                    "💡 <i>Введите код в приложении для подтверждения</i>\n\n"
                    "✅ <b>Верификация успешно инициирована!</b>"
                )
                
                self.send_telegram_message(chat_id, message)
                return {
                    "success": True,
                    "message": "Код верификации отправлен пользователю",
                    "phone_number": phone_number,
                    "code": code,
                    "chat_id": chat_id
                }
            else:
                error_text = api_result.get("message", "Неизвестная ошибка")
                error_type = api_result.get("error", "UNKNOWN_ERROR")
                
                if error_type == "AUTH_ERROR":
                    message = (
                        "❌ <b>Ошибка аутентификации</b>\n\n"
                        f"📱 Номер: <code>{phone_number}</code>\n"
                        "🔑 Проблема: Неверные токены доступа\n\n"
                        "🔄 <b>Попробуйте войти в приложение заново</b>"
                    )
                else:
                    message = (
                        "❌ <b>Ошибка при запросе кода</b>\n\n"
                        f"📱 Номер: <code>{phone_number}</code>\n"
                        f"🚨 Проблема: {error_text}\n\n"
                        "🔄 <b>Попробуйте позже или обратитесь в поддержку</b>"
                    )
                
                self.send_telegram_message(chat_id, message)
                return {
                    "success": False,
                    "error": error_type,
                    "message": error_text,
                    "phone_number": phone_number
                }
                
        except Exception as e:
            error_msg = f"Ошибка при обработке верификации по токену: {str(e)}"
            logger.error(error_msg)
            
            error_message = f"""
❌ <b>Внутренняя ошибка</b>

🚨 Проблема: {error_msg}

🔄 <b>Попробуйте позже или обратитесь в поддержку</b>
            """.strip()
            
            self.send_telegram_message(chat_id, error_message)
            
            return {
                "success": False,
                "error": "INTERNAL_ERROR",
                "message": error_msg
            }

    def _find_code_in_payload(self, payload: Any) -> Optional[str]:
        """Ищем значение кода в произвольной структуре ответа (dict/list)."""
        TARGET_KEYS = {"code", "verificationCode", "otp", "otpCode"}
        try:
            if isinstance(payload, dict):
                for key, value in payload.items():
                    lower_key = str(key).lower()
                    if lower_key in TARGET_KEYS and isinstance(value, (str, int)):
                        return str(value)
                    # Рекурсивный спуск
                    found = self._find_code_in_payload(value)
                    if found:
                        return found
            elif isinstance(payload, list):
                for item in payload:
                    found = self._find_code_in_payload(item)
                    if found:
                        return found
            return None
        except Exception:
            return None

    def get_auth_tokens(self) -> Dict:
        """
        Получает accessToken и refreshToken через API login
        """
        try:
            login_url = f"{self.api_base_url}/auth/login"
            login_data = {
                "phoneNumber": "telegrambot@gmail.com",
                "password": "TelegramBotPlaceAndPlay"
            }
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'PlaceAndPlay-TelegramBot/1.0',
                'isUser': 'true',
                'language': 'uz'
            }
            
            logger.info(f"Получение токенов аутентификации...")
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
                            "refresh_token": refresh_token,
                            "message": "Токены получены успешно"
                        }
                    else:
                        logger.error("Токены не найдены в ответе API")
                        return {
                            "success": False,
                            "error": "TOKENS_NOT_FOUND",
                            "message": "Токены не найдены в ответе API"
                        }
                else:
                    logger.error(f"Неверный формат ответа API: {response_data}")
                    return {
                        "success": False,
                        "error": "INVALID_RESPONSE",
                        "message": f"Неверный формат ответа API: {response_data.get('message', 'Unknown error')}"
                    }
            else:
                logger.error(f"Ошибка API login: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": "LOGIN_API_ERROR",
                    "message": f"Ошибка API login: {response.status_code} - {response.text}"
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при получении токенов: {str(e)}")
            return {
                "success": False,
                "error": "NETWORK_ERROR",
                "message": f"Ошибка сети: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении токенов: {str(e)}")
            return {
                "success": False,
                "error": "UNKNOWN_ERROR",
                "message": f"Неожиданная ошибка: {str(e)}"
            }

    def request_verification_code(self, phone_number: str, access_token: str = None, refresh_token: str = None) -> Dict:
        """
        Запрашивает код верификации через существующее API (GET /auth/phoneNumberVerification)
        Теперь поддерживает передачу токенов аутентификации
        """
        try:
            url = f"{self.api_base_url}/auth/phoneNumberVerification"
            params = {"phoneNumber": phone_number}
            
            # Подготавливаем заголовки с токенами, если они переданы
            headers = {
                'User-Agent': 'PlaceAndPlay-TelegramBot/1.0',
                'language': 'en'
            }
            
            if access_token:
                headers['accessToken'] = access_token
                logger.info(f"Используем accessToken для аутентификации")
            
            if refresh_token:
                headers['refreshToken'] = refresh_token
                logger.info(f"Используем refreshToken для аутентификации")
            
            logger.info(f"Запрос кода верификации для номера: {phone_number}")
            logger.info(f"URL: {url}")
            logger.info(f"Параметры: {params}")
            logger.info(f"Заголовки: {headers}")

            response = requests.get(url, params=params, headers=headers, timeout=30)
            logger.info(f"Ответ API: {response.status_code} - {response.text[:400]}")

            if response.status_code == 200:
                result_json = {}
                try:
                    result_json = response.json()
                except Exception:
                    pass

                code = self._find_code_in_payload(result_json)
                if code:
                    logger.info(f"Код верификации получен из ответа API: {code}")
                    return {
                        "success": True,
                        "message": f"Код получен",
                        "phone_number": phone_number,
                        "code": code,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    return {
                        "success": False,
                        "error": "CODE_NOT_FOUND",
                        "message": "Код не найден в ответе API",
                        "phone_number": phone_number,
                        "raw_response": result_json,
                        "timestamp": datetime.now().isoformat()
                    }
            elif response.status_code == 401:
                logger.warning(f"Ошибка аутентификации (401) для номера {phone_number}")
                return {
                    "success": False,
                    "error": "AUTH_ERROR",
                    "message": "Ошибка аутентификации. Проверьте токены доступа.",
                    "phone_number": phone_number,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": "API_ERROR",
                    "message": f"Ошибка API: {response.status_code} - {response.text}",
                    "phone_number": phone_number,
                    "raw_response": response.text,
                    "timestamp": datetime.now().isoformat()
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": "NETWORK_ERROR",
                "message": f"Ошибка сети при запросе кода: {str(e)}",
                "phone_number": phone_number,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": "UNKNOWN_ERROR",
                "message": f"Неожиданная ошибка: {str(e)}",
                "phone_number": phone_number,
                "timestamp": datetime.now().isoformat()
            }

    def process_verification_automatically(self, phone_number: str, chat_id: int) -> Dict:
        """
        Автоматически обрабатывает верификацию:
        1. Получает токены через API login
        2. Запрашивает код верификации с полученными токенами
        3. Отправляет результат пользователю
        """
        try:
            logger.info(f"Автоматическая обработка верификации для номера: {phone_number}")
            
            # Шаг 1: Получаем токены аутентификации
            logger.info("Шаг 1: Получение токенов аутентификации...")
            tokens_result = self.get_auth_tokens()
            
            if not tokens_result.get("success"):
                error_message = f"""
❌ <b>Ошибка получения токенов</b>

🚨 Проблема: {tokens_result.get('message', 'Неизвестная ошибка')}

🔄 <b>Попробуйте позже или обратитесь в поддержку</b>
                """.strip()
                
                self.send_telegram_message(chat_id, error_message)
                return tokens_result
            
            access_token = tokens_result["access_token"]
            refresh_token = tokens_result["refresh_token"]
            logger.info("Токены получены успешно, переходим к запросу кода...")
            
            # Шаг 2: Запрашиваем код верификации с полученными токенами
            logger.info("Шаг 2: Запрос кода верификации...")
            verification_result = self.request_verification_code(phone_number, access_token, refresh_token)
            
            if verification_result.get("success") and verification_result.get("code"):
                code = verification_result["code"]
                success_message = f"""
🔐 <b>Ваш код подтверждения</b>

📱 Номер: <code>{phone_number}</code>
🔢 Код: <code>{code}</code>

⚠️ <i>Никому не передавайте этот код</i>
💡 <i>Введите код в приложении Place&Play для подтверждения</i>

✅ <b>Верификация успешно инициирована!</b>
                """.strip()
                
                self.send_telegram_message(chat_id, success_message)
                return {
                    "success": True,
                    "message": "Код верификации отправлен пользователю",
                    "phone_number": phone_number,
                    "code": code,
                    "chat_id": chat_id
                }
            else:
                error_text = verification_result.get("message", "Неизвестная ошибка")
                error_type = verification_result.get("error", "UNKNOWN_ERROR")
                
                if error_type == "AUTH_ERROR":
                    error_message = f"""
❌ <b>Ошибка аутентификации</b>

📱 Номер: <code>{phone_number}</code>
🔑 Проблема: Неверные токены доступа

🔄 <b>Попробуйте позже или обратитесь в поддержку</b>
                    """.strip()
                else:
                    error_message = f"""
❌ <b>Ошибка при запросе кода</b>

📱 Номер: <code>{phone_number}</code>
🚨 Проблема: {error_text}

🔄 <b>Попробуйте позже или обратитесь в поддержку</b>
                    """.strip()
                
                self.send_telegram_message(chat_id, error_message)
                return verification_result
                
        except Exception as e:
            error_msg = f"Ошибка при автоматической обработке верификации: {str(e)}"
            logger.error(error_msg)
            
            error_message = f"""
❌ <b>Внутренняя ошибка</b>

🚨 Проблема: {error_msg}

🔄 <b>Попробуйте позже или обратитесь в поддержку</b>
            """.strip()
            
            self.send_telegram_message(chat_id, error_message)
            
            return {
                "success": False,
                "error": "INTERNAL_ERROR",
                "message": error_msg
            }

    def send_lottie_animation(self, chat_id: int, animation_path: str) -> bool:
        """Отправляет Lottie-анимацию (TGS) в чат"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendAnimation"
            with open(animation_path, "rb") as anim_file:
                files = {"animation": anim_file}
                data = {"chat_id": chat_id}
                response = requests.post(url, data=data, files=files, timeout=10)
            if response.status_code == 200:
                logger.info(f"Lottie-анимация отправлена в чат {chat_id}")
                return True
            else:
                logger.error(f"Ошибка отправки Lottie-анимации: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Ошибка при отправке Lottie-анимации: {str(e)}")
            return False

    def send_telegram_message(self, chat_id: int, message: str) -> bool:
        """Отправляет сообщение через Telegram бота. Если message начинается с __LOTTIE__, сначала отправляет анимацию."""
        try:
            if message.startswith("__LOTTIE__"):
                # Отправить Lottie-анимацию
                lottie_path = os.path.join(os.path.dirname(__file__), "Animation-incom-message.tgs")
                self.send_lottie_animation(chat_id, lottie_path)
                # Убрать маркер и пробелы
                message = message.replace("__LOTTIE__", "", 1).lstrip()
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info(f"Сообщение отправлено в чат {chat_id}")
                return True
            else:
                logger.error(f"Ошибка отправки сообщения: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Ошибка при отправке Telegram сообщения: {str(e)}")
            return False

    def get_user_info(self, chat_id: int) -> Dict:
        """Получает информацию о пользователе по chat_id"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/getChat"
            data = {"chat_id": chat_id}
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                chat_info = response.json()["result"]
                return {
                    "success": True,
                    "chat_id": chat_id,
                    "chat_type": chat_info.get("type"),
                    "title": chat_info.get("title"),
                    "username": chat_info.get("username"),
                    "first_name": chat_info.get("first_name"),
                    "last_name": chat_info.get("last_name")
                }
            else:
                return {
                    "success": False,
                    "error": f"Ошибка API: {response.status_code}",
                    "message": response.text
                }
        except Exception as e:
            return {
                "success": False,
                "error": "EXCEPTION",
                "message": f"Ошибка при получении информации: {str(e)}"
            }

    def send_chat_id_info(self, chat_id: int) -> bool:
        """Отправляет пользователю информацию о его chat_id"""
        user_info = self.get_user_info(chat_id)
        
        if user_info["success"]:
            message = (
                "🆔 <b>Информация о чате</b>\n\n"
                f"📱 <b>Chat ID:</b> <code>{chat_id}</code>\n"
                f"👤 <b>Тип:</b> {user_info['chat_type']}\n"
            )
            
            if user_info.get("title"):
                message += f"📝 <b>Название:</b> {user_info['title']}\n"
            if user_info.get("username"):
                message += f"🔗 <b>Username:</b> @{user_info['username']}\n"
            if user_info.get("first_name"):
                message += f"👨 <b>Имя:</b> {user_info['first_name']}\n"
            if user_info.get("last_name"):
                message += f"👨 <b>Фамилия:</b> {user_info['last_name']}\n"
            
            message += "\n💡 <i>Сохраните этот Chat ID для использования в API</i>"
        else:
            message = (
                "❌ <b>Ошибка получения информации</b>\n\n"
                f"🚨 Проблема: {user_info['message']}\n\n"
                "🔄 <b>Попробуйте позже</b>"
            )
        
        return self.send_telegram_message(chat_id, message)

    def process_verification_request(self, chat_id: int, phone_number: str, access_token: str = None, refresh_token: str = None) -> Dict:
        """
        Обрабатывает запрос: дергает API с токенами, извлекает code, отправляет его пользователю
        """
        logger.info(f"Обработка запроса верификации для чата {chat_id}, номер: {phone_number}")
        logger.info(f"Токены: accessToken={'передан' if access_token else 'не передан'}, refreshToken={'передан' if refresh_token else 'не передан'}")
        
        api_result = self.request_verification_code(phone_number, access_token, refresh_token)

        if api_result.get("success") and api_result.get("code"):
            code = api_result["code"]
            message = (
                "🔐 <b>Ваш код подтверждения</b>\n\n"
                f"📱 Номер: <code>{phone_number}</code>\n"
                f"🔢 Код: <code>{code}</code>\n\n"
                "⚠️ <i>Никому не передавайте этот код</i>\n"
                "💡 <i>Введите код в приложении для подтверждения</i>"
            )
            self.send_telegram_message(chat_id, message)
            return {"success": True, "message": "Код отправлен пользователю", "code": code}
        else:
            error_text = api_result.get("message", "Неизвестная ошибка")
            error_type = api_result.get("error", "UNKNOWN_ERROR")
            
            if error_type == "AUTH_ERROR":
                message = (
                    "❌ <b>Ошибка аутентификации</b>\n\n"
                    f"📱 Номер: <code>{phone_number}</code>\n"
                    "🔑 Проблема: Неверные токены доступа\n\n"
                    "🔄 <b>Попробуйте войти в приложение заново</b>"
                )
            else:
                message = (
                    "❌ <b>Ошибка при запросе кода</b>\n\n"
                    f"📱 Номер: <code>{phone_number}</code>\n"
                    f"🚨 Проблема: {error_text}\n\n"
                    "🔄 <b>Попробуйте позже или обратитесь в поддержку</b>"
                )
            
            self.send_telegram_message(chat_id, message)
            return {"success": False, "error": error_type, "message": error_text}

    def get_statistics(self) -> Dict:
        """Возвращает статистику работы агента"""
        return {
            "agent_status": "active",
            "api_base_url": self.api_base_url,
            "telegram_bot_configured": bool(self.telegram_bot_token),
            "api_credentials_configured": bool(self.login_email and self.login_password),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    try:
        agent = PlaceAndPlayAgent()
        print("🧪 Тестирование Place&Play Agent...")
        
        # Тест без токенов
        result = agent.request_verification_code("+998998888931")
        print(f"📱 Результат запроса кода (без токенов): {result}")
        
        # Тест с токенами (замените на реальные)
        result_with_tokens = agent.request_verification_code(
            "+998998888931", 
            access_token="test_access_token", 
            refresh_token="test_refresh_token"
        )
        print(f"📱 Результат запроса кода (с токенами): {result_with_tokens}")
        
        # Тест статистики
        stats = agent.get_statistics()
        print(f"📊 Статистика агента: {stats}")
        
        print("✅ Тестирование завершено успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
