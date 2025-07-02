# Datadog Multi-Agent Debugging

This project demonstrates complete agent separation and observability for LLM-based agents using Datadog and AWS Bedrock.

## Features
- Complete separation of agent spans (reasoning, knowledge base, tools, code, final response)
- Automatic detection of response types (SQL, JSON, API, text, etc.)
- Rich metadata and tagging for Datadog LLM Observability
- Bedrock agent orchestration and tracing

## Requirements
- Python 3.8+
- AWS credentials with access to Bedrock
- Datadog account and API key

## Setup
1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd datadog-multi-agent-debuging
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example environment file and fill in your values:
   ```bash
   cp .env-example .env
   ```
4. Set up your AWS credentials (via environment variables or AWS CLI config).

## Environment Variables
See `.env-example` for all required variables. Key variables:
- `BEDROCK_REGION`: AWS region for Bedrock (e.g., eu-west-1)
- `AGENT_ID`: Your Bedrock agent ID
- `AGENT_ALIAS_ID`: Your Bedrock agent alias ID
- `DATADOG_API_KEY`: Your Datadog API key
- `DATADOG_SITE`: Datadog site (e.g., datadoghq.eu)
- `ML_APP_NAME`: Application name for Datadog LLM Observability

## Usage
Run the main script:
```bash
python dd_traces.py
```

## Datadog LLM Observability
- All agent spans and traces are sent to Datadog for analysis.
- Check your traces at: `https://app.<DATADOG_SITE>/llm/`

## Notes
- Ensure your Datadog API key and AWS credentials are valid.
- The script disables Datadog APM by default and uses agentless LLM Observability.

---
MIT License 