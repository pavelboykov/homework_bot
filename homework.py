import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.DEBUG,
    filename='./homework_log.log',
    format='%(asctime)s [%(levelname)s] %(message)s',
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram чат"""
    try:
        logger.info(f'Бот отправил сообщение: "{message}"')
        return bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(f'Боту не удалось отправить сообщение: "{error}"')
        raise exceptions.SendMessageException(error)


def get_api_answer(current_timestamp):
    """Функция делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        message = f'Эндпоинт {ENDPOINT} недоступен: {error}'
        logger.error(message)
        raise exceptions.GetAPIAnswerException(message)
    if homework_statuses.status_code != 200:
        message = f'Код ответа API: {homework_statuses.status_code}'
        logger.error(message)
        raise exceptions.GetAPIAnswerException(message)
    return homework_statuses.json()


def check_response(response):
    """Функция проверки корректности данных,
    запрошенных от API сервиса Практикум.Домашка
    """
    if type(response) != dict:
        message = \
            f'Тип данных в ответе от API не соотвествует ожидаемому.' \
            f' Получен: {type(response)}'
        logger.error(message)
        raise TypeError(message)
    try:
        homeworks_list = response['homeworks']
    except KeyError as error:
        message = f'Ключ homeworks недоступен: {error}'
        logger.error(message)
        raise exceptions.CheckResponseException(message)
    if type(homeworks_list) != list:
        message = \
            f'В ответе от API домашки приходят не в виде списка. ' \
            f'Получен: {type(homeworks_list)}'
        logger.error(message)
        raise TypeError(message)
    return homeworks_list


def parse_status(homework):
    """Функция извлекает из информации
    о конкретной домашней работе статус этой работы.
    """
    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы ' \
               f'"{homework_name}". {verdict}'
    else:
        message = \
            f'Передан неизвестный статус домашней работы "{homework_status}"'
        logger.error(message)
        raise exceptions.ParseStatusException(message)


def check_tokens():
    """Функция проверяет доступность переменных окружения,
    которые необходимы для работы программы.
    """
    env_variables = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    availability_env_variables = True
    for key in env_variables:
        if env_variables[key] is None:
            availability_env_variables = False
            message = \
                f'Отсутствует обязательная переменная окружения: ' \
                f'{key}\nПрограмма принудительно остановлена.'
            logger.critical(message)
    return availability_env_variables


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError('Проверьте переменные окружения')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_status = ''
    current_error = ''
    while True:
        try:
            current_timestamp = int(time.time())
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if len(homework) == 0:
                logger.info('Статус не обновлен')
            else:
                homework_status = parse_status(homework[0])
                if current_status == homework_status:
                    logger.info(homework_status)
                else:
                    current_status = homework_status
                    send_message(bot, homework_status)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if current_error != str(error):
                current_error = str(error)
                send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
