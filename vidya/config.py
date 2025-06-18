"""Configuration setup"""
import os

from dotenv import load_dotenv
from loguru import logger

from vidya import (
    ROOT,
    __version__,
)


class BaseConfig(object):
    """Configuration items common across all config types"""
    ENV = 'DEV'
    DEBUG = False
    TESTING = False

    LOG_DIR = ROOT.joinpath('logs')
    SERVICE_NAME = 'vidya'

    VERSION = __version__
    PORT = 5007
    # Stuff for frontend
    STATIC_DIR_PATH = '../static'
    TEMPLATE_DIR_PATH = '../templates'

    def __init__(self):
        load_dotenv(dotenv_path=ROOT.joinpath('.env'))
        if not os.environ.get('VIDYA_WEBAPP_SECRET'):
            raise ValueError('VIDYA_WEBAPP_SECRET not detected.')
        else:
            logger.debug('Obtaining existing secret key.')
            self.SECRET_KEY = os.environ.get('VIDYA_WEBAPP_SECRET')


class DevelopmentConfig(BaseConfig):
    """Configuration for development environment"""
    ENV = 'DEV'
    DEBUG = True
    DB_SERVER = '0.0.0.0'
    LOG_LEVEL = 'DEBUG'

    def __init__(self):
        logger.info(f'Starting Webapp Config. Env: {self.ENV} Version: {self.VERSION} '
                    f'Debug: {self.DEBUG} Testing: {self.TESTING} Log level: {self.LOG_LEVEL}...')
        super().__init__()


class ProductionConfig(BaseConfig):
    """Configuration for production environment"""
    ENV = 'PROD'
    DEBUG = False
    DB_SERVER = '0.0.0.0'
    LOG_LEVEL = 'DEBUG'

    def __init__(self):
        logger.info(f'Starting Webapp Config. Env: {self.ENV} Version: {self.VERSION} '
                    f'Debug: {self.DEBUG} Testing: {self.TESTING} Log level: {self.LOG_LEVEL}...')
        super().__init__()
