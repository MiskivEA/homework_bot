import os
import sys

import requests
from dotenv import load_dotenv
import time
import telegram
import logging

from custom_exceptions import *

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
WEEK = 7 * 24 * 60 * 60

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
            ' [Модуль: %(module)s], [Имя функции: %(funcName)s], [Строка: %(lineno)s]')
)


def send_message(bot, message):
    """Функция отправки сообщений в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Отправлено сообщение в Telegram : {message}')
    except Exception as error:
        raise ErrorSendMessage(f'Ошибка отправки сообщения {error}')


def get_api_answer(current_timestamp):
    """Запрос к АПИ домашки.
    Возвращает словарь с работами и текущим временем
    """
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != 200:

        raise ResponseNot200(
            'Нет ответа API:'
            f' Код ответа: {response.status_code}'
            f' URL: {response.request.url}'
            f' Headers: {response.request.headers}'
            f' Parameters: {params}'
        )
    try:
        return response.json()
    except Exception as error:
        raise error


def check_response(response):
    """Вытаскиваю список работ из ответа АПИ и возвращаю их."""
    response_is_dict = isinstance(response, dict)
    if not response_is_dict:
        raise TypeError(f'Ожидается тип данных "словарь",'
                        f'получен {type(response)}')
    if len(response['homeworks']) > 0:
        correct_keys = response['homeworks'] and response['current_date']
        if not correct_keys:
            raise KeyError(f'Не найдены необходимые ключи словаря {response}')

        correct_type_data = isinstance(response['homeworks'], list)
        if not correct_type_data:
            raise TypeError(f'Ожидается тип данных "список",'
                            f'получен {type(response["homeworks"])}')
    try:
        return response['homeworks']
    except Exception as error:
        raise error


def parse_status(homework):
    """Обработка данных АПИ о конкретной ДЗ.
    Формирование статуса ДЗ и сообщения для
    отправки в Telegram
    """
    homework_name = homework.get('homework_name')
    if homework['status']:
        homework_status = homework['status']

        try:
            verdict = HOMEWORK_STATUSES[homework_status]
        except StatusIsUnregistered as error:
            raise error

        else:
            return (f'Изменился статус проверки работы "{homework_name}".'
                    f' {verdict}')


def check_tokens():
    """Проверка токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствие обязательных переменных'
                         ' окружения во время запуска бота')
        raise sys.exit('Ошибка доступа к токенам')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - WEEK * 4
    sent_messages = ['1']
    while True:
        try:
            try:
                response = get_api_answer(current_timestamp)
                list_homeworks = check_response(response)
                if len(list_homeworks) > 0:
                    logging.info(f'Список работ: {list_homeworks}')

                    homework = list_homeworks[0]
                    logging.info(f'Проверяемая работа:'
                                 f'{homework.get("homework_name")}')

                    message = parse_status(homework)

                    try:
                        if message not in sent_messages:
                            send_message(bot, message)
                            sent_messages.append(message)
                        else:
                            send_message(bot, 'I`m SPAM_BOT =)')

                    except ErrorSendMessage as error:
                        logging.error(f'{error}')
                    except Exception as error:
                        logging.error(f'Сбой при отправке'
                                      f'сообщения в Telegram: {error}')

                current_timestamp = response.get('current_date')
                logging.info(f'Время из response: {current_timestamp}')

            except ResponseNot200 as error:
                logging.error(f'{error}')
                send_message(bot, f'{error}')
            except KeyError as error:
                logging.error(f'{error}')
            except TypeError as error:
                logging.error(f'{error}')
            except Exception as error:
                logging.error(f'API ERROR: {error}')

        except ErrorSendMessage as error:
            logging.error(f'{error}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message not in sent_messages:
                send_message(bot, message)
                sent_messages.append(message)
            time.sleep(RETRY_TIME)

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
