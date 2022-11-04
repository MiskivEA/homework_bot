class ResponseNot200(Exception):
    """Нет ответа API."""

    pass


class ErrorSendMessage(Exception):
    """Ошибка отправки сообщения в Telegram"""

    pass
