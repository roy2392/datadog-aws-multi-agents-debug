"""
Evaluation runner script for Datadog Multi-Agent Debugging project.
Allows running different question sets for evaluation purposes.
"""

import json
import os
import sys
from runners.test_runner import TestRunner
from utils.logger import setup_logging

def load_evaluation_questions(file_path: str):
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
        return None
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {file_path}")
        return None

def get_available_question_files():
    """Get list of available question files in the data directory."""
    data_dir = "data"
    if not os.path.exists(data_dir):
        return []
    
    question_files = []
    for file in os.listdir(data_dir):
        if file.endswith('.json') and 'question' in file.lower():
            question_files.append(os.path.join(data_dir, file))
    
    return sorted(question_files)

def show_available_files():
    """Show available question files with numbers."""
    available_files = get_available_question_files()
    
    if not available_files:
        print("❌ No question files found in data/ directory")
        return None
    
    print("📁 Available question files:")
    for i, file_path in enumerate(available_files, 1):
        # Try to get question count
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                questions = json.load(f)
                count = len(questions)
        except:
            count = "unknown"
        
        print(f"  {i}. {file_path} ({count} questions)")
    
    return available_files

def run_evaluation(file_path: str, delay_between_tests: int = 3):
    """
    Run evaluation with the specified question file.
    
    Args:
        file_path: Path to the question file
        delay_between_tests: Delay between tests in seconds
    """
    print(f"\n🎯 Running evaluation with: {file_path}")
    print("=" * 60)
    
    # Load questions
    questions = load_evaluation_questions(file_path)
    if not questions:
        print("❌ Failed to load questions. Exiting.")
        return False
    
    # Create and run test suite
    runner = TestRunner()
    results = runner.run_test_suite(questions, delay_between_tests=delay_between_tests)
    
    # Flush data to Datadog
    runner.flush_data_to_datadog()
    
    # Print final summary
    summary = runner.get_results_summary()
    print(f"\n📋 Final Summary: {summary['successful_tests']}/{summary['total_tests']} tests passed")
    
    return True

def interactive_mode():
    """Run in interactive mode to select question file."""
    available_files = show_available_files()
    if not available_files:
        return False
    
    print("\nSelect a question file to run:")
    print("Enter the number (or 'q' to quit):")
    
    while True:
        try:
            choice = input("> ").strip()
            
            if choice.lower() == 'q':
                print("👋 Goodbye!")
                return False
            
            file_index = int(choice) - 1
            if 0 <= file_index < len(available_files):
                selected_file = available_files[file_index]
                
                # Ask for delay
                delay_input = input("Delay between tests (default 3 seconds): ").strip()
                delay = int(delay_input) if delay_input.isdigit() else 3
                
                return run_evaluation(selected_file, delay)
            else:
                print(f"❌ Invalid choice. Please enter a number between 1 and {len(available_files)}")
                
        except ValueError:
            print("❌ Invalid input. Please enter a number or 'q' to quit.")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            return False

def main():
    """Main function for evaluation runner."""
    # Setup logging
    setup_logging()
    
    print("🎯 Datadog Multi-Agent Debugging - Evaluation Runner")
    print("=" * 60)
    
    # Check command line arguments
    if len(sys.argv) > 1:
        # Run with specified file
        file_path = sys.argv[1]
        delay = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        run_evaluation(file_path, delay)
    else:
        # Interactive mode
        interactive_mode()

if __name__ == "__main__":
    main() 