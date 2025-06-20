import os

from flask import Flask
from loguru import logger
from slack_sdk import WebClient

from vidya.celery_init import celery_init_app
from vidya.config import (
    DevelopmentConfig,
    ProductionConfig,
)
from vidya.core.camera import IPCamera
from vidya.log_init import (
    InterceptHandler,
    configure_log,
)
from vidya.routes.camera import bp_cam
from vidya.routes.helpers import (
    clear_trailing_slash,
    log_after,
    log_before,
)
from vidya.routes.main import bp_main

ROUTES = [
    bp_main,
    bp_cam
]


def create_app(*args, **kwargs) -> Flask:
    """Creates a Flask app instance"""
    # Config app
    config_class = kwargs.get('config_class')
    if config_class is None:
        if os.getenv('ENV', 'dev').lower() == 'prod':
            config_class = ProductionConfig
        else:
            config_class = DevelopmentConfig

    if not isinstance(config_class, (DevelopmentConfig, ProductionConfig)):
        logger.debug('Config wasn\'t yet instantiated - doing that.')
        config_class = config_class()

    app = Flask(__name__, static_url_path='/')
    app.config.from_object(config_class)
    # Reduce the amount of 404s by disabling strict slashes (e.g., when a forward slash is appended to a url)
    app.url_map.strict_slashes = False

    # Initialize logger
    configure_log(app=app)

    logger.info('Logger started. Binding to app handler...')
    app.logger.addHandler(InterceptHandler(logger=logger))

    # Register routes
    logger.info('Registering routes...')
    for ruut in ROUTES:
        app.register_blueprint(ruut)

    # Initialize Celery
    app.config.from_mapping(
        CELERY=dict(
            broker_url=os.environ['REDIS_URL'],
            broker_connection_retry_on_startup=True,
            result_backend=os.environ['REDIS_URL'],
            task_ignore_result=True,
            timezone='America/Chicago',
        )
    )
    app.config.from_prefixed_env()
    celery_init_app(app)

    client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])
    app.extensions.setdefault('slack', client)

    # Load cameras
    cams = {}
    for cid in os.environ['CAMS'].split(','):
        cid = int(cid)
        cams[cid] = IPCamera(int(cid))
    app.extensions.setdefault('cams', cams)

    app.before_request(log_before)
    app.before_request(clear_trailing_slash)

    app.after_request(log_after)

    return app
