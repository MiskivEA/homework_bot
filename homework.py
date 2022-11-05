import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from custom_exceptions import (ErrorSendMessage, ResponseNot200)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 5
WEEK = 7 * 24 * 60 * 60
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='bot_logs.log',
    filemode='w',
    format=('[%(asctime)s], [%(levelname)s], [%(message)s],'
            ' [Модуль: %(module)s], [Имя функции: %(funcName)s],'
            ' [Строка: %(lineno)s]')
)


class MessageWithoutDublicate:
    """Функционал предотвращения отправки дублирующих сообщений в Telegram."""

    def __init__(self, bot, previous_message=None):
        """Создания объекта-отправителя сообщений."""
        self.previous_message = previous_message or ''
        self.bot = bot

    def check_and_send_message(self, message):
        """Проверка, отправка сообщения, перезапись отправленного сообщения."""
        if message != self.previous_message:
            send_message(self.bot, message)
            self.previous_message = message


def send_message(bot, message):
    """Функция отправки сообщений в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Отправлено сообщение в Telegram : {message}')
    except Exception as error:
        raise ErrorSendMessage(f'Ошибка функции отправки сообщений >> {error}')


def get_api_answer(current_timestamp):
    """Запрос к АПИ домашки.
    Возвращает словарь с работами и текущим временем
    """
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            raise ResponseNot200(
                'Нет ответа API:'
                f' Код ответа: {response.status_code}'
                f' URL: {response.request.url}'
                f' Headers: {response.request.headers}'
                f' Parameters: {params}'
            )
        response_json = response.json()
    except Exception as error:
        raise Exception(f'Ошибка обработки данных АПИ {error}')
    else:
        return response_json


def check_response(response_json):
    """Вытаскиваю список работ из ответа АПИ и возвращаю их.
    Проверка на то, что:
    1. response это словарь
    2. ключи homeworks и current_date существуют
    3. под ключом homeworks находится список
    """
    if not isinstance(response_json, dict):
        raise TypeError(f'Ожидается тип данных "словарь",'
                        f'получен {type(response_json)}')

    if not len(response_json) > 0:
        raise Exception('Пустой словарь')

    if ('homeworks' not in response_json
            and 'current_date' not in response_json):
        raise KeyError(f'В ответе нет нужных ключей {response_json}')

    if not isinstance(response_json['homeworks'], list):
        raise TypeError(f'Ожидается тип данных "список",'
                        f'получен {type(response_json["homeworks"])}')
    return response_json['homeworks']


def parse_status(homework):
    """Обработка данных АПИ о конкретной ДЗ.
    Формирование статуса ДЗ и сообщения для
    отправки в Telegram
    """
    if 'status' not in homework:
        raise KeyError('Нет ключа статус в словаре')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError('Ошибка получения статуса ДЗ')

    verdict = HOMEWORK_STATUSES[homework_status]
    return (f'Изменился статус проверки работы "{homework_name}".'
            f' {verdict}')


def check_tokens():
    """Проверка токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def get_homework(list_homeworks):
    """Упрощение основной функции.
    Здесь функционал, который определяет, что появился новый статус
    ДЗ, возвращает конкретную работу из списка работ
    """
    if list_homeworks:
        logging.info(f'Список работ: {list_homeworks}')
        homework = list_homeworks[0]
        logging.info(f'Проверяемая работа:'
                     f'{homework.get("homework_name")}')
        return homework


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствие обязательных переменных'
                         ' окружения во время запуска бота')
        sys.exit('Ошибка доступа к токенам')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - WEEK * 4
    sender = MessageWithoutDublicate(bot)

    while True:
        try:
            response_json = get_api_answer(current_timestamp)
            list_homeworks = check_response(response_json)
            if list_homeworks:
                homework = get_homework(list_homeworks)
                message = parse_status(homework)
                sender.check_and_send_message(message)
            current_timestamp = response_json.get('current_date')
            logging.info(f'Время из response: {current_timestamp}')
        except ErrorSendMessage as error:
            logging.error(f'Сбой при отправке'
                          f'сообщения в Telegram: {error}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            sender.check_and_send_message(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
