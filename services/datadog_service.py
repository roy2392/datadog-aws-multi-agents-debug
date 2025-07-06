"""
Datadog service module for LLM Observability setup and configuration.
Handles Datadog integration and observability setup.
"""

from ddtrace.llmobs import LLMObs
from config import DatadogConfig
from utils.logger import get_logger

logger = get_logger(__name__)

class DatadogService:
    """Service class for Datadog LLM Observability operations."""
    
    def __init__(self):
        """Initialize Datadog service."""
        self._setup_llm_observability()
    
    def _setup_llm_observability(self):
        """Setup LLM Observability with Datadog."""
        try:
            print("Enabling Datadog LLM Observability for Complete Agent Separation...")
            LLMObs.enable(
                ml_app=DatadogConfig.ML_APP_NAME,
                api_key=DatadogConfig.API_KEY,
                site=DatadogConfig.SITE,
                agentless_enabled=True,
            )
            print("✅ LLM Observability enabled for complete agent tracing")
            logger.info("LLM Observability enabled successfully")
        except Exception as e:
            logger.error(f"Failed to enable LLM Observability: {e}")
            raise
    
    def flush_data(self):
        """Flush LLM Observability data to Datadog."""
        try:
            LLMObs.flush()
            logger.info("Data successfully flushed to Datadog")
            return True
        except Exception as e:
            logger.error(f"Failed to flush data to Datadog: {e}")
            return False
    
    def get_llm_obs(self):
        """Get LLMObs instance for use in other modules."""
        return LLMObs 