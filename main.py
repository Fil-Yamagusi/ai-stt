#!/usr/bin/env python3.12
# -*- coding: utf-8 -*-
"""2024-04-30 Fil - Future code Yandex.Practicum
Yandex SpeechKit - Speech Recognition
README.md for more

Fil FC Speech-to-text
@fil_fc_ai_stt_bot
https://t.me/fil_fc_ai_stt_bot
"""
__version__ = '0.1'
__author__ = 'Firip Yamagusi'

from time import time_ns, strftime
from math import ceil

# third-party
import logging
from telebot import TeleBot
from telebot.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, Message, File
import soundfile as sf

# custom
# для авторизации и для ограничений
from config import MAIN, TB, YANDEX, LIM
from stt_db import (
    get_db_connection,
    create_db,
    is_limit_user,
    is_limit_stt_blocks,
    create_user,
    add_file2remove,
    insert_stt,
    is_limit,
)

from stt_stt import (
    ask_speech_recognition,
    ask_speech_kit_stt,
)

if MAIN['test_mode']:  # Настройки для этапа тестирования
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%F %T',
        level=logging.INFO,
    )
else:  # Настройки для опубликованного бота
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%F %T',
        level=logging.INFO,
        filename=MAIN['log_filename'],
        filemode="w",
        encoding='utf-8',
    )

# *******************************************************************
# ПОНЕСЛАСЬ! В АКАКУ!
logging.warning(f"MAIN: start")

# Подключаемся к БД и создаём таблицы (если не было). Без БД не сможем работать
db_conn = get_db_connection(MAIN['db_filename'])
if db_conn == False:
    logging.error(f"MAIN: DB cannot open connection")
    exit(1)
logging.warning(f"MAIN: DB open connection")

if create_db(db_conn) == False:
    logging.error(f"MAIN DB: cannot create tables")
    db_conn.close()
    exit(2)

bot = TeleBot(TB['TOKEN'])
logging.warning(f"TB: start: {TB['BOT_USERNAME']} | {TB['BOT_NAME']}")

# Пустое меню, может пригодиться
hideKeyboard = ReplyKeyboardRemove()

# Текстовые фразы. В словаре, чтобы легче управлять
T = {}
# Кнопка для выхода из проверки TTS, STT (вдруг не хочет тратить ИИ-ресурсы)
# t_stop_test = 'Отказаться от проверки'
T['t_stop_test'] = 'Отказаться от проверки'

mu_test_stt = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
mu_test_stt.add(*[T['t_stop_test']])

# Словарь с пользователями в памяти, чтобы не мучить БД
user_data = {}


def convert_ogg_to_wav(input_file: str, output_file: str) -> tuple:
    """
    Для бесплатного STT нужен WAV
    https://pypi.org/project/soundfile/
    """
    try:
        data, samplerate = sf.read(input_file)
        sf.write(output_file, data, samplerate, format='WAV')
        return True, output_file
    except Exception as e:
        logging.error(f"MAIN: convert_ogg_to_wav error: {e}")
        return False, e


def check_user(message):
    """
    Проверка наличия записи для данного пользователя
    Проверка ограничений разных пользователей (PROJECT_USERS)
    """

    user_id = message.from_user.id

    if user_id not in user_data:
        # Вдруг уже предел пользователей?
        limit_result, user_exists = is_limit_user(db_conn, user_id)
        # Да, предел
        if limit_result == True:
            bot.send_message(user_id, 'Странно, предел пользователей. Нельзя пользоваться ботом.')
            return False
        # Если не предел и ещё не существует в БД, то добавляем
        elif not user_exists:
            create_user(db_conn, user_id)

        user_data[user_id] = {}
        user_data[user_id]['user_id'] = user_id


