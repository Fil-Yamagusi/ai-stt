#!/usr/bin/env python3.12
# -*- coding: utf-8 -*-
"""2024-04-30 Fil - Future code Yandex.Practicum
Yandex SpeechKit - Speech Recognition

DB functions
"""

# standard
from time import time_ns, time, strftime
import logging
import sqlite3
from os import remove

# third-party

# custom
# для авторизации и для ограничений
from config import MAIN, TB, YANDEX, LIM


def get_db_connection(db_file: str) -> sqlite3.Connection:
    """
    Получаем соединение с БД
    """
    try:
        db_conn = sqlite3.connect(db_file, check_same_thread=False)
    except Exception as e:
        logging.error(f"DB: get_db_connection: {e}")
        return False

    return db_conn


def create_db(db_conn):
    """
    Создаём все таблицы. ИИ-ресурсы учитываем раздельно
    """
    cursor = db_conn.cursor()

    # Пользователи
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS Users ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'user_id INTEGER NOT NULL'
        ')'
    )

    # Создаем таблицу к STT - SpeechKit распознавание речи
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS STT ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'user_id INTEGER NOT NULL, '
        'filename TEXT NOT NULL, '
        'datetime TEXT NOT NULL, '
        'content TEXT NOT NULL, '
        'blocks INT, '
        'model TEXT NOT NULL, '
        'asr_time_ms INTEGER'
        ')'
    )

    # Звуковые файлы для удаления
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS Files2Remove ('
        'id INTEGER PRIMARY KEY, '
        'user_id INTEGER NOT NULL, '
        'file_path TEXT NOT NULL, '
        'timens_added INTEGER NOT NULL'
        ')'
    )

    try:
        r = db_conn.commit()
    except Exception as e:
        logging.error(f"DB: get_db_connection: {e}")
        return False

    return r


def is_limit_user(db_conn, user_id: int) -> tuple:
    """
    Возвращает: Превышен ли лимит пользователей, существует ли уже такой
    """
    cursor = db_conn.cursor()
    # если пользователь уже добавлен, значит однажды он прошёл проверку
    query = 'SELECT id FROM Users WHERE user_id = ?;'
    data = (user_id,)

    try:
        cursor.execute(query, data)
        res = cursor.fetchone()
    except Exception as e:
        logging.error(f"DB: is_limit_user {e}")
        return True, False

    if res is None:
        # если пользователь не добавлен, то проверить лимит пользователей
        query = 'SELECT COUNT(DISTINCT user_id) >= ? FROM Users;'
        data = (LIM['PROJECT_USERS']['value'],)

        try:
            cursor.execute(query, data)
            res2 = cursor.fetchone()
        except Exception as e:
            logging.error(f"DB: is_limit_user {e}")
            return True, False

        if res2 is None:
            return False, False
        elif res2[0] == 1:
            return True, False
        else:
            return False, False

    else:
        return False, True


def is_limit_stt_blocks(db_conn, user_id: int, blocks: int) -> tuple:
    """
    Возвращает кортеж:
    (Будет ли превышен лимит с учётом запрошенного blocks, текст ошибки)
    """
    cursor = db_conn.cursor()
    # проверяем превышение общего количества STT-блоков
    query = "SELECT COUNT(blocks) > ? FROM STT WHERE model='SpeechKit'";
    data = (LIM['PROJECT_STT_BLOCKS']['value'] - blocks,)

    try:
        cursor.execute(query, data)
        res = cursor.fetchone()
    except Exception as e:
        logging.error(f"DB: is_limit_stt_blocks {e}")
        return True, f'PROJECT_STT_BLOCKS DB error {e}'

    if res is None:
        return True, f'PROJECT_STT_BLOCKS is None?!'
    elif res[0] == 0:
        # проверяем превышение количества blocks на пользователя
        query = "SELECT COUNT(blocks) > ? FROM STT WHERE model='SpeechKit' AND user_id = ?";
        data = (LIM['USER_STT_BLOCKS']['value'] - blocks, user_id)

        try:
            cursor.execute(query, data)
            res2 = cursor.fetchone()
        except Exception as e:
            logging.error(f"DB: is_limit_user {e}")
            return True, f'USER_STT_BLOCKS DB error {e}'

        if res2 is None:
            return True, f'USER_STT_BLOCKS is None?!'
        elif res2[0] == 0:
            return False, f'Чётко, пацаны ваще ребята'
        else:
            return True, f'Превышен USER_STT_BLOCKS'

    else:
        return True, f'Превышен PROJECT_STT_BLOCKS'


