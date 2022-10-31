import os
import requests
from dotenv import load_dotenv
import time
import telegram
import logging

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
    filemode='w'
)


class TokenAccessError(Exception):
    """ Ошибка доступа к токенам """
    pass


class ResponseNot200(Exception):
    """ Нет ответа API """
    pass


def send_message(bot, message):
    """ Функция отправки сообщений в Telegram """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Отправлено сообщение в Telegram : {message}')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(current_timestamp):
    """ Запрос к АПИ домашки, возвращает словарь с работами и текущим временем"""
    #timestamp = current_timestamp or int(time.time())

    timestamp = current_timestamp
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != 200:
        logging.error('Нет доступа к API')
        raise ResponseNot200('Нет ответа API')
    return response.json()


def check_response(response):
    """ Вытаскиваю список работ из ответа АПИ и возвращаю их"""
    homeworks_list = []
    correct_response = response['homeworks'] and response['current_date']
    correct_type = isinstance(response['homeworks'], list)

    if not correct_response:
        logging.error('Не найдены ожидаемые ключи в ответе API')
    if not correct_type:
        logging.error('Неверный тип данных в словаре по ключу homeworks')
    if correct_type and correct_response:
        for homework in response['homeworks']:
            homeworks_list.append(homework)
        return homeworks_list


def parse_status(homework):
    """ Обработка данных АПИ о конкретной ДЗ,
        формирование статуса ДЗ
        и сообщения для отпрвки в Telegram
    """
    homework_name = homework.get('homework_name')
    try:
        homework_status = homework['status']
    except Exception as error:
        logging.error(f'Ошибка получения статуса ДЗ: {error}')
        raise error
    else:
        try:
            verdict = HOMEWORK_STATUSES[homework_status]
        except Exception as error:
            logging.error(f'В ответе АПИ незадокументированный статус. Ошибка: {error}')
            raise error
        else:
            return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """ Проверка токенов """
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    else:
        logging.critical('Отсутствие обязательных переменных окружения во время запуска бота')
        raise TokenAccessError


def main():
    """Основная логика работы бота."""

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - WEEK * 4

    if not check_tokens():
        raise TokenAccessError('Ошибка доступа к токенам')

    while True:
        try:
            response = get_api_answer(current_timestamp)
            list_homeworks = check_response(response)

            if len(list_homeworks) > 0:
                logging.info(f'Список работ: {list_homeworks}')

                homework = list_homeworks[0]
                logging.info(f'Проверяемая работа: {homework.get("homework_name")}')

                message = parse_status(homework)
                send_message(bot, message)

            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            pass


if __name__ == '__main__':
    main()
