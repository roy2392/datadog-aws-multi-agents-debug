# Datadog Multi-Agent Debugging

A comprehensive Python project for debugging and monitoring AWS Bedrock agents using Datadog LLM Observability. This project follows software engineering best practices for AI projects with a modular, maintainable architecture.

## 🏗️ Project Structure

```
datadog-multi-agent-debuging/
├── config.py                 # Centralized configuration management
├── main.py                   # Clean main entry point
├── migrate.py                # Migration helper script
├── requirements.txt          # Project dependencies
├── .env-example             # Environment variables template
├── .gitignore               # Git ignore rules
│
├── models/                  # Data models
│   ├── __init__.py
│   ├── question.py          # Question model
│   └── test_result.py       # Test result model
│
├── services/                # External service integrations
│   ├── __init__.py
│   ├── bedrock_service.py   # AWS Bedrock client
│   └── datadog_service.py   # Datadog LLM Observability
│
├── processors/              # Data processing modules
│   ├── __init__.py
│   └── trace_processor.py   # Bedrock trace event processing
│
├── orchestrators/           # Workflow orchestration
│   ├── __init__.py
│   └── agent_orchestrator.py # Main workflow coordination
│
├── runners/                 # Test execution
│   ├── __init__.py
│   └── test_runner.py       # Test suite execution
│
└── utils/                   # Utility modules
    ├── __init__.py
    ├── logger.py            # Logging utilities
    └── text_processing.py   # Text processing utilities
```

## 🎯 Features

- **Complete Bedrock Trace Capture**: Captures all AWS Bedrock trace types with actual content
- **Datadog LLM Observability**: Full integration with Datadog for monitoring and debugging
- **Modular Architecture**: Clean separation of concerns with focused modules
- **Type Safety**: Comprehensive type hints and data validation
- **Error Handling**: Robust error handling and graceful degradation
- **Configuration Management**: Environment-based configuration
- **Test Suite**: Automated test execution with detailed reporting
- **Migration Tools**: Easy migration from legacy code

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd datadog-multi-agent-debuging
```

### 2. Setup Environment
```bash
# Copy environment template
cp .env-example .env

# Edit .env with your credentials
nano .env
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python main.py
```

## 📋 Configuration

### Environment Variables
```bash
# AWS Bedrock Configuration
BEDROCK_REGION=eu-west-1
AGENT_ID=your-agent-id
AGENT_ALIAS_ID=your-agent-alias-id

# Datadog Configuration
DATADOG_API_KEY=your-datadog-api-key
DATADOG_SITE=datadoghq.eu
ML_APP_NAME=migdal-zone

# Application Configuration
LOG_LEVEL=INFO
SESSION_TIMEOUT=30
MAX_RETRIES=3
CHUNK_SIZE=100
```

## 🔧 Usage

### Basic Usage
```python
from runners.test_runner import TestRunner

# Create test runner
runner = TestRunner()

# Define test questions
questions = [
    {
        "question": "כמה משימות יש לי?",
        "expected": "Number of tasks"
    }
]

# Run tests
results = runner.run_test_suite(questions)

# Flush to Datadog
runner.flush_data_to_datadog()
```

### Custom Questions
```python
from models.question import Question

# Create custom question
question = Question(
    question="What is the weather like?",
    expected="Weather information",
    language="english"
)

# Use in test suite
questions = [question.to_dict()]
```

## 🔍 Monitoring

### Datadog Integration
The project automatically sends trace data to Datadog LLM Observability:

- **Workflows**: Complete agent interaction flows
- **Agents**: Individual agent reasoning and responses
- **Tools**: Action group invocations
- **Retrievals**: Knowledge base queries
- **Tasks**: Preprocessing, postprocessing, guardrails

### Trace Types Captured
- **PreProcessingTrace**: Input validation and preprocessing
- **OrchestrationTrace**: Agent reasoning and decision making
- **PostProcessingTrace**: Response formatting and validation
- **GuardrailTrace**: Safety and compliance checks
- **FailureTrace**: Error handling and debugging

## 🧪 Testing

### Running Tests
```python
from runners.test_runner import TestRunner

runner = TestRunner()

# Run with custom delay
results = runner.run_test_suite(questions, delay_between_tests=5)

# Get results summary
summary = runner.get_results_summary()
print(f"Success rate: {summary['success_rate']:.1f}%")
```

### Test Results
Each test result includes:
- Question asked
- Agent response
- Expected output
- Duration
- Success status
- Error message (if any)
- Timestamp

## 🔄 Migration from Legacy Code

If you're migrating from the old `dd_traces.py` structure:

```bash
# Run migration tool
python migrate.py

# Review generated files
cat main_migrated.py

# Run migrated code
python main_migrated.py
```

## 🛠️ Development

### Adding New Features

1. **New Service**: Add to `services/` directory
2. **New Processor**: Add to `processors/` directory
3. **New Model**: Add to `models/` directory
4. **New Utility**: Add to `utils/` directory

### Code Style
- Follow PEP 8
- Use type hints
- Add docstrings
- Keep functions small and focused

### Testing
- Unit tests for individual components
- Integration tests for workflows
- End-to-end tests for complete flows

## 📊 Performance

### Optimization Tips
- Use connection pooling for AWS services
- Implement retry logic with exponential backoff
- Cache frequently used data
- Monitor memory usage for large responses

### Monitoring
- Track response times
- Monitor error rates
- Watch Datadog metrics
- Set up alerts for failures

## 🔒 Security

### Best Practices
- Use environment variables for secrets
- Implement proper error handling
- Validate all inputs
- Log security events
- Use least privilege access

### AWS Permissions
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeAgent",
                "bedrock:InvokeModel"
            ],
            "Resource": "*"
        }
    ]
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Update documentation
6. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the documentation
2. Review existing issues
3. Create a new issue with details
4. Contact the development team

## 📈 Roadmap

- [ ] Add unit tests
- [ ] Implement caching layer
- [ ] Add more trace processors
- [ ] Create web dashboard
- [ ] Add performance monitoring
- [ ] Support for multiple agents
- [ ] Real-time monitoring
- [ ] Alert system integration 