import os
import boto3
import time
import logging
import json
import re
import uuid
import dotenv

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

def detect_response_type(content):
    """Detect the type of response (SQL, API, text, etc.)"""
    content_lower = content.lower().strip()
    
    if not content:
        return "empty_response"
    
    # SQL Detection
    sql_keywords = ['select', 'insert', 'update', 'delete', 'create', 'alter', 'drop', 'from', 'where', 'join']
    if any(keyword in content_lower for keyword in sql_keywords) and ('from' in content_lower or 'select' in content_lower):
        return "sql_query"
    
    # API/JSON Detection
    if content.strip().startswith('{') and content.strip().endswith('}'):
        try:
            json.loads(content)
            return "json_response"
        except:
            pass
    
    # XML Detection
    if content.strip().startswith('<') and content.strip().endswith('>'):
        return "xml_response"
    
    # URL/API Call Detection
    if re.search(r'https?://|api\.|/api/|endpoint', content_lower):
        return "api_call"
    
    # Code Detection
    code_patterns = ['def ', 'function ', 'class ', 'import ', 'return ', '#!/']
    if any(pattern in content_lower for pattern in code_patterns):
        return "code_response"
    
    # Error Detection
    error_patterns = ['error:', 'exception:', 'failed:', 'cannot', 'unable to']
    if any(pattern in content_lower for pattern in error_patterns):
        return "error_response"
    
    # Number/Calculation Detection
    if re.search(r'^\s*\d+\.?\d*\s*$', content.strip()) or 'count:' in content_lower or 'total:' in content_lower:
        return "numeric_response"
    
    # List Detection
    if content.count('\n') > 2 and ('1.' in content or '•' in content or '-' in content):
        return "list_response"
    
    return "text_response"

def extract_agent_info_from_trace(trace_event):
    """Extract detailed agent information from any trace event"""
    agents_found = []
    trace_data = trace_event.get("trace", {})
    
    # Get basic trace info
    trace_id = trace_event.get("traceId", str(uuid.uuid4()))
    agent_id = trace_event.get("agentId", "unknown")
    session_id = trace_event.get("sessionId", "unknown")
    
    if "orchestrationTrace" in trace_data:
        orchestration = trace_data["orchestrationTrace"]
        
        # Extract from rationale
        if "rationale" in orchestration:
            rationale = orchestration["rationale"]
            rationale_text = rationale.get("text", "")
            
            agent_info = {
                "type": "reasoning",
                "agent_id": f"supervisor-reasoning-{trace_id[:8]}",
                "agent_name": "Supervisor Reasoning",
                "content": rationale_text,
                "response_type": detect_response_type(rationale_text),
                "trace_step": "rationale",
                "trace_id": trace_id,
                "session_id": session_id,
                "metadata": {
                    "reasoning_length": len(rationale_text),
                    "contains_delegation": any(word in rationale_text.lower() for word in ['call', 'invoke', 'delegate', 'ask', 'query'])
                }
            }
            agents_found.append(agent_info)
        
        # Extract from invocations
        if "invocation" in orchestration:
            invocation = orchestration["invocation"]
            
            # Knowledge base lookups
            if "knowledgeBaseLookupOutput" in invocation:
                kb_output = invocation["knowledgeBaseLookupOutput"]
                kb_text = ""
                for ref in kb_output.get("retrievedReferences", []):
                    kb_text += ref.get("content", {}).get("text", "") + "\n"
                
                agent_info = {
                    "type": "knowledge_base",
                    "agent_id": f"knowledge-base-{trace_id[:8]}",
                    "agent_name": "Knowledge Base System",
                    "content": kb_text.strip(),
                    "response_type": detect_response_type(kb_text),
                    "trace_step": "knowledge_lookup",
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "metadata": {
                        "references_count": len(kb_output.get("retrievedReferences", [])),
                        "total_content_length": len(kb_text)
                    }
                }
                agents_found.append(agent_info)
            
            # Action group invocations (sub-agents, tools, etc.)
            if "actionGroupInvocationOutput" in invocation:
                action_output = invocation["actionGroupInvocationOutput"]
                action_name = action_output.get("actionGroupName", "unknown_action")
                action_text = action_output.get("text", "")
                
                # Create unique agent ID based on action name
                clean_action_name = re.sub(r'[^a-zA-Z0-9_-]', '-', action_name.lower())
                
                agent_info = {
                    "type": "action_group",
                    "agent_id": f"agent-{clean_action_name}-{trace_id[:8]}",
                    "agent_name": f"Agent: {action_name}",
                    "content": action_text,
                    "response_type": detect_response_type(action_text),
                    "trace_step": "action_invocation",
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "metadata": {
                        "action_group_name": action_name,
                        "response_length": len(action_text),
                        "invocation_type": "action_group"
                    }
                }
                agents_found.append(agent_info)
            
            # Code interpreter outputs
            if "codeInterpreterInvocationOutput" in invocation:
                code_output = invocation["codeInterpreterInvocationOutput"]
                code_text = str(code_output)
                
                agent_info = {
                    "type": "code_interpreter",
                    "agent_id": f"code-interpreter-{trace_id[:8]}",
                    "agent_name": "Code Interpreter",
                    "content": code_text,
                    "response_type": "code_execution",
                    "trace_step": "code_execution",
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "metadata": {
                        "execution_type": "code_interpreter",
                        "output_length": len(code_text)
                    }
                }
                agents_found.append(agent_info)
        
        # Extract from observations
        if "observation" in orchestration:
            observation = orchestration["observation"]
            
            # Final response
            if "finalResponse" in observation:
                final_resp = observation["finalResponse"]
                final_text = final_resp.get("text", "")
                
                agent_info = {
                    "type": "final_response",
                    "agent_id": f"final-response-{trace_id[:8]}",
                    "agent_name": "Final Response Generator",
                    "content": final_text,
                    "response_type": detect_response_type(final_text),
                    "trace_step": "final_response",
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "metadata": {
                        "is_final": True,
                        "response_length": len(final_text)
                    }
                }
                agents_found.append(agent_info)
            
            # Reprompt response (when agent asks for clarification)
            if "repromptResponse" in observation:
                reprompt = observation["repromptResponse"]
                reprompt_text = reprompt.get("text", "")
                
                agent_info = {
                    "type": "reprompt",
                    "agent_id": f"reprompt-{trace_id[:8]}",
                    "agent_name": "Clarification Agent",
                    "content": reprompt_text,
                    "response_type": detect_response_type(reprompt_text),
                    "trace_step": "reprompt",
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "metadata": {
                        "requires_clarification": True,
                        "reprompt_length": len(reprompt_text)
                    }
                }
                agents_found.append(agent_info)
    
    return agents_found

