"""
Agent orchestrator module for coordinating Bedrock agent interactions.
Handles the main workflow of asking agents and processing traces.
"""

import time
from typing import Optional, Dict, Any
from services.bedrock_service import BedrockService
from services.datadog_service import DatadogService
from processors.trace_processor import TraceProcessor
from utils.logger import safe_print, get_logger
from utils.text_processing import extract_chunks_from_trace

logger = get_logger(__name__)

class AgentOrchestrator:
    """Orchestrator for Bedrock agent interactions and trace processing."""
    
    def __init__(self):
        """Initialize the orchestrator with required services."""
        self.bedrock_service = BedrockService()
        self.datadog_service = DatadogService()
        self.trace_processor = TraceProcessor(self.datadog_service.get_llm_obs())
        self.llm_obs = self.datadog_service.get_llm_obs()
    
    def ask_agent_with_traces(self, question: str, expected: Optional[str] = None) -> Optional[str]:
        """
        Ask agent and capture all Bedrock traces following AWS documentation structure.
        
        Args:
            question: The question to ask the agent
            expected: Expected answer type (for metadata)
            
        Returns:
            Agent response or None if failed
        """
        output = ""
        session_id = f"bedrock-trace_{int(time.time())}"
        trace_count = 0
        
        safe_print(f"\n🎯 Starting BEDROCK TRACE CAPTURE for: {question}")
        
        with self.llm_obs.workflow(name="bedrock-agent-workflow", session_id=session_id):
            try:
                # Annotate the workflow with the initial question
                self.llm_obs.annotate(
                    input_data=question,
                    output_data="Starting Bedrock agent processing",
                    metadata={
                        "workflow_start": True,
                        "expected_answer": expected
                    },
                    tags={
                        "workflow": "bedrock_agent",
                        "language": "hebrew"
                    }
                )
                
                with self.llm_obs.agent(name=f"bedrock-agent-{self.bedrock_service.get_agent_info()['agent_id']}", 
                                      session_id=session_id):
                    safe_print(f"Processing question: {question}")
                    
                    # Invoke the agent
                    response = self.bedrock_service.invoke_agent(question, session_id)
                    
                    safe_print("🔍 Processing trace events...")
                    
                    # Process completion events
                    for event_index, event in enumerate(response.get("completion", [])):
                        if "chunk" in event:
                            chunk = event["chunk"]
                            if "bytes" in chunk:
                                text = chunk["bytes"].decode('utf-8')
                                output += text
                                safe_print(f"📝 Chunk {event_index + 1}: {text[:50]}{'...' if len(text) > 50 else ''}")
                        
                        elif "trace" in event:
                            trace_count += 1
                            safe_print(f"🔍 Processing trace event {trace_count}")
                            self.trace_processor.process_trace_event(event["trace"], session_id)
                    
                    # Extract additional chunks using the original method
                    chunks = extract_chunks_from_trace([
                        {"trace": event.get("trace", {})} 
                        for event in response.get("completion", []) 
                        if "trace" in event
                    ])
                    
                    # Annotate the main agent with results
                    self.llm_obs.annotate(
                        input_data=[{"role": "user", "content": question}],
                        output_data=[{"role": "assistant", "content": output}],
                        metadata={
                            "total_trace_events": trace_count,
                            "response_length": len(output),
                            "chunks_extracted": len(chunks) if chunks else 0,
                            "expected_answer": expected,
                            "agent_id": self.bedrock_service.get_agent_info()['agent_id'],
                            "session_id": session_id
                        },
                        tags={
                            "agent_type": "bedrock_supervisor",
                            "trace_events_count": str(trace_count),
                            "has_output": str(bool(output))
                        }
                    )
                    
                    safe_print(f"✅ Processed {trace_count} trace events")
                    safe_print(f"📤 Final output length: {len(output)} chars")
                    
                    return output.strip() if output else None
                    
            except Exception as e:
                safe_print(f"❌ Error in workflow: {str(e)}")
                logger.error(f"Workflow error: {e}")
                self.llm_obs.annotate(
                    input_data=question,
                    output_data=f"Error: {str(e)}",
                    metadata={
                        "error": str(e),
                        "error_type": type(e).__name__
                    },
                    tags={
                        "error": "true",
                        "workflow": "failed"
                    }
                )
                return None
    
    def flush_data(self) -> bool:
        """Flush data to Datadog."""
        return self.datadog_service.flush_data()
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get information about the configured agent."""
        return self.bedrock_service.get_agent_info() 