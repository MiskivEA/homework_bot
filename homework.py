import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from custom_exceptions import (ErrorSendMessage, ResponseNot200, SpamBotError)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 3
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


sent_messages = ''


def send_message(bot, message):
    """Функция отправки сообщений в Telegram."""
    global sent_messages
    try:
        if message != sent_messages:
            bot.send_message(TELEGRAM_CHAT_ID, message)
            logging.info(f'Отправлено сообщение в Telegram : {message}')
            sent_messages = message
        else:
            logging.info('Попытка отправить два одинаковых сообщения подряд')
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

    except Exception as error:
        raise Exception(f'Ошибка обработки данных АПИ {error}')
    else:
        return response.json()


def check_response(response):
    """Вытаскиваю список работ из ответа АПИ и возвращаю их."""
    response_is_dict = isinstance(response, dict)
    if not response_is_dict:
        raise TypeError(f'Ожидается тип данных "словарь",'
                        f'получен {type(response)}')

    correct_keys = all([response['homeworks'], response['current_date']])
    if correct_keys:
        correct_type_data = isinstance(response['homeworks'], list)
        if not correct_type_data:
            raise TypeError(f'Ожидается тип данных "список",'
                            f'получен {type(response["homeworks"])}')
        return response['homeworks']
    raise KeyError(f'Не найдены необходимые ключи словаря {response}')


def parse_status(homework):
    """Обработка данных АПИ о конкретной ДЗ.
    Формирование статуса ДЗ и сообщения для
    отправки в Telegram
    """
    status_key = 'status'
    if status_key in homework:
        homework_name = homework.get('homework_name')
        homework_status = homework[status_key]
        if homework_status in HOMEWORK_STATUSES:
            verdict = HOMEWORK_STATUSES[homework_status]
            return (f'Изменился статус проверки работы "{homework_name}".'
                    f' {verdict}')

        raise KeyError('Несуществующий статус ДЗ')
    raise KeyError('Отсутствует данные о статусе ДЗ')


def check_tokens():
    """Проверка токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def get_homework(list_homeworks):
    """Упрощение основной функции.
    Здесь функционал который определяет, что появился новый статус
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

    while True:
        try:
            response = get_api_answer(current_timestamp)
            if response.get('homeworks'):
                list_homeworks = check_response(response)
                homework = get_homework(list_homeworks)
                message = parse_status(homework)
                send_message(bot, message)
            current_timestamp = response.get('current_date')
            logging.info(f'Время из response: {current_timestamp}')
        except SpamBotError as error:
            logging.info(f'{error}')
        except ErrorSendMessage as error:
            logging.error(f'Сбой при отправке'
                          f'сообщения в Telegram: {error}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