def create_agent_spans(agents_info, session_id):
    """Create properly separated spans for each detected agent"""
    created_spans = []
    
    for agent_info in agents_info:
        agent_type = agent_info["type"]
        agent_id = agent_info["agent_id"]
        agent_name = agent_info["agent_name"]
        content = agent_info["content"]
        response_type = agent_info["response_type"]
        
        # Choose appropriate span type based on agent type
        if agent_type == "reasoning":
            span_context = LLMObs.workflow(name=f"reasoning-{agent_id}", session_id=session_id)
        elif agent_type == "knowledge_base":
            span_context = LLMObs.retrieval(name=f"kb-{agent_id}", session_id=session_id)
        elif agent_type == "action_group":
            # Determine if it's more like an agent or tool based on response type
            if response_type in ["sql_query", "json_response", "api_call"]:
                span_context = LLMObs.tool(name=f"tool-{agent_id}", session_id=session_id)
            else:
                span_context = LLMObs.agent(name=f"agent-{agent_id}", session_id=session_id)
        elif agent_type == "code_interpreter":
            span_context = LLMObs.tool(name=f"code-{agent_id}", session_id=session_id)
        elif agent_type == "final_response":
            span_context = LLMObs.llm(name=f"final-{agent_id}", model_name="bedrock-final", model_provider="aws", session_id=session_id)
        else:
            span_context = LLMObs.task(name=f"task-{agent_id}", session_id=session_id)
        
        with span_context:
            # Prepare input/output based on response type
            if response_type == "sql_query":
                input_data = f"Database query request"
                output_data = content
            elif response_type in ["json_response", "api_call"]:
                input_data = f"API/Service call"
                output_data = content
            elif agent_type == "final_response":
                input_data = [{"role": "system", "content": "Generate final response"}]
                output_data = [{"role": "assistant", "content": content}]
            elif agent_type == "knowledge_base":
                input_data = f"Knowledge retrieval request"
                output_data = [{"text": content, "source": "knowledge_base"}] if content else []
            else:
                input_data = f"Input to {agent_name}"
                output_data = content
            
            # Annotate with rich metadata
            LLMObs.annotate(
                input_data=input_data,
                output_data=output_data,
                metadata={
                    **agent_info["metadata"],
                    "agent_type": agent_type,
                    "response_type": response_type,
                    "trace_step": agent_info["trace_step"],
                    "content_length": len(content),
                    "agent_separation_id": agent_id
                },
                tags={
                    "agent_name": agent_name.lower().replace(" ", "_"),
                    "agent_type": agent_type,
                    "response_type": response_type,
                    "trace_step": agent_info["trace_step"],
                    "separated_agent": "true",
                    "agent_id": agent_id
                }
            )
            
            created_spans.append({
                "agent_id": agent_id,
                "agent_name": agent_name,
                "span_type": agent_type,
                "response_type": response_type
            })
            
            print(f"✅ Created separated span: {agent_name} ({response_type})")
    
    return created_spans

