import os
import boto3
import time
import logging
import json
import re
import uuid
import dotenv
from collections import defaultdict

# CRITICAL: Set environment variables BEFORE importing ddtrace to disable APM
# Load .env if present
dotenv.load_dotenv()
os.environ["DD_TRACE_ENABLED"] = "false"
os.environ["DD_AGENT_HOST"] = ""
os.environ["DD_TRACE_AGENT_URL"] = ""

from ddtrace.llmobs import LLMObs

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Bedrock configuration
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "eu-west-1")
AGENT_ID = os.environ.get("AGENT_ID", "")
AGENT_ALIAS_ID = os.environ.get("AGENT_ALIAS_ID", "")

# Datadog configuration
DATADOG_API_KEY = os.environ.get("DATADOG_API_KEY", "")
DATADOG_SITE = os.environ.get("DATADOG_SITE", "datadoghq.eu")
ML_APP_NAME = os.environ.get("ML_APP_NAME", "migdal-zone")

# Enable LLM Observability using in-code setup
print("Enabling Datadog LLM Observability for Complete Agent Separation...")
LLMObs.enable(
    ml_app=ML_APP_NAME,
    api_key=DATADOG_API_KEY,
    site=DATADOG_SITE,
    agentless_enabled=True,
)
print("✅ LLM Observability enabled for complete agent tracing")

# Initialize Bedrock client
client = boto3.client("bedrock-agent-runtime", region_name=BEDROCK_REGION)

def safe_print(text):
    """Print text safely, avoiding encoding issues."""
    try:
        print(text)
    except (UnicodeEncodeError, ValueError):
        try:
            print(text.encode('ascii', 'ignore').decode('ascii'))
        except:
            print("Processing item...")

def extract_chunks_from_trace(trace_events):
    """Extract chunks from trace events based on the AWS documentation structure."""
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
        safe_print(f"Error extracting chunks from trace: {str(e)}")
        return ""

