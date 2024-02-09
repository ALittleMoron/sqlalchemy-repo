import logging
import logging.config

LOGGER_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "main_formatter": {
            "format": (
                "%(asctime)s - %(name)s - %(levelname)s - %(message).400s "
                "- %(filename)s - %(lineno)s - %(funcName)s"
            ),
            "datefmt": "%d.%m.%Y %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "formatter": "main_formatter",
        },
    },
    "loggers": {
        "sqlrepo": {"handlers": ["console"], "level": "DEBUG"},
    },
}


logging.config.dictConfig(LOGGER_CONFIG)
logger = logging.getLogger('sqlrepo')