def ask_agent_with_complete_separation(question, expected=None):
    """Ask agent with complete separation of all sub-agents and response types"""
    output = ""
    session_id = f"separated-agents_{int(time.time())}"
    all_trace_events = []
    all_agents_detected = []
    response_types_found = set()
    
    print(f"\n🎯 Starting COMPLETE AGENT SEPARATION for: {question}")
    
    # Main separation workflow
    with LLMObs.workflow(name="complete-agent-separation-workflow", session_id=session_id):
        try:
            # Step 1: Input processing
            with LLMObs.task(name="input-preprocessing", session_id=session_id):
                LLMObs.annotate(
                    input_data=question,
                    output_data="Input ready for multi-agent processing",
                    metadata={
                        "preprocessing_step": "input_analysis",
                        "question_length": len(question)
                    },
                    tags={
                        "step_type": "preprocessing",
                        "workflow_stage": "input"
                    }
                )
            
            # Step 2: Main agent invocation
            with LLMObs.agent(name="main-supervisor-agent", session_id=session_id):
                logging.info(f"Processing with complete separation: {question}")
                
                response = client.invoke_agent(
                    agentId=AGENT_ID,
                    agentAliasId=AGENT_ALIAS_ID,
                    sessionId=session_id,
                    inputText=question,
                    enableTrace=True,
                    streamingConfigurations={
                        "streamFinalResponse": True,
                        "applyGuardrailInterval": 50
                    }
                )
                
                print("🔍 Processing ALL trace events for complete agent separation...")
                
                # Process each event and extract ALL agent information
                for event_index, event in enumerate(response.get("completion", [])):
                    if "chunk" in event:
                        chunk = event["chunk"]
                        if "bytes" in chunk:
                            text = chunk["bytes"].decode('utf-8')
                            output += text
                            print(f"📝 Main output chunk {event_index + 1}: {text[:50]}{'...' if len(text) > 50 else ''}")
                    
                    elif "trace" in event:
                        trace_event = event["trace"]
                        all_trace_events.append(trace_event)
                        
                        print(f"🔍 Processing trace event {len(all_trace_events)}")
                        
                        # Extract ALL agents from this trace event
                        agents_in_trace = extract_agent_info_from_trace(trace_event)
                        all_agents_detected.extend(agents_in_trace)
                        
                        # Track response types
                        for agent in agents_in_trace:
                            response_types_found.add(agent["response_type"])
                        
                        # Create separated spans for each agent
                        if agents_in_trace:
                            created_spans = create_agent_spans(agents_in_trace, session_id)
                            print(f"🎯 Created {len(created_spans)} separated agent spans")
                
                # Annotate main supervisor
                LLMObs.annotate(
                    input_data=[{"role": "user", "content": question}],
                    output_data=[{"role": "assistant", "content": output}],
                    metadata={
                        "supervisor_role": "main_coordinator",
                        "total_trace_events": len(all_trace_events),
                        "agents_detected_count": len(all_agents_detected),
                        "response_types_found": list(response_types_found),
                        "separation_complete": True
                    },
                    tags={
                        "agent_role": "supervisor",
                        "separation_enabled": "true",
                        "agents_count": str(len(all_agents_detected)),
                        "response_types_count": str(len(response_types_found))
                    }
                )
            
            # Step 3: Agent separation summary
            with LLMObs.task(name="agent-separation-summary", session_id=session_id):
                unique_agents = {}
                for agent in all_agents_detected:
                    agent_key = f"{agent['type']}_{agent['agent_name']}"
                    if agent_key not in unique_agents:
                        unique_agents[agent_key] = agent
                
                summary_data = {
                    "total_agents_detected": len(all_agents_detected),
                    "unique_agents": len(unique_agents),
                    "response_types": list(response_types_found),
                    "trace_events_processed": len(all_trace_events),
                    "agents_by_type": {}
                }
                
                # Group agents by type
                for agent in all_agents_detected:
                    agent_type = agent["type"]
                    if agent_type not in summary_data["agents_by_type"]:
                        summary_data["agents_by_type"][agent_type] = 0
                    summary_data["agents_by_type"][agent_type] += 1
                
                LLMObs.annotate(
                    input_data=f"Analyzing {len(all_agents_detected)} detected agents",
                    output_data=f"Complete separation: {len(unique_agents)} unique agents with {len(response_types_found)} response types",
                    metadata=summary_data,
                    tags={
                        "step_type": "summary",
                        "separation_complete": "true",
                        "unique_agents": str(len(unique_agents))
                    }
                )
            
            print(f"✅ Complete separation: {len(all_agents_detected)} agents, {len(response_types_found)} response types")
            print(f"📊 Response types found: {', '.join(response_types_found)}")
            
            # Annotate main workflow
            LLMObs.annotate(
                input_data=question,
                output_data=output,
                metadata={
                    "expected_answer": expected,
                    "session_id": session_id,
                    "complete_separation_results": {
                        "total_agents": len(all_agents_detected),
                        "unique_agents": len(unique_agents),
                        "response_types": list(response_types_found),
                        "trace_events": len(all_trace_events),
                        "agents_by_type": summary_data["agents_by_type"]
                    }
                },
                tags={
                    "environment": "development",
                    "language": "hebrew",
                    "service": "insurance-agent",
                    "complete_separation": "enabled",
                    "total_agents": str(len(all_agents_detected))
                }
            )
            
            return output.strip() if output else None
            
        except Exception as e:
            logging.error(f"Error in complete separation workflow: {e}")
            print(f"❌ Error occurred: {e}")
            
            LLMObs.annotate(
                input_data=question,
                output_data=f"Error: {str(e)}",
                metadata={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "separation_failed": True
                },
                tags={
                    "error": "true",
                    "separation": "failed"
                }
            )
            
            return None

