"""
Place&Play Agent API Server
FastAPI сервер для интеграции с существующим Place&Play API верификации
"""
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Optional
import uvicorn
from dotenv import load_dotenv
from datetime import datetime
import requests

from place_and_play_agent import PlaceAndPlayAgent

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создаем FastAPI приложение
app = FastAPI(
    title="Place&Play Agent API",
    description="API для интеграции с существующим Place&Play API верификации",
    version="2.1.0"
)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализируем агент
try:
    agent = PlaceAndPlayAgent()
    logger.info("Place&Play Agent успешно инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации Place&Play Agent: {e}")
    agent = None

# Pydantic модели
class VerificationRequest(BaseModel):
    phone_number: str
    chat_id: int
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None

class VerificationResponse(BaseModel):
    success: bool
    message: str
    phone_number: Optional[str] = None
    code: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None

class LinkGenerationRequest(BaseModel):
    phone_number: str
    access_token: str
    refresh_token: str
    bot_username: str

class LinkGenerationResponse(BaseModel):
    success: bool
    message: str
    verification_link: Optional[str] = None
    jwt_token: Optional[str] = None
    phone_number: Optional[str] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None

class TokenVerificationRequest(BaseModel):
    jwt_token: str
    chat_id: int

class StatisticsResponse(BaseModel):
    agent_status: str
    api_base_url: str
    telegram_bot_configured: bool
    api_credentials_configured: bool
    timestamp: str

class NotificationRequest(BaseModel):
    message: str
    chatId: int

class NotificationResponse(BaseModel):
    success: bool
    message: str
    chat_id: int
    error: Optional[str] = None

class ChatIdRequest(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None

class ChatIdResponse(BaseModel):
    success: bool
    chat_id: Optional[int] = None
    error: Optional[str] = None
    message: Optional[str] = None

@app.get("/")
async def root():
    """Главная страница API"""
    return {
        "message": "Place&Play Agent API v2.3.0",
        "description": "API для интеграции с существующим Place&Play API верификации через JWT токены и автоматическую обработку",
        "features": [
            "Генерация JWT токенов для верификации",
            "Создание ссылок для перехода в Telegram бота",
            "Валидация JWT токенов",
            "Автоматическое извлечение кода из ответа API",
            "Отправка кода через Telegram бота",
            "Обработка ошибок аутентификации",
            "Получение информации о пользователях по chat_id",
            "Отправка пользователю информации о его chat_id",
            "Автоматическая обработка верификации (получение токенов + запрос кода)",
            "Получение токенов аутентификации через API login"
        ],
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "generate_link": "/api/v1/generateLink",
            "verify_from_token": "/api/v1/verifyFromToken",
            "request_code": "/api/v1/requestCode",
            "request_code_auto": "/api/v1/requestCodeAuto",
            "statistics": "/api/v1/statistics",
            "user_info": "/api/v1/user/{chat_id}",
            "send_chat_id_info": "/api/v1/sendChatIdInfo/{chat_id}"
        },
        "usage": {
            "generate_link": {
                "method": "POST",
                "url": "/api/v1/generateLink",
                "description": "Сгенерировать ссылку для верификации",
                "body": {
                    "phone_number": "string (required)",
                    "access_token": "string (required)",
                    "refresh_token": "string (required)",
                    "bot_username": "string (required)"
                }
            },
            "verify_from_token": {
                "method": "POST",
                "url": "/api/v1/verifyFromToken",
                "description": "Верифицировать номер по JWT токену",
                "body": {
                    "jwt_token": "string (required)",
                    "chat_id": "integer (required)"
                }
            },
            "request_code": {
                "method": "POST",
                "url": "/api/v1/requestCode",
                "description": "Запрос кода верификации (прямой)",
                "body": {
                    "phone_number": "string (required)",
                    "chat_id": "integer (required)",
                    "access_token": "string (optional)",
                    "refresh_token": "string (optional)"
                }
            },
            "request_code_auto": {
                "method": "POST",
                "url": "/api/v1/requestCodeAuto",
                "description": "Автоматическая обработка верификации (получение токенов + запрос кода)",
                "body": {
                    "phone_number": "string (required)",
                    "chat_id": "integer (required)"
                }
            }
        },
        "workflow": {
            "step1": "Приложение генерирует ссылку через /api/v1/generateLink",
            "step2": "Пользователь переходит по ссылке: https://t.me/bot?start=<JWT>",
            "step3": "Бот получает JWT токен и вызывает /api/v1/verifyFromToken",
            "step4": "Агент валидирует токен и дергает ваш API",
            "step5": "Код отправляется пользователю в Telegram чат"
        },
        "jwt_token_info": {
            "what_is": "JWT токен содержит зашифрованные данные пользователя",
            "contains": [
                "phone_number - номер телефона",
                "access_token - токен доступа",
                "refresh_token - токен обновления",
                "exp - время истечения (24 часа)",
                "type - тип токена (verification)"
            ],
            "security": "Токен подписан секретным ключом и имеет ограниченный срок действия"
        }
    }

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Place&Play Agent не инициализирован")
    
    return {
        "status": "healthy",
        "agent_status": "active",
        "version": "2.3.0",
        "timestamp": agent.get_statistics()["timestamp"]
    }

