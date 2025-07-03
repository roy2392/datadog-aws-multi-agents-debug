import json

import requests

import os

import sys

import random

import time

from datetime import datetime

import boto3

from config import (

    kb_agent_id, kb_agent_alias_id, aws_region_bedrock_agent,

    eval_questions_file, results_directory, results_file_prefix,

    lambada_id,kb_lambada_agent_id, kb_lambada_agent_alias_id

)

 

agents_runtime_client = boto3.client(

    "bedrock-agent-runtime",

    region_name=aws_region_bedrock_agent,

    verify=False,

    aws_access_key_id=crad['aws_access_key_id'],

    aws_secret_access_key=crad['aws_secret_access_key'],

    aws_session_token=crad['aws_session_token']

)

 

lambda_client = boto3.client(

    "lambda",

    region_name=aws_region_bedrock_agent

)

 

def process_agent_response_with_trace(question, agent_id, agent_alias_id, session_id,crad = None):

    """Process agent response and collect trace events."""

    completion = ""

    trace_events = []

   

    try:

        # Call the API with trace enabled

        if crad is not None:

            response = agents_runtime_client.invoke_agent(

                inputText=question,

                agentId=agent_id,

                agentAliasId=agent_alias_id,

                sessionId=session_id,

                enableTrace=True

 

            )

        else:

            response = agents_runtime_client.invoke_agent(

                inputText=question,

                agentId=agent_id,

                agentAliasId=agent_alias_id,

                sessionId=session_id,

                enableTrace=True

            )

       

        event_stream = response['completion']

       

        # Process the event stream

        for event in event_stream:

            if 'chunk' in event:

                chunk = event['chunk']

                completion += chunk['bytes'].decode('utf-8')

            elif 'trace' in event:

                trace_events.append(event['trace'])

            else:

                safe_print(f"Unexpected event: {event}")

       

        return completion, trace_events

       

    except Exception as e:

        safe_print(f"Error processing agent response: {str(e)}")

        return "", []

 

def extract_timing_from_trace(trace_events):

    """Extract timing information from agent trace events."""

    timing_info = {

        'thinking_time': 0,

        'lambda_time': 0,

        'pre_lambda_time': 0,

        'post_lambda_time': 0,

        'total_trace_time': 0

    }

   

    try:

        timestamps = []

        model_start_time = None

        model_end_time = None

        action_start_time = None

        action_end_time = None

       

        for trace_event in trace_events:

            # Extract timestamp from trace event if available

            event_timestamp = None

           

            # Check different possible locations for timestamp

            if isinstance(trace_event, dict):

                if 'timestamp' in trace_event:

                    event_timestamp = trace_event['timestamp']

                elif 'trace' in trace_event and isinstance(trace_event['trace'], dict):

                    trace_data = trace_event['trace']

                    if 'timestamp' in trace_data:

                        event_timestamp = trace_data['timestamp']

                    elif 'orchestrationTrace' in trace_data:

                        orchestration = trace_data['orchestrationTrace']

                        if 'timestamp' in orchestration:

                            event_timestamp = orchestration['timestamp']

                       

                        # Track model invocation timing

                        if 'modelInvocationInput' in orchestration:

                            if model_start_time is None:

                                model_start_time = event_timestamp

                        elif 'modelInvocationOutput' in orchestration:

                            model_end_time = event_timestamp

                       

                        # Track action group invocation timing

                        elif 'invocationInput' in orchestration:

                            if 'actionGroupInvocationInput' in orchestration['invocationInput']:

                                action_start_time = event_timestamp

                        elif 'observation' in orchestration:

                            if 'actionGroupInvocationOutput' in orchestration['observation']:

                                action_end_time = event_timestamp

           

            if event_timestamp:

                timestamps.append(event_timestamp)

       

        # Calculate timing differences if we have timestamps

        if timestamps:

            timestamps.sort()

            timing_info['total_trace_time'] = (timestamps[-1] - timestamps[0]) / 1000.0 if len(timestamps) > 1 else 0

       

        if model_start_time and model_end_time:

            timing_info['thinking_time'] = (model_end_time - model_start_time) / 1000.0

       

        if action_start_time and action_end_time:

            timing_info['lambda_time'] = (action_end_time - action_start_time) / 1000.0

       

        if timestamps and len(timestamps) >= 2:

            if action_start_time:

                timing_info['pre_lambda_time'] = (action_start_time - timestamps[0]) / 1000.0

            if action_end_time and timestamps:

                timing_info['post_lambda_time'] = (timestamps[-1] - action_end_time) / 1000.0

       

        safe_print(f"Extracted timing: total_trace={timing_info['total_trace_time']:.3f}s, thinking={timing_info['thinking_time']:.3f}s, lambda={timing_info['lambda_time']:.3f}s")

       

    except Exception as e:

        safe_print(f"Error extracting timing from trace: {str(e)}")

   

    return timing_info

 