def voice_obj_to_text(message: Message, voice_obj: File) -> tuple:
    """
    Надо преобразовать voice из телеграма в словарь ответов.
    Блоки STT проверяем только для платного.
    """
    user_id = message.from_user.id

    # для SpeechRecognition нужен WAV
    ogg_file_path = voice_obj.file_path
    voice_file = bot.download_file(ogg_file_path)

    with open(ogg_file_path, 'wb') as ogg_file:
        ogg_file.write(voice_file)

    wav_file_path = f"{ogg_file_path[0:-3]}wav"
    wav_res = convert_ogg_to_wav(ogg_file_path, wav_file_path)[0]
    add_file2remove(db_conn, user_data[user_id], ogg_file_path)
    logging.info(f"Временный файл {ogg_file_path} от пользователя {user_id} - в список на удаление")
    add_file2remove(db_conn, user_data[user_id], wav_file_path)
    logging.info(f"Временный файл {wav_file_path} от пользователя {user_id} - в список на удаление")

    stt_blocks = ceil(message.voice.duration / 15)
    logging.debug(f"MAIN: process_test_stt: {voice_obj.file_path} {stt_blocks}")

    result = {}

    # Бесплатный модуль SpeechRecognition.Google
    asr_start = time_ns()
    success, res = ask_speech_recognition(wav_file_path)
    logging.info(f"MAIN: ask_speech_recognition {success}, {res}")
    asr_time_ms = (time_ns() - asr_start) // 1000000

    # Проверяем успешность распознавания и выводим результат, сохраняем в БД
    result['SR.Google'] = {'content': res, 'asr_time_ms': asr_time_ms}
    if success:
        insert_stt(db_conn, user_id,
                   wav_file_path, content=res,
                   blocks=stt_blocks, model='SR.Google',
                   asr_time_ms=asr_time_ms)

    # Платный модуль SpeechKit. Перед ним нужно проверить лимиты
    limit_result, error_msg = is_limit_stt_blocks(db_conn, user_id, stt_blocks)
    # Уже превышен или будет превышен?
    if limit_result:
        logging.warning(f"MAIN: is_limit_stt_blocks {limit_result}, {error_msg}")
        result['Yandex SpeechKit'] = {'content': error_msg, 'asr_time_ms': 0}
        return True, result

    asr_start = time_ns()
    success, res = ask_speech_kit_stt(voice_file)
    logging.info(f"MAIN: ask_speech_kit_stt {success}, {res}")
    # success, res = True, "SpeechKit закомментировал, идёт тест модуля SR"
    asr_time_ms = (time_ns() - asr_start) // 1000000

    # Проверяем успешность распознавания и выводим результат, сохраняем в БД
    result['Yandex SpeechKit'] = {'content': res, 'asr_time_ms': asr_time_ms}
    if not success:
        stt_blocks = 0
    insert_stt(db_conn, user_id,
               ogg_file_path, content=res,
               blocks=stt_blocks, model='SpeechKit',
               asr_time_ms=asr_time_ms)

    return True, result


@bot.message_handler(commands=['start'])
def handle_start(message: Message):
    """
    Обработчик команды /start
    Подсказка самого быстрого начала
    """
    user_id = message.from_user.id
    check_user(message)

    # Исходное приветствие
    bot.send_message(
        user_id,
        '✌🏻 <b>Привет!</b>\n'
        'Давай проверим Speech-to-text: <b>/stt</b>\n\n'
        'Кстати,\n'
        '/stat - немного статистики\n'
        '/debug - немного отладочной информации',
        parse_mode='HTML',
        reply_markup=hideKeyboard)


@bot.message_handler(commands=['stt'])
def handle_stt(message: Message):
    """
    по ТЗ: пользователь отправляет аудио, а бот распознаёт текст.
    """
    user_id = message.from_user.id
    check_user(message)

    bot.send_message(
        user_id,
        f"<b>Проверка работы Speech-to-text</b>\n\n"
        f"Пришли голосовое сообщение 5-15 сек, получи в ответ текст.\n"
        f"(или нажми <i>Отказаться от проверки</i>)\n\n"
        f"Проверка использует лимиты на блоки (1 блок = 15 сек): /stat ",
        parse_mode='HTML',
        reply_markup=mu_test_stt)
    bot.register_next_step_handler(message, process_stt)


