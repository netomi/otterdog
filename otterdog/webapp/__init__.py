# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from importlib import import_module
from importlib.util import find_spec
import logging

from flask.app import Flask
from flask_login import LoginManager  # type: ignore
from flask_sqlalchemy import SQLAlchemy

from celery import Celery, Task  # type: ignore

from otterdog.providers.github import RestApi
from otterdog.providers.github.rest.auth.app import AppAuthStrategy

_MODULES = ["authentication", "home", "webhook"]

db = SQLAlchemy()
login_manager = LoginManager()


def register_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)


def register_blueprints(app):
    for module_name in _MODULES:
        routes_fqn = f"otterdog.webapp.{module_name}.routes"
        spec = find_spec(routes_fqn)
        if spec is not None:
            module = import_module(routes_fqn)
            app.register_blueprint(module.blueprint)


def configure_database(app):
    with app.app_context():
        for module_name in _MODULES:
            models_fqn = f"otterdog.webapp.{module_name}.models"
            spec = find_spec(models_fqn)
            if spec is not None:
                _ = import_module(models_fqn)

        db.create_all()

    @app.teardown_request
    def shutdown_session(exception=None):
        db.session.remove()


def get_or_create(session, model, defaults=None, **kwargs):
    instance = session.query(model).filter_by(**kwargs).one_or_none()
    if instance:
        return instance, False
    else:
        kwargs |= defaults or {}
        instance = model(**kwargs)
        try:
            session.add(instance)
            session.commit()
        except Exception:
            # The actual exception depends on the specific database, so we catch all exceptions.
            # This is similar to the official documentation:
            # https://docs.sqlalchemy.org/en/latest/orm/session_transaction.html
            session.rollback()
            instance = session.query(model).filter_by(**kwargs).one()
            return instance, False
        else:
            return instance, True


def fill_database(app):
    from .home.models import Organizations

    with app.app_context():
        logging.debug("filling database with app installations")
        rest_api = RestApi(AppAuthStrategy(app.config["GITHUB_APP_ID"], app.config["GITHUB_APP_PRIVATE_KEY"]))
        for app_installation in rest_api.app.get_app_installations():
            dbid = app_installation["id"]
            github_id = app_installation["account"]["login"]
            get_or_create(db.session, Organizations, id=dbid, github_id=github_id)

        rest_api.close()


def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask, broker_connection_retry_on_startup=True)

    CELERY = dict(
        broker_url=app.config["CELERY_BROKER"],
        result_backend=app.config["CELERY_BACKEND"],
        task_ignore_result=True,
    )

    celery_app.config_from_object(CELERY)
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app


def create_app(config):
    app = Flask(config.FLASK_APP)
    app.config.from_object(config)
    register_extensions(app)

    if app.config["SOCIAL_AUTH_GITHUB"] is True:
        from .authentication.oauth import github_blueprint

        app.register_blueprint(github_blueprint, url_prefix="/login")

    register_blueprints(app)
    configure_database(app)

    fill_database(app)

    return app
