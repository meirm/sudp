#!/usr/bin/env python3
"""Logging infrastructure for SUDP.

This module provides a centralized logging system with:
- Configurable log levels
- Log rotation
- Performance metrics
- Structured logging format
- Error tracking with context
"""

import asyncio
import logging
import logging.handlers
import os
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

# Default log directory is in the user's home directory
DEFAULT_LOG_DIR = Path.home() / ".sudp" / "logs"
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
PERFORMANCE_LOG_FORMAT = '%(asctime)s - PERFORMANCE - %(message)s'

class PerformanceMetrics:
    """Track performance metrics for operations."""
    
    def __init__(self) -> None:
        self.start_time: float = time.time()
        self.metrics: Dict[str, float] = {}
        self.logger = logging.getLogger('sudp.performance')
    
    def record(self, metric_name: str, value: float) -> None:
        """Record a performance metric."""
        self.metrics[metric_name] = value
        self.logger.debug(f"Metric {metric_name}: {value:.3f}")
    
    def measure_time(self) -> float:
        """Measure elapsed time since initialization."""
        duration = time.time() - self.start_time
        self.record('duration', duration)
        return duration

def setup_logging(
    log_dir: Union[str, Path] = DEFAULT_LOG_DIR,
    log_level: int = DEFAULT_LOG_LEVEL,
    rotation_when: str = 'midnight',
    backup_count: int = 7
) -> logging.Logger:
    """Set up the logging infrastructure.
    
    Args:
        log_dir: Directory to store log files
        log_level: Logging level (default: INFO)
        rotation_when: When to rotate logs ('midnight', 'h', 'w0', etc.)
        backup_count: Number of backup files to keep
    
    Returns:
        Logger: Configured logger instance
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Main application logger
    logger = logging.getLogger('sudp')
    logger.setLevel(log_level)
    logger.propagate = False  # Prevent double logging
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Console handler with colored output
    console_handler = logging.StreamHandler()
    console_format = '\033[1;36m%(asctime)s\033[0m - \033[1;32m%(name)s\033[0m - \033[1;34m%(levelname)s\033[0m - %(message)s'
    console_handler.setFormatter(logging.Formatter(console_format))
    console_handler.setLevel(logging.DEBUG)  # Show all logs in console
    logger.addHandler(console_handler)
    
    # File handler with rotation
    main_log = log_dir / 'sudp.log'
    file_handler = logging.handlers.TimedRotatingFileHandler(
        main_log,
        when=rotation_when,
        backupCount=backup_count
    )
    file_handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
    file_handler.setLevel(log_level)
    logger.addHandler(file_handler)
    
    # Performance logger setup
    perf_logger = logging.getLogger('sudp.performance')
    perf_logger.setLevel(logging.DEBUG)
    perf_logger.propagate = False  # Prevent double logging
    perf_logger.handlers.clear()
    
    # Performance console handler
    perf_console = logging.StreamHandler()
    perf_console.setFormatter(logging.Formatter('\033[1;35mPERF\033[0m - %(message)s'))
    perf_console.setLevel(logging.DEBUG)
    perf_logger.addHandler(perf_console)
    
    # Performance file handler
    perf_log = log_dir / 'performance.log'
    perf_file = logging.handlers.TimedRotatingFileHandler(
        perf_log,
        when=rotation_when,
        backupCount=backup_count
    )
    perf_file.setFormatter(logging.Formatter(PERFORMANCE_LOG_FORMAT))
    perf_file.setLevel(logging.DEBUG)
    perf_logger.addHandler(perf_file)
    
    return logger

def log_performance(operation: str) -> Callable:
    """Decorator to log performance metrics for an operation.
    
    Args:
        operation: Name of the operation being measured
    
    Returns:
        Callable: Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            metrics = PerformanceMetrics()
            try:
                metrics.record('operation_start', time.time())
                result = await func(*args, **kwargs)
                duration = metrics.measure_time()
                metrics.logger.info(
                    f"{operation} completed in {duration:.3f}s"
                )
                return result
            except Exception as e:
                duration = metrics.measure_time()
                metrics.logger.error(
                    f"{operation} failed after {duration:.3f}s: {str(e)}"
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            metrics = PerformanceMetrics()
            try:
                metrics.record('operation_start', time.time())
                result = func(*args, **kwargs)
                duration = metrics.measure_time()
                metrics.logger.info(
                    f"{operation} completed in {duration:.3f}s"
                )
                return result
            except Exception as e:
                duration = metrics.measure_time()
                metrics.logger.error(
                    f"{operation} failed after {duration:.3f}s: {str(e)}"
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def log_error(
    logger: logging.Logger,
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """Log an error with additional context information.
    
    Args:
        logger: Logger instance to use
        error: Exception to log
        context: Additional context information
    """
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'timestamp': datetime.utcnow().isoformat(),
        'context': context or {}
    }
    
    logger.error(
        f"Error occurred: {error_info['error_type']}: {error_info['error_message']}",
        extra={'error_info': error_info}
    ) 