def process_stt(message: Message):
    """
    по ТЗ: пользователь отправляет аудио, а бот распознаёт текст.
    """
    user_id = message.from_user.id
    check_user(message)

    if message.text == T['t_stop_test']:
        bot.send_message(
            user_id,
            f"Ок, выходим из проверки Speech-to-text.\n"
            f"Можешь перейти в начало: /start",
            reply_markup=hideKeyboard)
        return

    if not message.voice:
        bot.send_message(
            user_id,
            f"Эта функция работает только с голосовыми сообщениями.\n"
            f"Попробуй ещё раз: /stt",
            reply_markup=hideKeyboard)
        return

    if message.voice.duration > 30:
        bot.send_message(
            user_id,
            f"Голосовое сообщение должно быть не длиннее 30 секунд.\n"
            f"Попробуй ещё раз: /stt",
            reply_markup=hideKeyboard)
        return

    bot.send_message(
        user_id,
        f"Передаю в обработку...\n\n"
        f"блоков: <b>{ceil(message.voice.duration / 15)}</b>\n"
        f"длина: <b>{message.voice.duration} сек</b>\n",
        parse_mode='HTML',
        reply_markup=hideKeyboard)

    # Для SpeechKit достаточно звуковых данных
    bot.send_chat_action(user_id, 'typing')
    voice_obj = bot.get_file(message.voice.file_id)
    success, res = voice_obj_to_text(message, voice_obj)

    if success:
        result_msg = ""
        for r in res.keys():
            result_msg += (
                f"Модуль <b>{r}</b> за {res[r]['asr_time_ms']} мс:\n"
                f"<i>{res[r]['content']}</i>\n\n")
    else:
        result_msg = f"<b>Ошибка!</b>\n\nНе получилось распознать\n\n"

    bot.send_message(
        user_id,
        f"{result_msg}Проверяй расход командой /stat",
        parse_mode='HTML',
        reply_markup=hideKeyboard)


def append_stat(stat: list, param_name: str, user: dict) -> list:
    """
    Формирует список для отображения статистики ИИ-ресурсов /stat
    Функция из финального проекта, в нём много разных ресурсов, а тут только три. Ну штош...
    """
    r1, r2 = is_limit(db_conn, param_name=param_name, user=user)

    stat.append(f"{LIM[param_name]['descr']}:")
    stat.append(f"<b>{int(100 * r2 / LIM[param_name]['value'])}</b>% "
                f"({r2} / {LIM[param_name]['value']})")

    return stat


@bot.message_handler(commands=['stat'])
def handle_stat(message: Message):
    """
    Статистика расходов ИИ-ресурсов и ограничений
    Функция из финального проекта, в нём много разных ресурсов, а тут только три. Ну штош...
    """
    user_id = message.from_user.id
    check_user(message)

    p_stat = []
    p_stat = append_stat(p_stat, 'PROJECT_USERS', user_data[user_id])
    p_stat = append_stat(p_stat, 'PROJECT_STT_BLOCKS', user_data[user_id])

    u_stat = []
    u_stat = append_stat(u_stat, 'USER_STT_BLOCKS', user_data[user_id])

    bot.send_message(
        user_id,
        f"<b>ОГРАНИЧЕНИЯ И РАСХОД ИИ-РЕСУРСОВ</b>\n(только для Yandex SpeechKit)\n\n"
        f"<b>Весь проект:</b>\n\n"
        f"{'\n'.join(p_stat)}\n\n"
        f"<b>Твой личный расход:</b>\n\n"
        f"{'\n'.join(u_stat)}",
        parse_mode='HTML',
        reply_markup=hideKeyboard)


@bot.message_handler(commands=['debug'])
def handle_debug(message: Message):
    """
    Часть ТЗ - СИКРЕТНЫЙ вывод отладочной информации
    """
    user_id = message.from_user.id
    check_user(message)
    logging.info(f"MAIN: пользователь {user_id} запросил лог-файл")

    try:
        with open(MAIN['log_filename'], "rb") as f:
            bot.send_document(user_id, f)
    except Exception:
        logging.error(f"MAIN: ошибка при отправке лог-файла пользователю {user_id}")
        bot.send_message(
            user_id,
            f"Аааа! Не могу найти лог-файл {MAIN['log_filename']}",
            reply_markup=hideKeyboard)


# *********************************************************************
# Запуск бота
try:
    bot.infinity_polling()
except urllib3.exceptions.ReadTimeoutError as e:
    logging.info(f"TB: Read timed out. (read timeout=25)")

logging.warning(f"TB: finish")

db_conn.close()
logging.warning(f"MAIN: DB close connection")

logging.warning(f"MAIN: finish")