def create_user(db_conn, user_id: int):
    """
    Добавляем пользователя в БД. Проверка снаружи
    """
    cursor = db_conn.cursor()
    query = 'INSERT INTO Users (user_id) VALUES (?);'
    cursor.execute(query, (user_id,))
    db_conn.commit()


def add_file2remove(db_conn, user, file_path):
    """
    Добавить файл в очередь на удаление, удалить старые
    Используется в /profile
    """

    cursor = db_conn.cursor()
    query = ('INSERT INTO Files2Remove '
             '(user_id, file_path, timens_added) '
             'VALUES (?, ?, ?);')
    cursor.execute(query, (user['user_id'], file_path, time_ns()))

    old = time_ns() - 10 ** 11  # старше 100 секунд
    query = (f"SELECT id, file_path FROM Files2Remove WHERE "
             f"timens_added <= {old}")
    cursor.execute(query)
    res = cursor.fetchall()
    if res is not None:
        for r in res:
            try:
                remove(r[1])
                cursor.execute(f"DELETE FROM Files2Remove WHERE id={r[0]};")
            except Exception as e:
                logging.error(f"Error while deleting {r[0]} {r[1]}")

    # Принудительно удаляем всё старше 10000 секунд
    old = time_ns() - 10 ** 13
    cursor.execute(f"DELETE FROM Files2Remove WHERE timens_added <= {old};")

    db_conn.commit()


def insert_stt(db_conn,
               user_id: int, filename: str, content: str,
               blocks: int, model: str, asr_time_ms: int):
    """
    Функция для добавления в БД нового запроса STT
    """
    cursor = db_conn.cursor()

    data = (
        user_id,
        filename,
        strftime('%F %T'),
        content,
        blocks,
        model,
        asr_time_ms,
    )
    try:
        cursor.execute('INSERT INTO STT '
                       '(user_id, filename, datetime, content, '
                       'blocks, model, asr_time_ms) '
                       'VALUES (?, ?, ?, ?, ?, ?, ?);',
                       data)
        db_conn.commit()
        logging.debug(f"DB: insert_stt: added id={cursor.lastrowid}")
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        logging.warning(f"DB: insert_tts: not added")
        return False


def is_limit(db_conn, **kwargs):
    """
    Возвращает кортеж: (Превышен ли лимит, текущее значение)
    Пробуем все проверки в одной функции сделать
    user - про кого спрашиваем, но иногда это не надо
    """
    # Для некоторых проверок нужны параметры, достаём их из kwargs
    param_name = kwargs.get('param_name', None)

    user = kwargs.get('user', None)
    if isinstance(user, dict):
        user_id = user['user_id']

    session_id = kwargs.get('session_id', None)

    param = LIM[param_name]

    cursor = db_conn.cursor()
    # Чаще всего передаём в запрос user_id
    data = tuple()

    # LIM['PROJECT_USERS'] = {
    #     'descr': 'max пользователей на весь проект',
    #     'value': 4, }
    if param_name == 'PROJECT_USERS':
        query = 'SELECT COUNT(DISTINCT user_id) FROM Users;'

    # LIM['PROJECT_STT_BLOCKS'] = {
    #     'descr': 'max блоков (STT) на весь проект',
    #     'value': 100, }
    if param_name == 'PROJECT_STT_BLOCKS':
        query = "SELECT SUM(blocks) FROM STT WHERE model='SpeechKit';"
    #
    # LIM['USER_STT_BLOCKS'] = {
    #     'descr': 'max блоков (STT) на пользователя',
    #     'value': 12, }
    if param_name == 'USER_STT_BLOCKS':
        query = ("SELECT SUM(blocks) FROM STT WHERE user_id = ? AND model='SpeechKit';")
        data = (user_id,)

    try:
        cursor.execute(query, data)
        res = cursor.fetchone()
    except Exception as e:
        logging.error(f"DB: is_limit {param_name} {e}")

    if res is None:
        r, rr = False, 0
    elif res[0] is None:
        r, rr = False, 0
    else:
        r, rr = (res[0] >= param['value']), res[0]
    logging.debug(f"DB: {param_name} is_limit = {r}: "
                  f"{rr} / {param['value']} ({param['descr']})")

    return r, rr
