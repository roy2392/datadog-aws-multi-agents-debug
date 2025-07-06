"""
Logging utilities for the Datadog Multi-Agent Debugging project.
Provides safe printing and logging functionality.
"""

import logging
from config import LoggingConfig

def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, LoggingConfig.LEVEL),
        format=LoggingConfig.FORMAT
    )

def safe_print(text):
    """Print text safely, avoiding encoding issues."""
    try:
        print(text)
    except (UnicodeEncodeError, ValueError):
        try:
            print(text.encode('ascii', 'ignore').decode('ascii'))
        except:
            print("Processing item...")

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(name) 