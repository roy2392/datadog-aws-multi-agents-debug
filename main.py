"""
Main entry point for Datadog Multi-Agent Debugging project.
Refactored to follow software engineering best practices for AI projects.
"""

import json
import os
from runners.test_runner import TestRunner
from utils.logger import setup_logging

def load_evaluation_questions(file_path: str = "data/evaluation_questions.json"):
    """
    Load evaluation questions from JSON file.
    
    Args:
        file_path: Path to the JSON file containing questions
        
    Returns:
        List of question dictionaries
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        print(f"✅ Loaded {len(questions)} questions from {file_path}")
        return questions
    except FileNotFoundError:
        print(f"❌ Question file not found: {file_path}")
        return get_default_questions()
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {file_path}")
        return get_default_questions()

def get_default_questions():
    """Get default test questions if no file is available."""
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

def get_available_question_files():
    """Get list of available question files in the data directory."""
    data_dir = "data"
    if not os.path.exists(data_dir):
        return []
    
    question_files = []
    for file in os.listdir(data_dir):
        if file.endswith('.json') and 'question' in file.lower():
            question_files.append(os.path.join(data_dir, file))
    
    return question_files

def main():
    """Main function with refactored structure."""
    # Setup logging
    setup_logging()
    
    # Show available question files
    available_files = get_available_question_files()
    if available_files:
        print("📁 Available question files:")
        for i, file_path in enumerate(available_files, 1):
            print(f"  {i}. {file_path}")
        print()
    
    # Load evaluation questions (default to the main evaluation file)
    questions = load_evaluation_questions()
    
    if not questions:
        print("❌ No questions available. Exiting.")
        return
    
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