# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
from sys import exit

from decouple import config  # type: ignore
from flask_migrate import Migrate

from otterdog.webapp import create_app, celery_init_app, db
from otterdog.webapp.config import config_dict

# WARNING: Don't run with debug turned on in production!
DEBUG: bool = config('DEBUG', default=True, cast=bool)

# Determine which configuration to use
config_mode = 'Debug' if DEBUG else 'Production'

try:
    app_config = config_dict[config_mode]
except KeyError:
    exit('Error: Invalid <config_mode>. Expected values [Debug, Production] ')

app = create_app(app_config)
celery = celery_init_app(app)

Migrate(app, db)

if DEBUG:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    app.logger.info('DEBUG         = ' + str(DEBUG))
    app.logger.info('Environment   = ' + config_mode)
    app.logger.info('FLASK_APP     = ' + app_config.FLASK_APP)
    app.logger.info('DBMS          = ' + app_config.SQLALCHEMY_DATABASE_URI)
    app.logger.info('ASSETS_ROOT   = ' + app_config.ASSETS_ROOT)
    app.logger.info('CELERY_BROKER = ' + app_config.CELERY_BROKER)


def run():
    app.run(use_reloader=False)


if __name__ == "__main__":
    run()
