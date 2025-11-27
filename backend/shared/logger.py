"""
Structured logging with daily file rotation
Generates log files organized by date: logs/app.YYYY-MM-DD.log
Each day gets its own log file for easy debugging
"""

import logging
import os
import json
from datetime import datetime
from pathlib import Path
import threading


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


class DailyRotatingFileHandler(logging.Handler):
    """
    Custom file handler that creates a new log file each day
    Files are named: app.YYYY-MM-DD.log (e.g., app.2025-11-27.log)
    """
    
    def __init__(self, log_dir: Path, base_name: str = 'app', level: int = logging.INFO):
        super().__init__(level)
        self.log_dir = log_dir
        self.base_name = base_name
        self.current_date = None
        self.current_file = None
        self.lock = threading.Lock()
        self._open_file()
    
    def _get_log_filename(self, date: datetime = None) -> Path:
        """Get log filename for a specific date"""
        if date is None:
            date = datetime.now()
        date_str = date.strftime('%Y-%m-%d')
        return self.log_dir / f'{self.base_name}.{date_str}.log'
    
    def _open_file(self):
        """Open log file for current date"""
        try:
            today = datetime.now()
            today_str = today.strftime('%Y-%m-%d')
            
            if self.current_date != today_str:
                if self.current_file:
                    try:
                        self.current_file.close()
                    except Exception:
                        pass
                
                log_file = self._get_log_filename(today)
                # Ensure directory exists
                log_file.parent.mkdir(parents=True, exist_ok=True)
                self.current_file = open(log_file, 'a', encoding='utf-8')
                self.current_date = today_str
        except Exception as e:
            # Fallback to stderr if file opening fails
            import sys
            print(f"Logger file open error: {e}", file=sys.stderr)
            if not self.current_file:
                self.current_file = sys.stderr
    
    def emit(self, record):
        """Emit a log record"""
        try:
            # Use timeout to prevent deadlock
            if self.lock.acquire(timeout=0.1):
                try:
                    # Check if date changed (new day)
                    today = datetime.now()
                    today_str = today.strftime('%Y-%m-%d')
                    
                    if self.current_date != today_str or not self.current_file:
                        self._open_file()
                    
                    # Format and write log
                    if self.current_file:
                        msg = self.format(record)
                        self.current_file.write(msg + '\n')
                        self.current_file.flush()
                finally:
                    self.lock.release()
            else:
                # If lock acquisition fails, skip this log (prevent deadlock)
                pass
        except Exception:
            self.handleError(record)
    
    def close(self):
        """Close the log file"""
        if self.current_file:
            self.current_file.close()
        super().close()


class DailyRotatingLogger:
    """
    Logger class with daily file rotation
    Creates log files organized by date: logs/app.YYYY-MM-DD.log
    Each day gets its own log file (e.g., app.2025-11-27.log)
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
        
        # File handler with daily rotation (creates app.YYYY-MM-DD.log files)
        file_handler = DailyRotatingFileHandler(
            log_dir=self.log_dir,
            base_name='app',
            level=self.level
        )
        file_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(file_handler)
        
        # Error file handler (separate file for errors only, creates errors.YYYY-MM-DD.log)
        error_handler = DailyRotatingFileHandler(
            log_dir=self.log_dir,
            base_name='errors',
            level=logging.ERROR
        )
        error_handler.setFormatter(JSONFormatter())
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
