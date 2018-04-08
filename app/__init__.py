from flask import Flask, request, Response
from flask_sqlalchemy import SQLAlchemy
from config import config

import logging
from logging.handlers import RotatingFileHandler

db = SQLAlchemy()

from .sync import Syncer
syncer = Syncer()

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    db.init_app(app)
    syncer.init_app(app)

    formatter = logging.Formatter(app.config['LOG_FORMAT'])
    handler = RotatingFileHandler(app.config['LOG_FILENAME'],
        maxBytes=10000000, backupCount=5)
    app.logger.addHandler(handler)
    for h in app.logger.handlers:
        h.setLevel(app.config['LOG_LEVEL'])
        h.setFormatter(formatter)

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint)

    from .reports import reports as reports_blueprint
    app.register_blueprint(reports_blueprint)

    def get_handler(code):
        path = request.path
        for bp_name, bp in app.blueprints.items():
            if bp.url_prefix and path.startswith(bp.url_prefix):
                handler = app.error_handler_spec.get(bp_name, {}).get(code)
                if handler: return tuple(handler.values())[0]

    @app.errorhandler(400)
    def not_found(error):
        handler = get_handler(400)
        return handler(error) if handler else Response('bad request', 400)

    @app.errorhandler(403)
    def not_found(error):
        handler = get_handler(403)
        return handler(error) if handler else Response('forbidden', 404)

    @app.errorhandler(404)
    def not_found(error):
        handler = get_handler(404)
        return handler(error) if handler else Response('not found', 404)

    app.logger.debug('initialization finished')
    return app