@app.post("/api/v1/requestCode", response_model=VerificationResponse)
async def request_verification_code(request: VerificationRequest):
    """
    Запрос кода верификации через существующее API
    
    Args:
        request: Запрос с номером телефона, ID чата и токенами аутентификации
        
    Returns:
        Результат запроса кода верификации
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Place&Play Agent не инициализирован")
    
    try:
        logger.info(f"Получен запрос на верификацию для номера: {request.phone_number}")
        logger.info(f"Chat ID: {request.chat_id}")
        logger.info(f"Токены: accessToken={'передан' if request.access_token else 'не передан'}, refreshToken={'передан' if request.refresh_token else 'не передан'}")
        
        # Обрабатываем запрос через агента
        result = agent.process_verification_request(
            request.chat_id, 
            request.phone_number, 
            request.access_token, 
            request.refresh_token
        )
        
        if result["success"]:
            logger.info(f"Код верификации успешно запрошен для {request.phone_number}")
            return VerificationResponse(
                success=True,
                message=result["message"],
                phone_number=request.phone_number,
                code=result.get("code"),
                timestamp=result.get("timestamp")
            )
        else:
            logger.warning(f"Ошибка при запросе кода для {request.phone_number}: {result.get('error')}")
            return VerificationResponse(
                success=False,
                message=result["message"],
                phone_number=request.phone_number,
                error=result.get("error"),
                timestamp=result.get("timestamp")
            )
            
    except Exception as e:
        error_msg = f"Внутренняя ошибка сервера: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/v1/requestCodeAuto", response_model=VerificationResponse)
async def request_verification_code_auto(request: VerificationRequest):
    """
    Автоматически обрабатывает верификацию:
    1. Получает токены через API login
    2. Запрашивает код верификации с полученными токенами
    3. Отправляет результат пользователю
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Place&Play Agent не инициализирован")
    
    try:
        logger.info(f"Автоматическая обработка верификации для номера: {request.phone_number}")
        logger.info(f"Chat ID: {request.chat_id}")
        
        # Автоматически обрабатываем верификацию через агента
        result = agent.process_verification_automatically(
            request.phone_number,
            request.chat_id
        )
        
        if result["success"]:
            logger.info(f"Автоматическая верификация успешно завершена для {request.phone_number}")
            return VerificationResponse(
                success=True,
                message=result["message"],
                phone_number=request.phone_number,
                code=result.get("code"),
                timestamp=result.get("timestamp")
            )
        else:
            logger.warning(f"Ошибка при автоматической верификации для {request.phone_number}: {result.get('error')}")
            return VerificationResponse(
                success=False,
                message=result["message"],
                phone_number=request.phone_number,
                error=result.get("error"),
                timestamp=result.get("timestamp")
            )
            
    except Exception as e:
        error_msg = f"Внутренняя ошибка сервера: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/v1/generateLink", response_model=LinkGenerationResponse)
async def generate_verification_link(request: LinkGenerationRequest):
    """
    Генерация ссылки для верификации номера телефона
    
    Args:
        request: Запрос с номером телефона, токенами и username бота
        
    Returns:
        Ссылка для верификации и JWT токен
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Place&Play Agent не инициализирован")
    
    try:
        logger.info(f"Генерация ссылки верификации для номера: {request.phone_number}")
        logger.info(f"Bot username: {request.bot_username}")
        
        # Генерируем ссылку через агента
        result = agent.generate_verification_link(
            request.phone_number,
            request.access_token,
            request.refresh_token,
            request.bot_username
        )
        
        if result["success"]:
            logger.info(f"Ссылка верификации успешно сгенерирована для {request.phone_number}")
            return LinkGenerationResponse(
                success=True,
                message=result["message"],
                verification_link=result.get("verification_link"),
                jwt_token=result.get("jwt_token"),
                phone_number=result.get("phone_number"),
                expires_at=result.get("expires_at")
            )
        else:
            logger.warning(f"Ошибка при генерации ссылки для {request.phone_number}: {result.get('error')}")
            return LinkGenerationResponse(
                success=False,
                message=result["message"],
                error=result.get("error"),
                phone_number=request.phone_number
            )
            
    except Exception as e:
        error_msg = f"Внутренняя ошибка сервера: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/v1/verifyFromToken", response_model=VerificationResponse)
async def verify_from_token(request: TokenVerificationRequest):
    """
    Верификация номера телефона по JWT токену
    
    Args:
        request: Запрос с JWT токеном и ID чата
        
    Returns:
        Результат верификации
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Place&Play Agent не инициализирован")
    
    try:
        logger.info(f"Верификация по токену для чата: {request.chat_id}")
        
        # Обрабатываем верификацию по токену через агента
        result = agent.process_verification_from_token(
            request.jwt_token,
            request.chat_id
        )
        
        if result["success"]:
            logger.info(f"Верификация по токену успешно выполнена для чата {request.chat_id}")
            return VerificationResponse(
                success=True,
                message=result["message"],
                phone_number=result.get("phone_number"),
                code=result.get("code"),
                timestamp=datetime.now().isoformat()
            )
        else:
            logger.warning(f"Ошибка при верификации по токену для чата {request.chat_id}: {result.get('error')}")
            return VerificationResponse(
                success=False,
                message=result["message"],
                error=result.get("error"),
                phone_number=result.get("phone_number"),
                timestamp=datetime.now().isoformat()
            )
            
    except Exception as e:
        error_msg = f"Внутренняя ошибка сервера: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/api/v1/statistics", response_model=StatisticsResponse)
