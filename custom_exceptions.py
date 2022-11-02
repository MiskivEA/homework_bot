class ResponseNot200(Exception):
    """Нет ответа API."""

    pass


class StatusIsUnregistered(Exception):
    """Получен незадокументированный статус ДЗ"""

    pass


class ErrorSendMessage(Exception):
    """Ошибка отправки сообщения в Telegram"""

    pass