def process_trace_event(trace_event, session_id):
    """Process a single trace event and create appropriate spans"""
    try:
        # Get basic trace info
        agent_id = trace_event.get("agentId", "unknown")
        agent_name = trace_event.get("agentName", "unknown")
        collaborator_name = trace_event.get("collaboratorName", "")
        trace_data = trace_event.get("trace", {})
        
        # Process PreProcessingTrace
        if "preProcessingTrace" in trace_data:
            preprocessing = trace_data["preProcessingTrace"]
            model_input = preprocessing.get("modelInvocationInput", {})
            model_output = preprocessing.get("modelInvocationOutput", {})
            
            prompt_text = model_input.get("text", "")
            rationale = model_output.get("parsedResponse", {}).get("rationale", "")
            is_valid = model_output.get("parsedResponse", {}).get("isValid", True)
            
            with LLMObs.task(name="preprocessing-validation", session_id=session_id):
                LLMObs.annotate(
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
        
        # Process OrchestrationTrace
        if "orchestrationTrace" in trace_data:
            orchestration = trace_data["orchestrationTrace"]
            
            # Process Rationale
            if "rationale" in orchestration:
                rationale = orchestration["rationale"]
                rationale_text = rationale.get("text", "")
                
                with LLMObs.agent(name=f"reasoning-agent-{agent_name}", session_id=session_id):
                    LLMObs.annotate(
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
            
            # Process InvocationInput
            if "invocationInput" in orchestration:
                invocation_input = orchestration["invocationInput"]
                invocation_type = invocation_input.get("invocationType", "")
                
                if invocation_type == "ACTION_GROUP":
                    action_input = invocation_input.get("actionGroupInvocationInput", {})
                    action_name = action_input.get("actionGroupName", "")
                    api_path = action_input.get("apiPath", "")
                    verb = action_input.get("verb", "")
                    parameters = action_input.get("parameters", [])
                    
                    # Format parameters for display
                    params_str = json.dumps(parameters, indent=2) if parameters else "No parameters"
                    
                    with LLMObs.tool(name=f"action-{action_name}", session_id=session_id):
                        LLMObs.annotate(
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
                
                elif invocation_type == "KNOWLEDGE_BASE":
                    kb_input = invocation_input.get("knowledgeBaseLookupInput", {})
                    kb_id = kb_input.get("knowledgeBaseId", "")
                    query_text = kb_input.get("text", "")
                    
                    with LLMObs.retrieval(name="knowledge-base-query", session_id=session_id):
                        LLMObs.annotate(
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
                
                elif invocation_type == "AGENT_COLLABORATOR":
                    collab_input = invocation_input.get("agentCollaboratorInvocationInput", {})
                    collab_name = collab_input.get("agentCollaboratorName", "")
                    input_text = collab_input.get("input", {}).get("text", "")
                    
                    with LLMObs.agent(name=f"collaborator-{collab_name}", session_id=session_id):
                        LLMObs.annotate(
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
            
            # Process Observation
            if "observation" in orchestration:
                observation = orchestration["observation"]
                obs_type = observation.get("type", "")
                
                if obs_type == "ACTION_GROUP":
                    action_output = observation.get("actionGroupInvocationOutput", {})
                    response_text = action_output.get("text", "")
                    
                    # Try to parse JSON response
                    try:
                        if response_text.startswith('"') and response_text.endswith('"'):
                            response_text = json.loads(response_text)
                        parsed_response = json.loads(response_text) if isinstance(response_text, str) and response_text.strip().startswith('{') else response_text
                        formatted_response = json.dumps(parsed_response, indent=2) if isinstance(parsed_response, dict) else str(response_text)
                    except:
                        formatted_response = str(response_text)
                    
                    with LLMObs.tool(name="action-group-response", session_id=session_id):
                        LLMObs.annotate(
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
                
                elif obs_type == "KNOWLEDGE_BASE":
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
                    
                    with LLMObs.retrieval(name="knowledge-base-retrieval", session_id=session_id):
                        LLMObs.annotate(
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
                
                elif obs_type == "AGENT_COLLABORATOR":
                    collab_output = observation.get("agentCollaboratorInvocationOutput", {})
                    collab_name = collab_output.get("agentCollaboratorName", "")
                    output_text = collab_output.get("output", {}).get("text", "")
                    
                    with LLMObs.agent(name=f"collaborator-response-{collab_name}", session_id=session_id):
                        LLMObs.annotate(
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
                
                elif obs_type == "FINISH":
                    final_response = observation.get("finalResponse", {})
                    final_text = final_response.get("text", "")
                    
                    with LLMObs.llm(name="final-response-generator", model_name="bedrock-agent", model_provider="aws", session_id=session_id):
                        LLMObs.annotate(
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
                
                elif obs_type == "REPROMPT":
                    reprompt = observation.get("repromptResponse", {})
                    reprompt_text = reprompt.get("text", "")
                    reprompt_source = reprompt.get("source", "")
                    
                    with LLMObs.agent(name="clarification-agent", session_id=session_id):
                        LLMObs.annotate(
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
        
        # Process PostProcessingTrace
        if "postProcessingTrace" in trace_data:
            postprocessing = trace_data["postProcessingTrace"]
            model_input = postprocessing.get("modelInvocationInput", {})
            model_output = postprocessing.get("modelInvocationOutput", {})
            
            input_text = model_input.get("text", "")
            output_text = model_output.get("parsedResponse", {}).get("text", "")
            
            with LLMObs.task(name="response-postprocessing", session_id=session_id):
                LLMObs.annotate(
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
        
        # Process GuardrailTrace
        if "guardrailTrace" in trace_data:
            guardrail = trace_data["guardrailTrace"]
            action = guardrail.get("action", "")
            
            with LLMObs.task(name="guardrail-assessment", session_id=session_id):
                LLMObs.annotate(
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
        
        # Process FailureTrace
        if "failureTrace" in trace_data:
            failure = trace_data["failureTrace"]
            failure_reason = failure.get("failureReason", "")
            
            with LLMObs.task(name="error-handler", session_id=session_id):
                LLMObs.annotate(
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
    
    except Exception as e:
        safe_print(f"Error processing trace event: {str(e)}")

def ask_agent_with_bedrock_traces(question, expected=None):
    """Ask agent and capture all Bedrock traces following AWS documentation structure"""
    output = ""
    session_id = f"bedrock-trace_{int(time.time())}"
    trace_count = 0
    
    safe_print(f"\n🎯 Starting BEDROCK TRACE CAPTURE for: {question}")
    
    with LLMObs.workflow(name="bedrock-agent-workflow", session_id=session_id):
        try:
            # Annotate the workflow with the initial question
            LLMObs.annotate(
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
            
            with LLMObs.agent(name=f"bedrock-agent-{AGENT_ID}", session_id=session_id):
                safe_print(f"Processing question: {question}")
                
                response = client.invoke_agent(
                    agentId=AGENT_ID,
                    agentAliasId=AGENT_ALIAS_ID,
                    sessionId=session_id,
                    inputText=question,
                    enableTrace=True
                )
                
                safe_print("🔍 Processing trace events...")
                
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
                        process_trace_event(event["trace"], session_id)
                
                # Extract additional chunks using your original method
                chunks = extract_chunks_from_trace([{"trace": event.get("trace", {})} for event in response.get("completion", []) if "trace" in event])
                
                # Annotate the main agent with results
                LLMObs.annotate(
                    input_data=[{"role": "user", "content": question}],
                    output_data=[{"role": "assistant", "content": output}],
                    metadata={
                        "total_trace_events": trace_count,
                        "response_length": len(output),
                        "chunks_extracted": len(chunks) if chunks else 0,
                        "expected_answer": expected,
                        "agent_id": AGENT_ID,
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
            LLMObs.annotate(
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

def main():
    """Main function with Bedrock trace capture"""
    questions = [
        {
            "question": "כמה משימות יש לי?",
            "expected": "Number of tasks"
        },
        {
            "question": "אילו פוליסות הן כשרות?", 
            "expected": "Valid policies information"
        },
        {
            "question": "כמה לקוחות יש לי עם ביטוח דירה אקטיבי?",
            "expected": "Active home insurance clients count"
        }
    ]
    
    print("=" * 80)
    print("🎯 BEDROCK AGENT TRACE CAPTURE - Following AWS Documentation")
    print(f"📍 Application: {ML_APP_NAME}")
    print(f"🌍 Datadog Site: {DATADOG_SITE}")
    print(f"🤖 Agent ID: {AGENT_ID}")
    print("📊 Captures: All AWS Bedrock trace types with actual content")
    print("🔍 Following: PreProcessing, Orchestration, PostProcessing, Guardrail, Failure")
    print("=" * 80)
    
    successful_calls = 0
    total_calls = len(questions)
    
    for i, item in enumerate(questions, 1):
        print(f"\n{'='*20} Test {i}/{total_calls} {'='*20}")
        print(f"❓ Question: {item['question']}")
        print(f"📋 Expected: {item['expected']}")
        print("-" * 60)
        
        start_time = time.time()
        result = ask_agent_with_bedrock_traces(item["question"], item["expected"])
        end_time = time.time()
        duration = end_time - start_time
        
        if result:
            successful_calls += 1
            print(f"✅ SUCCESS - Duration: {duration:.2f}s")
            print(f"📤 Response: {result[:200]}{'...' if len(result) > 200 else ''}")
        else:
            print(f"❌ FAILED - Duration: {duration:.2f}s")
            print("📤 No response received")
        
        if i < total_calls:
            time.sleep(3)
    
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print(f"✅ Successful calls: {successful_calls}/{total_calls}")
    print(f"❌ Failed calls: {total_calls - successful_calls}/{total_calls}")
    print(f"📈 Success rate: {(successful_calls/total_calls)*100:.1f}%")
    print("=" * 80)
    
    print("\n🔄 Flushing LLM Observability data to Datadog...")
    try:
        LLMObs.flush()
        print("✅ Data successfully flushed to Datadog!")
        print(f"🔗 Check your traces at: https://app.{DATADOG_SITE}/llm/")
        print("🎯 You should now see:")
        print("   • Actual input/output content in each span")
        print("   • Agent reasoning (rationale) with full text")
        print("   • Action group calls with parameters & responses")
        print("   • Knowledge base queries with retrieved documents")
        print("   • Final responses with complete content")
        print("   • All trace types following AWS Bedrock structure")
    except Exception as flush_error:
        print(f"❌ Flush error: {flush_error}")
    
    print("\n🎉 Bedrock trace capture with content completed!")

if __name__ == "__main__":
    main()