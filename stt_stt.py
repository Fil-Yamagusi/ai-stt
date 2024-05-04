#!/usr/bin/env python3.12
# -*- coding: utf-8 -*-
"""2024-04-30 Fil - Future code Yandex.Practicum
Yandex SpeechKit - Speech Recognition

STT functions. Yandex SpeechKit by default
"""
__version__ = '0.1'
__author__ = 'Firip Yamagusi'

# standard
from requests import post

# third-party
import logging
import speech_recognition as sr

# custom
# для авторизации и для ограничений
from config import MAIN, TB, YANDEX, LIM


def ask_speech_recognition(wav_file: str) -> tuple:
    """
    Функция для распознавания аудио формата ".wav" в текст
    """

    with sr.AudioFile(wav_file) as source:
        r = sr.Recognizer()
        r.adjust_for_ambient_noise(source, duration=0.5)
        audio = r.record(source, duration=29)

        try:
            return True, r.recognize_google(audio, language='ru_RU')
        except sr.UnknownValueError as e:
            return False, "Speech Recognition could not understand audio: {e}"
        except sr.RequestError as e:
            return False, "SpeechRecognition service is unavailable: {e}"


def ask_speech_kit_stt(data):
    """
    Запросы к SpeechKit РАСПОЗНАВАНИЕ
    Проверку на лимиты делаем в том месте, где вызывается функция
    """

    params = "&".join([
        "topic=general",
        f"folderId={YANDEX['FOLDER_ID']}",
        "lang=ru-RU",
    ])

    url = f"https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?{params}"
    headers = {'Authorization': f"Bearer {YANDEX['IAM_TOKEN']}"}

    try:
        response = post(url, headers=headers, data=data)
        decoded_data = response.json()
        if decoded_data.get('error_code') is None:
            logging.debug(decoded_data.get('result'))
            return True, decoded_data.get('result')
        else:
            logging.warning(f"Error SpeechKit {decoded_data.get('error_code')}")
            return False, f"Error SpeechKit {decoded_data.get('error_code')}"

    except Exception as e:
        logging.warning(f"Error SpeechKit: post {e}")
        return False, f"Error SpeechKit: post {e}"
