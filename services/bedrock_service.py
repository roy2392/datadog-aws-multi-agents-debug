"""
Bedrock service module for AWS Bedrock operations.
Handles Bedrock client initialization and agent interactions.
"""

import boto3
from config import BedrockConfig
from utils.logger import get_logger

logger = get_logger(__name__)

class BedrockService:
    """Service class for AWS Bedrock operations."""
    
    def __init__(self):
        """Initialize Bedrock service with client."""
        self.client = boto3.client(
            "bedrock-agent-runtime", 
            region_name=BedrockConfig.REGION
        )
        logger.info(f"Bedrock client initialized for region: {BedrockConfig.REGION}")
    
    def invoke_agent(self, question: str, session_id: str) -> dict:
        """
        Invoke Bedrock agent with the given question.
        
        Args:
            question: The question to ask the agent
            session_id: Session identifier for tracking
            
        Returns:
            Response from Bedrock agent
        """
        try:
            response = self.client.invoke_agent(
                agentId=BedrockConfig.AGENT_ID,
                agentAliasId=BedrockConfig.AGENT_ALIAS_ID,
                sessionId=session_id,
                inputText=question,
                enableTrace=True
            )
            logger.info(f"Agent invoked successfully for session: {session_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to invoke agent: {e}")
            raise
    
    def get_agent_info(self) -> dict:
        """Get information about the configured agent."""
        return {
            "agent_id": BedrockConfig.AGENT_ID,
            "agent_alias_id": BedrockConfig.AGENT_ALIAS_ID,
            "region": BedrockConfig.REGION
        } 