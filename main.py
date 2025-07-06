"""
Main entry point for Datadog Multi-Agent Debugging project.
Refactored to follow software engineering best practices for AI projects.
"""

from runners.test_runner import TestRunner
from utils.logger import setup_logging

def get_default_questions():
    """Get default test questions."""
    return [
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

def main():
    """Main function with refactored structure."""
    # Setup logging
    setup_logging()
    
    # Get test questions
    questions = get_default_questions()
    
    # Create and run test suite
    runner = TestRunner()
    results = runner.run_test_suite(questions, delay_between_tests=3)
    
    # Flush data to Datadog
    runner.flush_data_to_datadog()
    
    # Print final summary
    summary = runner.get_results_summary()
    print(f"\n📋 Final Summary: {summary['successful_tests']}/{summary['total_tests']} tests passed")

if __name__ == "__main__":
    main() 