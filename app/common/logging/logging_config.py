import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict
import os


log_level = os.environ.get('LOG_LEVEL', 'DEBUG').upper()

class StructuredLogger:
    """Structured logger for JSON-formatted logs"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)

        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JSONFormatter())
            self.logger.addHandler(handler)

        self.logger.propagate = False

    def info(self, message: str, **kwargs):
        """Log info level message with structured data"""
        self.logger.info(message, extra={'data': kwargs})

    def error(self, message: str, exc_info: bool = True, **kwargs):
        """Log error level message with structured data and exception info"""
        self.logger.error(message, extra={'data': kwargs}, exc_info=exc_info)

    def warning(self, message: str, **kwargs):
        """Log warning level message with structured data"""
        self.logger.warning(message, extra={'data': kwargs})

    def debug(self, message: str, **kwargs):
        """Log debug level message with structured data"""
        self.logger.debug(message, extra={'data': kwargs})


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for easy parsing in production"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'severity': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        if hasattr(record, 'data'):
            log_data.update(record.data)

        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            log_data['exception_type'] = record.exc_info[0].__name__ if record.exc_info[0] else None

        return json.dumps(log_data)


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Name of the logger (typically module name or service name)

    Returns:
        StructuredLogger instance

    Example:
        logger = get_logger('iterable.services')
        logger.info('Processing request', user_id=123, action='fetch')
    """
    return StructuredLogger(name)