def main():
    """Main function with complete agent separation"""
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
    print("🎯 COMPLETE AGENT SEPARATION - All Response Types Captured")
    print(f"📍 Application: {ML_APP_NAME}")
    print(f"🌍 Datadog Site: {DATADOG_SITE}")
    print(f"🤖 Agent ID: {AGENT_ID}")
    print("📊 Captures: SQL queries, JSON, API calls, text responses, etc.")
    print("🔍 Detection: Automatic with complete separation")
    print("=" * 80)
    
    successful_calls = 0
    total_calls = len(questions)
    
    for i, item in enumerate(questions, 1):
        print(f"\n{'='*20} Test {i}/{total_calls} {'='*20}")
        print(f"❓ Question: {item['question']}")
        print(f"📋 Expected: {item['expected']}")
        print("-" * 60)
        
        start_time = time.time()
        result = ask_agent_with_complete_separation(item["question"], item["expected"])
        end_time = time.time()
        
        duration = end_time - start_time
        
        if result:
            successful_calls += 1
            print(f"✅ SUCCESS - Duration: {duration:.2f}s")
            print(f"📤 Response: {result[:200]}{'...' if len(result) > 200 else ''}")
        else:
            print(f"❌ FAILED - Duration: {duration:.2f}s")
            print("📤 No response received")
        
        print(f"📊 Expected: {item['expected']}")
        
        # Delay between calls
        if i < total_calls:
            time.sleep(3)
    
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print(f"✅ Successful calls: {successful_calls}/{total_calls}")
    print(f"❌ Failed calls: {total_calls - successful_calls}/{total_calls}")
    print(f"📈 Success rate: {(successful_calls/total_calls)*100:.1f}%")
    print("=" * 80)
    
    # Force flush to ensure all data is sent to Datadog
    print("\n🔄 Flushing LLM Observability data to Datadog...")
    try:
        LLMObs.flush()
        print("✅ Data successfully flushed to Datadog!")
        print(f"🔗 Check your traces at: https://app.{DATADOG_SITE}/llm/")
        print("🎯 You should now see COMPLETE SEPARATION:")
        print("   • Each agent in its own span with unique ID")
        print("   • SQL queries clearly separated from text responses")
        print("   • JSON/API responses properly categorized")
        print("   • Knowledge base lookups as retrieval spans")
        print("   • Code interpreter outputs as tool spans")
        print("   • Final responses as LLM spans")
        print("   • Clear hierarchy: Supervisor → Sub-agents → Tools")
    except Exception as flush_error:
        print(f"❌ Flush error: {flush_error}")
    
    print("\n🎉 Complete agent separation tracing completed!")

if __name__ == "__main__":
    main()