async def get_statistics():
    """Получение статистики работы агента"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Place&Play Agent не инициализирован")
    
    try:
        stats = agent.get_statistics()
        return StatisticsResponse(**stats)
    except Exception as e:
        error_msg = f"Ошибка при получении статистики: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/api/v1/user/{chat_id}")
async def get_user_info(chat_id: int):
    """Получение информации о пользователе по chat_id"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Place&Play Agent не инициализирован")
    
    try:
        user_info = agent.get_user_info(chat_id)
        if user_info["success"]:
            return user_info
        else:
            raise HTTPException(status_code=400, detail=user_info["message"])
    except Exception as e:
        error_msg = f"Ошибка при получении информации о пользователе: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/v1/sendChatIdInfo/{chat_id}")
async def send_chat_id_info(chat_id: int):
    """Отправка пользователю информации о его chat_id"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Place&Play Agent не инициализирован")
    
    try:
        success = agent.send_chat_id_info(chat_id)
        if success:
            return {
                "success": True,
                "message": f"Информация о chat_id отправлена в чат {chat_id}",
                "chat_id": chat_id
            }
        else:
            raise HTTPException(status_code=500, detail="Не удалось отправить сообщение")
    except Exception as e:
        error_msg = f"Ошибка при отправке информации о chat_id: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/v1/sendNotification", response_model=NotificationResponse)
async def send_notification(request: NotificationRequest):
    """
    Отправляет сообщение в указанный чат через Telegram-бота
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Place&Play Agent не инициализирован")
    try:
        logger.info(f"Отправка уведомления в чат {request.chatId}: {request.message}")
        # Формируем новый текст уведомления
        message = (
            "🆕🎉 Новое событие!\n"
            "🔔 Получено новое уведомление о регистрации в вашем заведении.\n"
            "Проверьте подробности по ссылке: <a href=\"https://placeandplay.uz/organization.html\">проверить событие</a>"
        )
        success = agent.send_telegram_message(request.chatId, message)
        if success:
            return NotificationResponse(success=True, message="Уведомление отправлено", chat_id=request.chatId)
        else:
            return NotificationResponse(success=False, message="Ошибка отправки уведомления", chat_id=request.chatId, error="SEND_ERROR")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при отправке уведомления: {str(e)}")

@app.post("/api/v1/getChatId", response_model=ChatIdResponse)
async def get_chat_id(request: ChatIdRequest):
    """
    Получить chat_id по username или user_id через Telegram Bot API
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Place&Play Agent не инициализирован")
    try:
        if request.user_id:
            chat_id = request.user_id
            return ChatIdResponse(success=True, chat_id=chat_id, message="chat_id найден по user_id")
        elif request.username:
            # Получаем chat_id по username через Telegram API
            url = f"https://api.telegram.org/bot{agent.telegram_bot_token}/getChat"
            data = {"chat_id": f"@{request.username}"}
            resp = requests.post(url, json=data, timeout=10)
            if resp.status_code == 200:
                chat_info = resp.json().get("result", {})
                chat_id = chat_info.get("id")
                if chat_id:
                    return ChatIdResponse(success=True, chat_id=chat_id, message="chat_id найден по username")
                else:
                    return ChatIdResponse(success=False, error="NOT_FOUND", message="chat_id не найден по username")
            else:
                return ChatIdResponse(success=False, error="API_ERROR", message=f"Ошибка Telegram API: {resp.text}")
        else:
            return ChatIdResponse(success=False, error="NO_INPUT", message="Не передан username или user_id")
    except Exception as e:
        logger.error(f"Ошибка при получении chat_id: {str(e)}")
        return ChatIdResponse(success=False, error="EXCEPTION", message=f"Ошибка: {str(e)}")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик исключений"""
    logger.error(f"Необработанное исключение: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Внутренняя ошибка сервера"
        }
    )

if __name__ == "__main__":
    logger.info("🚀 Запуск Place&Play Agent API Server v2.1.0...")
    
    if agent is None:
        logger.error("❌ Place&Play Agent не может быть инициализирован. Проверьте config.env")
        exit(1)
    
    # Запускаем сервер
    uvicorn.run(
        "place_and_play_api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