def extract_chunks_from_trace(trace_events, use_lambda_agent=True):

    """Extract chunks from trace events based on agent type."""

    chunks_text = ""

   

    try:

        for trace_event in trace_events:

            if 'trace' in trace_event:

                trace = trace_event['trace']

                if 'orchestrationTrace' in trace:

                    orchestration = trace['orchestrationTrace']

                   

                    if use_lambda_agent:

                        # For lambda agent - look for actionGroupInvocationOutput

                        if 'observation' in orchestration:

                            observation = orchestration['observation']

                            if 'actionGroupInvocationOutput' in observation:

                                action_output = observation['actionGroupInvocationOutput']

                                if 'text' in action_output:

                                    chunks_text = action_output['text']

                                    # Remove quotes if it's a JSON string

                                    if chunks_text.startswith('"') and chunks_text.endswith('"'):

                                        chunks_text = json.loads(chunks_text)

                                    # break

                    else:

                        # For KB agent - look for knowledgeBaseLookupOutput

                        if 'observation' in orchestration:

                            observation = orchestration['observation']

                            if 'knowledgeBaseLookupOutput' in observation:

                                kb_output = observation['knowledgeBaseLookupOutput']

                                if 'retrievedReferences' in kb_output:

                                    references = kb_output['retrievedReferences']

                                    # Combine all reference texts

                                    reference_texts = []

                                    for ref in references:

                                        if 'content' in ref and 'text' in ref['content']:

                                            reference_texts.append(ref['content']['text'])

                                    chunks_text = '\n\n'.join(reference_texts)

                                    # break

       

        return chunks_text

       

    except Exception as e:

        safe_print(f"Error extracting chunks from trace: {str(e)}")

        return ""

 

def run_query(agent_id, agent_alias_id, agents_runtime_client, suffix='', use_lambda_agent=True):

    """Test the agent with each question and save the results."""

    # Generate random session ID between 100000-999999

    session_id = str(random.randint(107000, 599999))

   

    # Read questions from JSON

    with open(eval_questions_file, 'r', encoding='utf-8') as file:

        questions = json.load(file)

   

    results = []

   

    # Process each question

    for i, question_data in enumerate(questions):

        try:

            # Use safe_print to avoid encoding issues

            safe_print(f"Testing question {i+1}/{len(questions)}: {question_data['question']}")

           

            # Start timing the total invocation

            start_time = time.time()

           

            # Process agent response with trace

            completion, trace_events = process_agent_response_with_trace(

                question_data['question'], agent_id, agent_alias_id, session_id

            )

           

            # End timing the total invocation

            end_time = time.time()

            total_running_time = end_time - start_time

           

            # Extract chunks directly from trace events

            chunks = extract_chunks_from_trace(trace_events, use_lambda_agent)

           

            # Extract timing information from trace events

            timing_info = extract_timing_from_trace(trace_events)

            timing_info['total_running_time'] = total_running_time

           

            safe_print(f"Extracted chunks from trace (lambda_agent={use_lambda_agent})")

           

            # Calculate chunk metrics

            chunks_length = len(chunks) if chunks else 0

            chunks_per_second = chunks_length / total_running_time if total_running_time > 0 else 0

           

            result = {

                'question': question_data['question'],

                'baseTruth': question_data['baseTruth'],

                'answer': completion.strip(),

                'chunks': chunks,

                'timing': timing_info,

                'chunks_metrics': {

                    'chunks_length': chunks_length,

                    'chunks_per_second': round(chunks_per_second, 2)

                }

            }

           

            results.append(result)

            # break

        except Exception as e:

            safe_print(f"Error processing question {i+1}: {str(e)}")

            # Add failed result to maintain question order

            result = {

                'question': question_data['question'],

                'baseTruth': question_data['baseTruth'],

                'answer': f"Error: {str(e)}",

                'chunks': "",

                'timing': {'total_running_time': 0},

                'chunks_metrics': {

                    'chunks_length': 0,

                    'chunks_per_second': 0

                }

            }

            results.append(result)

   

    # Create directory if it doesn't exist

    os.makedirs(results_directory, exist_ok=True)

   

    # Save results to JSON

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    file_name = f'{results_directory}/{results_file_prefix}{timestamp}{suffix}.json'

    with open(file_name, 'w', encoding='utf-8') as file:

        json.dump(results, file, ensure_ascii=False, indent=2)

   

    safe_print(f"Completed testing {len(results)} questions")

    safe_print(f"Results saved to: {file_name}")

    return file_name

 

def safe_print(text):

    """Print text safely, avoiding encoding issues."""

    try:

        print(text)

    except (UnicodeEncodeError, ValueError):

        # Fallback for encoding issues

        try:

            print(text.encode('ascii', 'ignore').decode('ascii'))

        except:

            print("Processing item...")

 

colabs = set()

for tr in trace:

    if 'collaboratorName' in tr:

        colabs.add(tr['collaboratorName'])

 

print(colabs)

 

for tr in trace:

    inner_trace = tr['trace']

    if 'orchestrationTrace' in inner_trace:

        if 'observation' in inner_trace['orchestrationTrace']:

            if 'actionGroupInvocationOutput' in inner_trace['orchestrationTrace']['observation']:

                if 'text' in inner_trace['orchestrationTrace']['observation']['actionGroupInvocationOutput']:

                    lambada_output = inner_trace['orchestrationTrace']['observation']['actionGroupInvocationOutput']['text']

                    if 'query' in lambada_output:

                        sql_query = lambada_output[lambada_output.find('query')+6:-2]

                   

print(sql_query)      