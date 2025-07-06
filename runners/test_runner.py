"""
Test runner module for executing agent test suites.
Handles test execution, result collection, and reporting.
"""

import time
from typing import List, Dict, Any
from orchestrators.agent_orchestrator import AgentOrchestrator
from models.question import Question
from models.test_result import TestResult
from utils.logger import safe_print, get_logger
from config import DatadogConfig

logger = get_logger(__name__)

class TestRunner:
    """Runner for executing agent test suites."""
    
    def __init__(self):
        """Initialize test runner with orchestrator."""
        self.orchestrator = AgentOrchestrator()
        self.results: List[TestResult] = []
    
    def run_test_suite(self, questions: List[Dict[str, Any]], delay_between_tests: int = 3) -> List[TestResult]:
        """
        Run a complete test suite with the given questions.
        
        Args:
            questions: List of question dictionaries
            delay_between_tests: Delay in seconds between tests
            
        Returns:
            List of test results
        """
        self._print_test_suite_header()
        
        total_calls = len(questions)
        successful_calls = 0
        
        for i, question_data in enumerate(questions, 1):
            question = Question.from_dict(question_data)
            result = self._run_single_test(question, i, total_calls)
            
            if result.success:
                successful_calls += 1
            
            self.results.append(result)
            
            # Add delay between tests (except for the last one)
            if i < total_calls:
                time.sleep(delay_between_tests)
        
        self._print_test_suite_summary(successful_calls, total_calls)
        return self.results
    
    def _run_single_test(self, question: Question, test_number: int, total_tests: int) -> TestResult:
        """
        Run a single test with the given question.
        
        Args:
            question: Question to test
            test_number: Current test number
            total_tests: Total number of tests
            
        Returns:
            Test result
        """
        self._print_test_header(question, test_number, total_tests)
        
        start_time = time.time()
        
        try:
            response = self.orchestrator.ask_agent_with_traces(question.question, question.expected)
            end_time = time.time()
            duration = end_time - start_time
            
            success = response is not None
            error_message = None if success else "No response received"
            
            self._print_test_result(success, duration, response)
            
            return TestResult(
                question=question.question,
                response=response,
                expected=question.expected,
                duration=duration,
                success=success,
                error_message=error_message
            )
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            
            logger.error(f"Test failed with exception: {e}")
            self._print_test_result(False, duration, None, str(e))
            
            return TestResult(
                question=question.question,
                response=None,
                expected=question.expected,
                duration=duration,
                success=False,
                error_message=str(e)
            )
    
    def _print_test_suite_header(self):
        """Print test suite header information."""
        agent_info = self.orchestrator.get_agent_info()
        
        print("=" * 80)
        print("🎯 BEDROCK AGENT TRACE CAPTURE - Following AWS Documentation")
        print(f"📍 Application: {DatadogConfig.ML_APP_NAME}")
        print(f"🌍 Datadog Site: {DatadogConfig.SITE}")
        print(f"🤖 Agent ID: {agent_info['agent_id']}")
        print("📊 Captures: All AWS Bedrock trace types with actual content")
        print("🔍 Following: PreProcessing, Orchestration, PostProcessing, Guardrail, Failure")
        print("=" * 80)
    
    def _print_test_header(self, question: Question, test_number: int, total_tests: int):
        """Print header for individual test."""
        print(f"\n{'='*20} Test {test_number}/{total_tests} {'='*20}")
        print(f"❓ Question: {question.question}")
        print(f"📋 Expected: {question.expected}")
        print("-" * 60)
    
    def _print_test_result(self, success: bool, duration: float, response: str, error: str = None):
        """Print result for individual test."""
        if success:
            print(f"✅ SUCCESS - Duration: {duration:.2f}s")
            print(f"📤 Response: {response[:200]}{'...' if len(response) > 200 else ''}")
        else:
            print(f"❌ FAILED - Duration: {duration:.2f}s")
            if error:
                print(f"📤 Error: {error}")
            else:
                print("📤 No response received")
    
    def _print_test_suite_summary(self, successful_calls: int, total_calls: int):
        """Print summary of test suite execution."""
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print(f"✅ Successful calls: {successful_calls}/{total_calls}")
        print(f"❌ Failed calls: {total_calls - successful_calls}/{total_calls}")
        print(f"📈 Success rate: {(successful_calls/total_calls)*100:.1f}%")
        print("=" * 80)
    
    def flush_data_to_datadog(self) -> bool:
        """Flush all data to Datadog and print results."""
        print("\n🔄 Flushing LLM Observability data to Datadog...")
        
        success = self.orchestrator.flush_data()
        
        if success:
            print("✅ Data successfully flushed to Datadog!")
            print(f"🔗 Check your traces at: https://app.{DatadogConfig.SITE}/llm/")
            print("🎯 You should now see:")
            print("   • Actual input/output content in each span")
            print("   • Agent reasoning (rationale) with full text")
            print("   • Action group calls with parameters & responses")
            print("   • Knowledge base queries with retrieved documents")
            print("   • Final responses with complete content")
            print("   • All trace types following AWS Bedrock structure")
        else:
            print("❌ Failed to flush data to Datadog")
        
        print("\n🎉 Bedrock trace capture with content completed!")
        return success
    
    def get_results_summary(self) -> Dict[str, Any]:
        """Get a summary of test results."""
        if not self.results:
            return {"error": "No results available"}
        
        total_tests = len(self.results)
        successful_tests = sum(1 for result in self.results if result.success)
        failed_tests = total_tests - successful_tests
        avg_duration = sum(result.duration for result in self.results) / total_tests
        
        return {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": (successful_tests / total_tests) * 100,
            "average_duration": avg_duration,
            "results": [result.to_dict() for result in self.results]
        } 