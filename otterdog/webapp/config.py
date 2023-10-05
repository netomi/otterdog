# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
from decouple import config  # type: ignore


class Config(object):
    FLASK_APP = "otterdog.webapp"

    # Assets Management
    ASSETS_ROOT = "/static/assets"

    # Set up the App SECRET_KEY
    SECRET_KEY = config("SECRET_KEY")

    APP_ROOT = config("APP_ROOT")

    if not os.path.exists(APP_ROOT):
        os.makedirs(APP_ROOT)

    # This will create a sqlite db in <app-root> FOLDER
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(APP_ROOT, 'db.sqlite3')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # GitHub App config
    GITHUB_APP_ID = config('GITHUB_APP_ID')
    GITHUB_APP_PRIVATE_KEY = config('GITHUB_APP_PRIVATE_KEY')

    # OAUTH config
    SOCIAL_AUTH_GITHUB = False

    GITHUB_OAUTH_CLIENT_ID = config('GITHUB_OAUTH_CLIENT_ID')
    GITHUB_OAUTH_CLIENT_SECRET = config('GITHUB_OAUTH_CLIENT_SECRET')

    # Enable/Disable GitHub Social Login
    if GITHUB_OAUTH_CLIENT_ID and GITHUB_OAUTH_CLIENT_SECRET:
        SOCIAL_AUTH_GITHUB = True

    # Celery config
    CELERY_BROKER = config('CELERY_BROKER')
    CELERY_BACKEND = config('CELERY_BACKEND')


class ProductionConfig(Config):
    DEBUG = False

    # Security
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600

    # PostgreSQL database
    SQLALCHEMY_DATABASE_URI = '{}://{}:{}@{}:{}/{}'.format(
        config('DB_ENGINE', default='postgresql'),
        config('DB_USERNAME', default='otterdog'),
        config('DB_PASS', default='pass'),
        config('DB_HOST', default='localhost'),
        config('DB_PORT', default=5432),
        config('DB_NAME', default='otterdog-flask'),
    )


class DebugConfig(Config):
    DEBUG = True

    # SQLALCHEMY_ECHO = True


# Load all possible configurations
config_dict = {'Production': ProductionConfig, 'Debug': DebugConfig}
