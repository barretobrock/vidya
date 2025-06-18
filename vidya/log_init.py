import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger

    def emit(self, record):
        # Get corresponding loguru level if it exists
        try:
            level = self.logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find call whence the logged message originated
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        self.logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def handle_exception(exc_type, exc_value, exc_traceback):
    """This is used to patch over sys.excepthook so uncaught logs are also recorded"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    # We'll log uncaught errors as critical to differentiate them from caught `error` level entries
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical('Uncaught exception:')


def configure_log(app):
    BASE_FORMAT = '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | ' \
                  '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>'
    sys.excepthook = handle_exception
    handlers = [
        {
            'sink': sys.stdout,
            'level': app.config.get('LOG_LEVEL'),
            'format': BASE_FORMAT,
            'backtrace': app.config.get('DEBUG')
        }
    ]

    if app.config.get('LOG_DIR') is not None:
        # Add a filepath to the handlers list
        # First, ensure all the directories are made
        app.config.get('LOG_DIR').mkdir(parents=True, exist_ok=True)
        handlers.append({
            'sink': app.config.get('LOG_DIR').joinpath('{}.log'.format(app.config.get('SERVICE_NAME'))),
            'level': app.config.get('LOG_LEVEL'),
            'rotation': '7 days',
            'retention': '30 days',
            'format': BASE_FORMAT,
            'enqueue': True,
            'backtrace': app.config.get('DEBUG')
        })
    config = {
        'handlers': handlers,
    }
    logger.configure(**config)
