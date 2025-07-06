"""
Configuration module for Datadog Multi-Agent Debugging project.
Centralizes all environment variables and application settings.
"""

import os
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()

# CRITICAL: Set environment variables BEFORE importing ddtrace to disable APM
os.environ["DD_TRACE_ENABLED"] = "false"
os.environ["DD_AGENT_HOST"] = ""
os.environ["DD_TRACE_AGENT_URL"] = ""

class BedrockConfig:
    """Bedrock service configuration."""
    REGION = os.environ.get("BEDROCK_REGION", "eu-west-1")
    AGENT_ID = os.environ.get("AGENT_ID", "")
    AGENT_ALIAS_ID = os.environ.get("AGENT_ALIAS_ID", "")

class DatadogConfig:
    """Datadog configuration."""
    API_KEY = os.environ.get("DATADOG_API_KEY", "")
    SITE = os.environ.get("DATADOG_SITE", "datadoghq.eu")
    ML_APP_NAME = os.environ.get("ML_APP_NAME", "migdal-zone")

class LoggingConfig:
    """Logging configuration."""
    LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

class AppConfig:
    """Application-wide configuration."""
    SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "30"))
    MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
    CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "100")) 