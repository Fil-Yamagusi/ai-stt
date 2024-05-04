# top-secret passwords
from auth import _TB, _YANDEX

#
# Настройки самой программы
MAIN = {}
MAIN['test_mode'] = False
MAIN['log_filename'] = 'stt_log.txt'
MAIN['db_filename'] = 'stt_sqlite.db'

# **********************************************************
# Ну вы поняли, какие переменные надо задать в файле auth.py
# Telegram bot
TB = {}
TB['TOKEN'] = _TB['TOKEN']
TB['BOT_NAME'] = _TB['BOT_NAME']
TB['BOT_USERNAME'] = _TB['BOT_USERNAME']

# Yandex API
YANDEX = {}
YANDEX['GPT_MODEL'] = _YANDEX['GPT_MODEL']  # 'yandexgpt-lite'
YANDEX['FOLDER_ID'] = _YANDEX['FOLDER_ID']
YANDEX['IAM_TOKEN'] = _YANDEX['IAM_TOKEN']
# **********************************************************

#
# А вот тут уже несекретные настройки - ограничения по ИИ-ресурсам
LIM = {}
# Ограничения на проект
# Каждый пользователь использует все типы ресурсов
LIM['PROJECT_USERS'] = {
    'descr': 'max пользователей на весь проект',
    'value': 4, }
LIM['PROJECT_STT_BLOCKS'] = {
    'descr': 'max блоков (STT) на весь проект',
    'value': 50, }
LIM['USER_STT_BLOCKS'] = {
    'descr': 'max блоков (STT) на пользователя',
    'value': 12, }
