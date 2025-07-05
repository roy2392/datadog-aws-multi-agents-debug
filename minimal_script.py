from ddtrace.llmobs import LLMObs
import os 
import dotenv

dotenv.load_dotenv()

LLMObs.enable(
    ml_app=os.environ.get("ML_APP_NAME"),
    api_key=os.environ.get("DATADOG_API_KEY"),
    site="datadoghq.eu",
    agentless_enabled=True,
)

with LLMObs.agent(name="debug-agent-span", session_id="debug-session"):
    LLMObs.annotate(
        input_data="DEBUG INPUT",
        output_data="DEBUG OUTPUT"
    )

LLMObs.flush()