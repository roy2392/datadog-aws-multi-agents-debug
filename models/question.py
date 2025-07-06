"""
Question model for representing test questions and expected outputs.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class Question:
    """Model representing a test question."""
    
    question: str
    expected: Optional[str] = None
    language: str = "hebrew"
    
    def __post_init__(self):
        """Validate question data after initialization."""
        if not self.question or not self.question.strip():
            raise ValueError("Question cannot be empty")
    
    def to_dict(self) -> dict:
        """Convert question to dictionary format."""
        return {
            "question": self.question,
            "expected": self.expected,
            "language": self.language
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Question':
        """Create question from dictionary."""
        return cls(
            question=data.get("question", ""),
            expected=data.get("expected"),
            language=data.get("language", "hebrew")
        ) 