#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bedrock multi-question evaluator with exhaustive Datadog LLMObs spans.

• Plain-string I/O so Datadog cards show only text.
• Spans for every Bedrock trace element: preprocess ▸ rationale ▸
  (SQL | KB | collaborator | code-interp) + their outputs ▸
  postprocess ▸ guardrail ▸ failure.
"""

import os, time, json, re, difflib, logging, random
from datetime import datetime
from typing import Dict, List, Any


import boto3, dotenv
dotenv.load_dotenv()

# ── disable APM – we only emit LLMObs spans
os.environ["DD_TRACE_ENABLED"]   = "false"
os.environ["DD_AGENT_HOST"]      = ""
os.environ["DD_TRACE_AGENT_URL"] = ""

from ddtrace.llmobs import LLMObs        # noqa: E402

# ── config ──────────────────────────────────────────────────────────────
REGION   = os.getenv("BEDROCK_REGION",  "eu-west-1")
AGENT_ID = os.getenv("AGENT_ID",        "")
ALIAS_ID = os.getenv("AGENT_ALIAS_ID",  "")

DD_KEY   = os.getenv("DATADOG_API_KEY", "")
DD_SITE  = os.getenv("DATADOG_SITE",    "datadoghq.eu")
APP_NAME = os.getenv("ML_APP_NAME",     "migdal-zone-eval")

# Load questions from eval.json by default
QUESTIONS_FILE = os.environ.get("EVAL_QUESTIONS_FILE", "eval.json")

OUT_DIR   = os.getenv("RESULTS_DIR",         "evaluation_results")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

LLMObs.enable(ml_app=APP_NAME, api_key=DD_KEY,
              site=DD_SITE, agentless_enabled=True)

client = boto3.client("bedrock-agent-runtime", region_name=REGION)
# ------------------------------------------------------------------------------
#  Tiny helper to print without crashing on odd Unicode
# ------------------------------------------------------------------------------
def safe_p(msg):
    try:
        print(msg)
    except Exception:
        print(msg.encode("ascii", "ignore").decode("ascii"))

# ── helpers ─────────────────────────────────────────────────────────────
def sim(a, b):                    # similarity %
    if not a or not b: return 0
    a, b = re.sub(r"\s+"," ",a.lower()), re.sub(r"\s+"," ",b.lower())
    return round(difflib.SequenceMatcher(None,a.strip(),b.strip()).ratio()*100,2)

def grade(s): return "excellent" if s>=80 else "good" if s>=60 else "fair" if s>=40 else "poor"

def mk(kind, name, sid):
    return dict(agent=LLMObs.agent, llm=LLMObs.llm,
                tool=LLMObs.tool, retrieval=LLMObs.retrieval,
                task=LLMObs.task)[kind](name=name, session_id=sid)

# ── full Bedrock trace → spans ──────────────────────────────────────────
def process_trace_event(trace_event, session_id):
    try:
        agent_id = trace_event.get("agentId", "unknown")
        agent_name = trace_event.get("agentName", "unknown")
        collaborator_name = trace_event.get("collaboratorName", "")
        trace_data = trace_event.get("trace", {})
        
        # PreProcessingTrace
        if "preProcessingTrace" in trace_data:
            preprocessing = trace_data["preProcessingTrace"]
            model_input = preprocessing.get("modelInvocationInput", {})
            model_output = preprocessing.get("modelInvocationOutput", {})
            prompt_text = model_input.get("text", "")
            rationale = model_output.get("parsedResponse", {}).get("rationale", "")
            is_valid = model_output.get("parsedResponse", {}).get("isValid", True)
            with LLMObs.task(name="preprocessing-validation", session_id=session_id):
                print(f"[DD SPAN] preprocessing-validation, session_id={session_id}")
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

        # OrchestrationTrace
        if "orchestrationTrace" in trace_data:
            orchestration = trace_data["orchestrationTrace"]
            # Rationale
            if "rationale" in orchestration:
                rationale = orchestration["rationale"]
                rationale_text = rationale.get("text", "")
                with LLMObs.agent(name=f"reasoning-agent-{agent_name}", session_id=session_id):
                    print(f"[DD SPAN] reasoning-agent-{agent_name}, session_id={session_id}")
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
            # InvocationInput
            if "invocationInput" in orchestration:
                invocation_input = orchestration["invocationInput"]
                invocation_type = invocation_input.get("invocationType", "")
                if invocation_type == "ACTION_GROUP":
                    action_input = invocation_input.get("actionGroupInvocationInput", {})
                    action_name = action_input.get("actionGroupName", "")
                    api_path = action_input.get("apiPath", "")
                    verb = action_input.get("verb", "")
                    parameters = action_input.get("parameters", [])
                    params_str = json.dumps(parameters, indent=2) if parameters else "No parameters"
                    with LLMObs.tool(name=f"action-{action_name}", session_id=session_id):
                        print(f"[DD SPAN] action-{action_name}, session_id={session_id}")
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
                elif invocation_type == "KNOWLEDGE_BASE":
                    kb_input = invocation_input.get("knowledgeBaseLookupInput", {})
                    kb_id = kb_input.get("knowledgeBaseId", "")
                    query_text = kb_input.get("text", "")
                    with LLMObs.retrieval(name="knowledge-base-query", session_id=session_id):
                        print(f"[DD SPAN] knowledge-base-query, session_id={session_id}")
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
                elif invocation_type == "AGENT_COLLABORATOR":
                    collab_input = invocation_input.get("agentCollaboratorInvocationInput", {})
                    collab_name = collab_input.get("agentCollaboratorName", "")
                    input_text = collab_input.get("input", {}).get("text", "")
                    with LLMObs.agent(name=f"collaborator-{collab_name}", session_id=session_id):
                        print(f"[DD SPAN] collaborator-{collab_name}, session_id={session_id}")
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
                                "collaborator": collab_name,
                                "span_type": "agent"
                            }
                        )
            # Observation
            if "observation" in orchestration:
                observation = orchestration["observation"]
                obs_type = observation.get("type", "")
                if obs_type == "ACTION_GROUP":
                    action_output = observation.get("actionGroupInvocationOutput", {})
                    response_text = action_output.get("text", "")
                    try:
                        if response_text.startswith('"') and response_text.endswith('"'):
                            response_text = json.loads(response_text)
                        parsed_response = json.loads(response_text) if isinstance(response_text, str) and response_text.strip().startswith('{') else response_text
                        formatted_response = json.dumps(parsed_response, indent=2) if isinstance(parsed_response, dict) else str(response_text)
                    except:
                        formatted_response = str(response_text)
                    with LLMObs.tool(name="action-group-response", session_id=session_id):
                        print(f"[DD SPAN] action-group-response, session_id={session_id}")
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
                elif obs_type == "AGENT_COLLABORATOR":
                    collab_output = observation.get("agentCollaboratorInvocationOutput", {})
                    collab_name = collab_output.get("agentCollaboratorName", "")
                    output_text = collab_output.get("output", {}).get("text", "")
                    with LLMObs.agent(name=f"collaborator-response-{collab_name}", session_id=session_id):
                        print(f"[DD SPAN] collaborator-response-{collab_name}, session_id={session_id}")
                        LLMObs.annotate(
                            input_data=f"Response from {collab_name}",
                            output_data=output_text,
                            metadata={
                                "collaborator_name": collab_name,
                                "response_length": len(output_text)
                            },
                            tags={
                                "trace_type": "collaborator_output",
                                "collaborator": collab_name,
                                "span_type": "agent"
                            }
                        )
                elif obs_type == "FINISH":
                    final_response = observation.get("finalResponse", {})
                    final_text = final_response.get("text", "")
                    with LLMObs.llm(name="final-response-generator", model_name="bedrock-agent", model_provider="aws", session_id=session_id):
                        print(f"[DD SPAN] final-response-generator, session_id={session_id}")
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
        # GuardrailTrace
        if "guardrailTrace" in trace_data:
            guardrail = trace_data["guardrailTrace"]
            action = guardrail.get("action", "")
            with LLMObs.task(name="guardrail-assessment", session_id=session_id):
                print(f"[DD SPAN] guardrail-assessment, session_id={session_id}")
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
    except Exception as e:
        safe_p(f"[TRACE-PARSE ERROR] {e}")

# ── evaluate one question ──────────────────────────────────────────────
def evaluate(qd: Dict[str,Any], idx:int, total:int) -> Dict[str,Any]:
    q, expect, qtype = qd["question"], qd["expected_answer"], qd.get("type","rag")
    sid = f"eval_{random.randint(100000,999999)}_{idx}"
    answer = ""
    safe_p(f"\n▶ {idx}/{total} {q[:70]}…")

    with mk("task","workflow",sid):  # root workflow span
        with mk("agent",f"bedrock:{AGENT_ID}",sid):
            resp = client.invoke_agent(agentId=AGENT_ID,
                                       agentAliasId=ALIAS_ID,
                                       sessionId=sid,
                                       inputText=q,
                                       enableTrace=True)
            for ev in resp["completion"]:
                print("DEBUG TRACE EVENT:", json.dumps(ev, ensure_ascii=False, indent=2, default=str))
                if "chunk" in ev:
                    answer += ev["chunk"]["bytes"].decode("utf-8")
                elif "trace" in ev:
                    process_trace_event(ev, sid)

            LLMObs.annotate(input_data=q, output_data=answer)

        # attach prompt/answer to workflow span
        LLMObs.annotate(input_data=q, output_data=answer)
        sc = sim(answer, expect)
        LLMObs.annotate(input_data="eval", output_data=f"{sc:.1f}% {grade(sc)}",
                        metadata={"similarity":sc,"quality":grade(sc)})

    return dict(question=q, expected=expect, answer=answer,                similarity=sc, quality=grade(sc))

# ── driver ─────────────────────────────────────────────────────────────
def load_questions():
    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        return json.load(f)

def main():
    """Main function: run evaluation for all questions in eval.json (or EVAL_QUESTIONS_FILE)"""
    questions = load_questions()
    results = []
    for idx, q in enumerate(questions):
        question = q["question"]
        expected = q["expected_answer"]
        sql = q.get("sql", "")
        qtype = q.get("type", "")
        user_id = q.get("user_id", "")
        session_id = f"bedrock-trace_{idx}_{int(time.time())}"
        output = ""
        trace_count = 0
        final_response_text = None

        print("=" * 80)
        print(f"❓ Question {idx+1}/{len(questions)}: {question}")
        print(f"👤 User ID: {user_id}")
        print(f"📄 Type: {qtype}")
        print(f"📝 SQL: {sql}")
        print("=" * 80)

        with LLMObs.workflow(name="bedrock-agent-workflow", session_id=session_id):
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
                print(f"Processing question: {question}")
                response = client.invoke_agent(
                    agentId=AGENT_ID,
                    agentAliasId=ALIAS_ID,
                    sessionId=session_id,
                    inputText=question,
                    enableTrace=True
                )
                print("🔍 Processing trace events...")
                for event_index, event in enumerate(response.get("completion", [])):
                    if "chunk" in event:
                        chunk = event["chunk"]
                        if "bytes" in chunk:
                            text = chunk["bytes"].decode('utf-8')
                            output += text
                            print(f"📝 Chunk {event_index + 1}: {text[:50]}{'...' if len(text) > 50 else ''}")
                    elif "trace" in event:
                        trace_count += 1
                        print(f"🔍 Processing trace event {trace_count}")
                        trace_data = event["trace"].get("trace", {})
                        orch = trace_data.get("orchestrationTrace", {})
                        if "observation" in orch:
                            obs = orch["observation"]
                            if obs.get("type") == "FINISH" and "finalResponse" in obs:
                                final_response_text = obs["finalResponse"].get("text", None)
                        process_trace_event(event["trace"], session_id)

                output_to_use = final_response_text if final_response_text is not None else output

                LLMObs.annotate(
                    input_data=[{"role": "user", "content": question}],
                    output_data=[{"role": "assistant", "content": output_to_use}],
                    metadata={
                        "total_trace_events": trace_count,
                        "response_length": len(output_to_use),
                        "expected_answer": expected,
                        "agent_id": AGENT_ID,
                        "session_id": session_id
                    },
                    tags={
                        "agent_type": "bedrock_supervisor",
                        "trace_events_count": str(trace_count),
                        "has_output": str(bool(output_to_use))
                    }
                )
                print(f"✅ Processed {trace_count} trace events")
                print(f"📤 Final output length: {len(output_to_use)} chars")

            LLMObs.annotate(
                input_data=question,
                output_data=output_to_use,
                tags={"final_output": "true"}
            )

        print("\n🔄 Flushing LLM Observability data to Datadog...")
        try:
            LLMObs.flush()
            print("✅ Data successfully flushed to Datadog!")
            print(f"🔗 Check your traces at: https://app.{DD_SITE}/llm/")
        except Exception as flush_error:
            print(f"❌ Flush error: {flush_error}")

        print("\n🎉 Bedrock trace capture with content completed!")
        results.append({
            "question": question,
            "expected_answer": expected,
            "output": output_to_use,
            "user_id": user_id,
            "type": qtype,
            "sql": sql,
            "session_id": session_id
        })

    # Optionally, save results to a file
    out_path = os.path.join(OUT_DIR, f"eval_results_{int(time.time())}.json")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nAll results saved to {out_path}")

if __name__ == "__main__":
    main()
