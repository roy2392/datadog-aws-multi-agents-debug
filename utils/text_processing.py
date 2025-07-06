"""
Text processing utilities for the Datadog Multi-Agent Debugging project.
Handles text extraction, formatting, and JSON parsing.
"""

import json
from typing import Any, Dict, List, Optional

def extract_chunks_from_trace(trace_events: List[Dict[str, Any]]) -> str:
    """
    Extract chunks from trace events based on the AWS documentation structure.
    
    Args:
        trace_events: List of trace events from Bedrock
        
    Returns:
        Extracted text chunks as a single string
    """
    chunks_text = ""
    
    try:
        for trace_event in trace_events:
            if 'trace' in trace_event:
                trace = trace_event['trace']
                
                # Look for orchestrationTrace
                if 'orchestrationTrace' in trace:
                    orchestration = trace['orchestrationTrace']
                    
                    # Look for observation with actionGroupInvocationOutput
                    if 'observation' in orchestration:
                        observation = orchestration['observation']
                        
                        if 'actionGroupInvocationOutput' in observation:
                            action_output = observation['actionGroupInvocationOutput']
                            if 'text' in action_output:
                                chunks_text = action_output['text']
                                # Remove quotes if it's a JSON string
                                if chunks_text.startswith('"') and chunks_text.endswith('"'):
                                    try:
                                        chunks_text = json.loads(chunks_text)
                                    except:
                                        pass
                        
                        # Also look for knowledgeBaseLookupOutput
                        elif 'knowledgeBaseLookupOutput' in observation:
                            kb_output = observation['knowledgeBaseLookupOutput']
                            if 'retrievedReferences' in kb_output:
                                references = kb_output['retrievedReferences']
                                reference_texts = []
                                for ref in references:
                                    if 'content' in ref and 'text' in ref['content']:
                                        reference_texts.append(ref['content']['text'])
                                chunks_text = '\n\n'.join(reference_texts)
        
        return chunks_text
    except Exception as e:
        print(f"Error extracting chunks from trace: {str(e)}")
        return ""

def safe_json_parse(text: str) -> Any:
    """
    Safely parse JSON text, handling various formats.
    
    Args:
        text: Text to parse as JSON
        
    Returns:
        Parsed JSON object or original text if parsing fails
    """
    try:
        # Remove quotes if it's a JSON string
        if text.startswith('"') and text.endswith('"'):
            text = json.loads(text)
        
        # Try to parse as JSON
        if isinstance(text, str) and text.strip().startswith('{'):
            return json.loads(text)
        
        return text
    except (json.JSONDecodeError, ValueError):
        return text

def format_response_for_display(response_text: str) -> str:
    """
    Format response text for display, handling JSON formatting.
    
    Args:
        response_text: Raw response text
        
    Returns:
        Formatted response string
    """
    try:
        parsed_response = safe_json_parse(response_text)
        if isinstance(parsed_response, dict):
            return json.dumps(parsed_response, indent=2)
        return str(response_text)
    except:
        return str(response_text)

def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to specified length with ellipsis.
    
    Args:
        text: Text to truncate
        max_length: Maximum length before truncation
        
    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..." 