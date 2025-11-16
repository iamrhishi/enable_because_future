"""
Structured logging with daily file rotation
Generates log files organized by date for efficient debugging
"""

import logging
import os
import json
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra') and record.extra:
            log_data.update(record.extra)
        
        return json.dumps(log_data)


class DailyRotatingLogger:
    """
    Logger class with daily file rotation
    Creates log files organized by date: logs/app_YYYY-MM-DD.log
    """
    
    def __init__(self, name: str = 'becauseFuture', log_dir: str = 'logs', level: str = None):
        """
        Initialize logger with daily rotation
        
        Args:
            name: Logger name
            log_dir: Directory to store log files
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Get log level from environment or default to INFO
        log_level = level or os.environ.get('LOG_LEVEL', 'INFO')
        self.level = getattr(logging, log_level.upper(), logging.INFO)
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.level)
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up console and file handlers"""
        
        # Console handler (always active)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.level)
        console_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(console_handler)
        
        # File handler with daily rotation
        log_file = self.log_dir / 'app.log'
        file_handler = TimedRotatingFileHandler(
            filename=str(log_file),
            when='midnight',  # Rotate at midnight
            interval=1,       # Every day
            backupCount=30,   # Keep 30 days of logs
            encoding='utf-8',
            utc=False  # Use local time
        )
        file_handler.setLevel(self.level)
        file_handler.setFormatter(JSONFormatter())
        file_handler.suffix = '%Y-%m-%d'  # Log file suffix format
        self.logger.addHandler(file_handler)
        
        # Error file handler (separate file for errors only)
        error_log_file = self.log_dir / 'errors.log'
        error_handler = TimedRotatingFileHandler(
            filename=str(error_log_file),
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8',
            utc=False
        )
        error_handler.setLevel(logging.ERROR)  # Only ERROR and above
        error_handler.setFormatter(JSONFormatter())
        error_handler.suffix = '%Y-%m-%d'
        self.logger.addHandler(error_handler)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        if kwargs:
            self.logger.debug(message, extra=kwargs)
        else:
            self.logger.debug(message)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        if kwargs:
            self.logger.info(message, extra=kwargs)
        else:
            self.logger.info(message)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        if kwargs:
            self.logger.warning(message, extra=kwargs)
        else:
            self.logger.warning(message)
    
    def error(self, message: str, exc_info=False, **kwargs):
        """Log error message"""
        if kwargs:
            self.logger.error(message, exc_info=exc_info, extra=kwargs)
        else:
            self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message: str, exc_info=False, **kwargs):
        """Log critical message"""
        if kwargs:
            self.logger.critical(message, exc_info=exc_info, extra=kwargs)
        else:
            self.logger.critical(message, exc_info=exc_info)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        if kwargs:
            self.logger.exception(message, extra=kwargs)
        else:
            self.logger.exception(message)


def setup_logger(name: str = 'becauseFuture', level: str = None) -> logging.Logger:
    """
    Set up structured logger (backward compatibility)
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger instance
    """
    logger_instance = DailyRotatingLogger(name=name, level=level)
    return logger_instance.logger


# Global logger instance using DailyRotatingLogger
_logger_instance = DailyRotatingLogger()
logger = _logger_instance.logger

# Convenience functions for backward compatibility (use logger directly)
# Example: logger.info("message") or logger.error("message", exc_info=True)
