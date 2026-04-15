import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'autoservice_db')
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')

    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PERMANENT_SESSION_LIFETIME = 3600

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = 'static/uploads'

    ROLES = {
        'admin': 'Администратор',
        'master': 'Мастер-приёмщик',
        'mechanic': 'Механик',
        'manager': 'Руководитель',
        'storekeeper': 'Кладовщик'
    }

    ORDER_STATUSES = {
        'принят': 'Принят',
        'в работе': 'В работе',
        'ожидает запчастей': 'Ожидает запчастей',
        'завершен': 'Завершен',
        'отменен': 'Отменен',
        # Английские версии для совместимости
        'new': 'Принят',
        'in_progress': 'В работе',
        'waiting_parts': 'Ожидает запчастей',
        'completed': 'Завершен',
        'cancelled': 'Отменен'
    }

    WORK_STATUSES = {
        'назначена': 'Назначена',
        'в работе': 'В работе',
        'завершена': 'Завершена'
    }