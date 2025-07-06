"""
Migration script to help transition from dd_traces.py to the new modular structure.
"""

import json
import os
from typing import List, Dict, Any

def migrate_questions_from_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Migrate questions from existing JSON files to the new format.
    
    Args:
        file_path: Path to the JSON file containing questions
        
    Returns:
        List of questions in the new format
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different file formats
        if isinstance(data, list):
            # Direct list of questions
            return data
        elif isinstance(data, dict) and 'questions' in data:
            # Questions nested in a dict
            return data['questions']
        else:
            print(f"❌ Unsupported format in {file_path}")
            return []
            
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return []
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {file_path}")
        return []

def create_migrated_main(questions: List[Dict[str, Any]], output_file: str = "main_migrated.py"):
    """
    Create a migrated main.py file using the new structure.
    
    Args:
        questions: List of questions to use
        output_file: Output file path
    """
    template = f'''"""
Migrated main.py using the new modular structure.
Generated from existing question data.
"""

from runners.test_runner import TestRunner
from utils.logger import setup_logging

def get_migrated_questions():
    """Get questions migrated from existing data."""
    return {json.dumps(questions, indent=4)}

def main():
    """Main function using migrated questions."""
    # Setup logging
    setup_logging()
    
    # Get migrated questions
    questions = get_migrated_questions()
    
    # Create and run test suite
    runner = TestRunner()
    results = runner.run_test_suite(questions, delay_between_tests=3)
    
    # Flush data to Datadog
    runner.flush_data_to_datadog()
    
    # Print final summary
    summary = runner.get_results_summary()
    print(f"\\n📋 Final Summary: {{summary['successful_tests']}}/{{summary['total_tests']}} tests passed")

if __name__ == "__main__":
    main()
'''
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(template)
    
    print(f"✅ Created migrated main file: {output_file}")

def check_environment_setup():
    """Check if environment is properly set up for the new structure."""
    print("🔍 Checking environment setup...")
    
    # Check for .env file
    if os.path.exists('.env'):
        print("✅ .env file found")
    else:
        print("⚠️  .env file not found - copy from .env-example")
    
    # Check for required directories
    required_dirs = ['models', 'services', 'processors', 'orchestrators', 'runners', 'utils']
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"✅ {dir_name}/ directory found")
        else:
            print(f"❌ {dir_name}/ directory missing")
    
    # Check for required files
    required_files = [
        'config.py',
        'main.py',
        'models/question.py',
        'models/test_result.py',
        'services/bedrock_service.py',
        'services/datadog_service.py',
        'processors/trace_processor.py',
        'orchestrators/agent_orchestrator.py',
        'runners/test_runner.py',
        'utils/logger.py',
        'utils/text_processing.py'
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} found")
        else:
            print(f"❌ {file_path} missing")

def main():
    """Main migration function."""
    print("🔄 Datadog Multi-Agent Debugging - Migration Tool")
    print("=" * 50)
    
    # Check environment
    check_environment_setup()
    print()
    
    # Try to migrate questions from existing files
    question_files = [
        'eval_questions.json',
        'eval_questions_single.json',
        'eval.json'
    ]
    
    migrated_questions = []
    
    for file_path in question_files:
        if os.path.exists(file_path):
            print(f"📁 Found existing file: {file_path}")
            questions = migrate_questions_from_file(file_path)
            if questions:
                migrated_questions.extend(questions)
                print(f"✅ Migrated {len(questions)} questions from {file_path}")
            print()
    
    if migrated_questions:
        print(f"📊 Total questions migrated: {len(migrated_questions)}")
        create_migrated_main(migrated_questions)
    else:
        print("📝 No questions found to migrate - using default questions")
        create_migrated_main([
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
        ])
    
    print("\n🎉 Migration completed!")
    print("\n📋 Next steps:")
    print("1. Review the generated main_migrated.py file")
    print("2. Update your .env file with proper credentials")
    print("3. Run: python main_migrated.py")
    print("4. Check Datadog for your traces")
    print("\n📚 For more information, see README_REFACTORED.md")

if __name__ == "__main__":
    main() 