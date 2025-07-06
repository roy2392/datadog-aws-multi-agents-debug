"""
Trace processor module for handling Bedrock trace events.
Processes trace events and creates appropriate Datadog spans.
"""

import json
from typing import Dict, Any
from utils.logger import safe_print, get_logger
from utils.text_processing import safe_json_parse, format_response_for_display

logger = get_logger(__name__)

class TraceProcessor:
    """Processor for Bedrock trace events."""
    
    def __init__(self, llm_obs):
        """Initialize trace processor with LLM Observability instance."""
        self.llm_obs = llm_obs
    
    def process_trace_event(self, trace_event: Dict[str, Any], session_id: str):
        """
        Process a single trace event and create appropriate spans.
        
        Args:
            trace_event: The trace event to process
            session_id: Session identifier for tracking
        """
        try:
            # Get basic trace info
            agent_id = trace_event.get("agentId", "unknown")
            agent_name = trace_event.get("agentName", "unknown")
            collaborator_name = trace_event.get("collaboratorName", "")
            trace_data = trace_event.get("trace", {})
            
            # Process different trace types
            self._process_preprocessing_trace(trace_data, session_id, agent_name)
            self._process_orchestration_trace(trace_data, session_id, agent_id, agent_name, collaborator_name)
            self._process_postprocessing_trace(trace_data, session_id, agent_name)
            self._process_guardrail_trace(trace_data, session_id)
            self._process_failure_trace(trace_data, session_id)
            
        except Exception as e:
            logger.error(f"Error processing trace event: {str(e)}")
            safe_print(f"Error processing trace event: {str(e)}")
    
    def _process_preprocessing_trace(self, trace_data: Dict[str, Any], session_id: str, agent_name: str):
        """Process PreProcessingTrace events."""
        if "preProcessingTrace" not in trace_data:
            return
            
        preprocessing = trace_data["preProcessingTrace"]
        model_input = preprocessing.get("modelInvocationInput", {})
        model_output = preprocessing.get("modelInvocationOutput", {})
        
        prompt_text = model_input.get("text", "")
        rationale = model_output.get("parsedResponse", {}).get("rationale", "")
        is_valid = model_output.get("parsedResponse", {}).get("isValid", True)
        
        with self.llm_obs.task(name="preprocessing-validation", session_id=session_id):
            self.llm_obs.annotate(
                input_data=prompt_text,
                output_data=f"Valid: {is_valid}, Rationale: {rationale}",
                metadata={
                    "step": "preprocessing",
                    "is_valid": is_valid,
                    "foundation_model": model_input.get("foundationModel", ""),
                    "usage": model_output.get("metadata", {}).get("usage", {})
                },
                tags={
                    "trace_type": "preprocessing",
                    "agent_name": agent_name,
                    "valid_input": str(is_valid)
                }
            )
            safe_print(f"✅ Preprocessing: Valid={is_valid}, Rationale={rationale[:50]}...")
    
    def _process_orchestration_trace(self, trace_data: Dict[str, Any], session_id: str, 
                                   agent_id: str, agent_name: str, collaborator_name: str):
        """Process OrchestrationTrace events."""
        if "orchestrationTrace" not in trace_data:
            return
            
        orchestration = trace_data["orchestrationTrace"]
        
        # Process Rationale
        self._process_rationale(orchestration, session_id, agent_id, agent_name, collaborator_name)
        
        # Process InvocationInput
        self._process_invocation_input(orchestration, session_id, agent_name)
        
        # Process Observation
        self._process_observation(orchestration, session_id, agent_name)
    
    def _process_rationale(self, orchestration: Dict[str, Any], session_id: str, 
                          agent_id: str, agent_name: str, collaborator_name: str):
        """Process rationale from orchestration trace."""
        if "rationale" not in orchestration:
            return
            
        rationale = orchestration["rationale"]
        rationale_text = rationale.get("text", "")
        
        with self.llm_obs.agent(name=f"reasoning-agent-{agent_name}", session_id=session_id):
            self.llm_obs.annotate(
                input_data="Analyzing user input and determining next steps",
                output_data=rationale_text,
                metadata={
                    "step": "reasoning",
                    "reasoning_length": len(rationale_text),
                    "agent_id": agent_id,
                    "collaborator": collaborator_name
                },
                tags={
                    "trace_type": "rationale",
                    "agent_name": agent_name,
                    "has_collaborator": bool(collaborator_name)
                }
            )
            safe_print(f"✅ Rationale: {rationale_text[:100]}...")
    
    def _process_invocation_input(self, orchestration: Dict[str, Any], session_id: str, agent_name: str):
        """Process invocation input from orchestration trace."""
        if "invocationInput" not in orchestration:
            return
            
        invocation_input = orchestration["invocationInput"]
        invocation_type = invocation_input.get("invocationType", "")
        
        if invocation_type == "ACTION_GROUP":
            self._process_action_group_input(invocation_input, session_id, agent_name)
        elif invocation_type == "KNOWLEDGE_BASE":
            self._process_knowledge_base_input(invocation_input, session_id)
        elif invocation_type == "AGENT_COLLABORATOR":
            self._process_collaborator_input(invocation_input, session_id)
    
    def _process_action_group_input(self, invocation_input: Dict[str, Any], session_id: str, agent_name: str):
        """Process action group invocation input."""
        action_input = invocation_input.get("actionGroupInvocationInput", {})
        action_name = action_input.get("actionGroupName", "")
        api_path = action_input.get("apiPath", "")
        verb = action_input.get("verb", "")
        parameters = action_input.get("parameters", [])
        
        params_str = json.dumps(parameters, indent=2) if parameters else "No parameters"
        
        with self.llm_obs.tool(name=f"action-{action_name}", session_id=session_id):
            self.llm_obs.annotate(
                input_data=f"Calling {verb} {api_path} with parameters: {params_str}",
                output_data="Action group invocation initiated",
                metadata={
                    "action_group_name": action_name,
                    "api_path": api_path,
                    "verb": verb,
                    "parameters_count": len(parameters),
                    "execution_type": action_input.get("executionType", "")
                },
                tags={
                    "trace_type": "action_input",
                    "action_group": action_name,
                    "api_method": verb
                }
            )
            safe_print(f"✅ Action Input: {action_name} - {verb} {api_path}")
    
    def _process_knowledge_base_input(self, invocation_input: Dict[str, Any], session_id: str):
        """Process knowledge base invocation input."""
        kb_input = invocation_input.get("knowledgeBaseLookupInput", {})
        kb_id = kb_input.get("knowledgeBaseId", "")
        query_text = kb_input.get("text", "")
        
        with self.llm_obs.retrieval(name="knowledge-base-query", session_id=session_id):
            self.llm_obs.annotate(
                input_data=query_text,
                output_data="Knowledge base query initiated",
                metadata={
                    "knowledge_base_id": kb_id,
                    "query_length": len(query_text)
                },
                tags={
                    "trace_type": "kb_input",
                    "knowledge_base_id": kb_id
                }
            )
            safe_print(f"✅ KB Query: {query_text[:100]}...")
    
    def _process_collaborator_input(self, invocation_input: Dict[str, Any], session_id: str):
        """Process collaborator invocation input."""
        collab_input = invocation_input.get("agentCollaboratorInvocationInput", {})
        collab_name = collab_input.get("agentCollaboratorName", "")
        input_text = collab_input.get("input", {}).get("text", "")
        
        with self.llm_obs.agent(name=f"collaborator-{collab_name}", session_id=session_id):
            self.llm_obs.annotate(
                input_data=input_text,
                output_data="Collaborator agent invocation initiated",
                metadata={
                    "collaborator_name": collab_name,
                    "collaborator_arn": collab_input.get("agentCollaboratorAliasArn", ""),
                    "input_length": len(input_text)
                },
                tags={
                    "trace_type": "collaborator_input",
                    "collaborator": collab_name
                }
            )
            safe_print(f"✅ Collaborator Input: {collab_name} - {input_text[:100]}...")
    
    def _process_observation(self, orchestration: Dict[str, Any], session_id: str, agent_name: str):
        """Process observation from orchestration trace."""
        if "observation" not in orchestration:
            return
            
        observation = orchestration["observation"]
        obs_type = observation.get("type", "")
        
        if obs_type == "ACTION_GROUP":
            self._process_action_group_output(observation, session_id)
        elif obs_type == "KNOWLEDGE_BASE":
            self._process_knowledge_base_output(observation, session_id)
        elif obs_type == "AGENT_COLLABORATOR":
            self._process_collaborator_output(observation, session_id)
        elif obs_type == "FINISH":
            self._process_final_response(observation, session_id)
        elif obs_type == "REPROMPT":
            self._process_reprompt(observation, session_id)
    
    def _process_action_group_output(self, observation: Dict[str, Any], session_id: str):
        """Process action group output."""
        action_output = observation.get("actionGroupInvocationOutput", {})
        response_text = action_output.get("text", "")
        
        formatted_response = format_response_for_display(response_text)
        
        with self.llm_obs.tool(name="action-group-response", session_id=session_id):
            self.llm_obs.annotate(
                input_data="Action group execution completed",
                output_data=formatted_response,
                metadata={
                    "response_length": len(str(response_text)),
                    "response_type": "json" if str(response_text).strip().startswith('{') else "text"
                },
                tags={
                    "trace_type": "action_output",
                    "has_response": bool(response_text)
                }
            )
            safe_print(f"✅ Action Output: {str(response_text)[:200]}...")
    
    def _process_knowledge_base_output(self, observation: Dict[str, Any], session_id: str):
        """Process knowledge base output."""
        kb_output = observation.get("knowledgeBaseLookupOutput", {})
        references = kb_output.get("retrievedReferences", [])
        
        # Extract all reference texts and sources
        retrieved_docs = []
        for ref in references:
            text = ref.get("content", {}).get("text", "")
            source = ref.get("location", {}).get("s3Location", {}).get("uri", "")
            if text:
                retrieved_docs.append({
                    "text": text,
                    "source": source,
                    "id": f"doc_{len(retrieved_docs) + 1}"
                })
        
        all_text = "\n\n".join([doc["text"] for doc in retrieved_docs])
        
        with self.llm_obs.retrieval(name="knowledge-base-retrieval", session_id=session_id):
            self.llm_obs.annotate(
                input_data="Knowledge base search completed",
                output_data=retrieved_docs,
                metadata={
                    "references_count": len(references),
                    "total_content_length": len(all_text),
                    "sources": [doc["source"] for doc in retrieved_docs]
                },
                tags={
                    "trace_type": "kb_output",
                    "references_found": str(len(references))
                }
            )
            safe_print(f"✅ KB Output: {len(references)} references, {len(all_text)} chars")
    
    def _process_collaborator_output(self, observation: Dict[str, Any], session_id: str):
        """Process collaborator output."""
        collab_output = observation.get("agentCollaboratorInvocationOutput", {})
        collab_name = collab_output.get("agentCollaboratorName", "")
        output_text = collab_output.get("output", {}).get("text", "")
        
        with self.llm_obs.agent(name=f"collaborator-response-{collab_name}", session_id=session_id):
            self.llm_obs.annotate(
                input_data=f"Response from {collab_name}",
                output_data=output_text,
                metadata={
                    "collaborator_name": collab_name,
                    "response_length": len(output_text)
                },
                tags={
                    "trace_type": "collaborator_output",
                    "collaborator": collab_name
                }
            )
            safe_print(f"✅ Collaborator Output: {collab_name} - {output_text[:100]}...")
    
    def _process_final_response(self, observation: Dict[str, Any], session_id: str):
        """Process final response."""
        final_response = observation.get("finalResponse", {})
        final_text = final_response.get("text", "")
        
        with self.llm_obs.llm(name="final-response-generator", model_name="bedrock-agent", 
                             model_provider="aws", session_id=session_id):
            self.llm_obs.annotate(
                input_data=[{"role": "system", "content": "Generate final response to user"}],
                output_data=[{"role": "assistant", "content": final_text}],
                metadata={
                    "is_final": True,
                    "response_length": len(final_text)
                },
                tags={
                    "trace_type": "final_response",
                    "is_complete": "true"
                }
            )
            safe_print(f"✅ Final Response: {final_text[:200]}...")
    
    def _process_reprompt(self, observation: Dict[str, Any], session_id: str):
        """Process reprompt response."""
        reprompt = observation.get("repromptResponse", {})
        reprompt_text = reprompt.get("text", "")
        reprompt_source = reprompt.get("source", "")
        
        with self.llm_obs.agent(name="clarification-agent", session_id=session_id):
            self.llm_obs.annotate(
                input_data=f"Reprompt needed from {reprompt_source}",
                output_data=reprompt_text,
                metadata={
                    "reprompt_source": reprompt_source,
                    "requires_clarification": True
                },
                tags={
                    "trace_type": "reprompt",
                    "source": reprompt_source
                }
            )
            safe_print(f"✅ Reprompt: {reprompt_text[:100]}...")
    
    def _process_postprocessing_trace(self, trace_data: Dict[str, Any], session_id: str, agent_name: str):
        """Process PostProcessingTrace events."""
        if "postProcessingTrace" not in trace_data:
            return
            
        postprocessing = trace_data["postProcessingTrace"]
        model_input = postprocessing.get("modelInvocationInput", {})
        model_output = postprocessing.get("modelInvocationOutput", {})
        
        input_text = model_input.get("text", "")
        output_text = model_output.get("parsedResponse", {}).get("text", "")
        
        with self.llm_obs.task(name="response-postprocessing", session_id=session_id):
            self.llm_obs.annotate(
                input_data=input_text,
                output_data=output_text,
                metadata={
                    "step": "postprocessing",
                    "foundation_model": model_input.get("foundationModel", ""),
                    "usage": model_output.get("metadata", {}).get("usage", {})
                },
                tags={
                    "trace_type": "postprocessing",
                    "agent_name": agent_name
                }
            )
            safe_print(f"✅ Postprocessing: {output_text[:100]}...")
    
    def _process_guardrail_trace(self, trace_data: Dict[str, Any], session_id: str):
        """Process GuardrailTrace events."""
        if "guardrailTrace" not in trace_data:
            return
            
        guardrail = trace_data["guardrailTrace"]
        action = guardrail.get("action", "")
        
        with self.llm_obs.task(name="guardrail-assessment", session_id=session_id):
            self.llm_obs.annotate(
                input_data="Guardrail safety assessment",
                output_data=f"Action taken: {action}",
                metadata={
                    "guardrail_action": action,
                    "intervention": action == "GUARDRAIL_INTERVENED",
                    "input_assessments": len(guardrail.get("inputAssessments", [])),
                    "output_assessments": len(guardrail.get("outputAssessments", []))
                },
                tags={
                    "trace_type": "guardrail",
                    "action": action
                }
            )
            safe_print(f"✅ Guardrail: {action}")
    
    def _process_failure_trace(self, trace_data: Dict[str, Any], session_id: str):
        """Process FailureTrace events."""
        if "failureTrace" not in trace_data:
            return
            
        failure = trace_data["failureTrace"]
        failure_reason = failure.get("failureReason", "")
        
        with self.llm_obs.task(name="error-handler", session_id=session_id):
            self.llm_obs.annotate(
                input_data="Processing failed",
                output_data=f"Failure: {failure_reason}",
                metadata={
                    "failed": True,
                    "failure_reason": failure_reason
                },
                tags={
                    "trace_type": "failure",
                    "error": "true"
                }
            )
            safe_print(f"❌ Failure: {failure_reason}") 