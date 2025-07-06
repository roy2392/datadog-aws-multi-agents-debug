"""
Test result model for representing agent test results.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class TestResult:
    """Model representing a test result."""
    
    question: str
    response: Optional[str]
    expected: Optional[str]
    duration: float
    success: bool
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> dict:
        """Convert test result to dictionary format."""
        return {
            "question": self.question,
            "response": self.response,
            "expected": self.expected,
            "duration": self.duration,
            "success": self.success,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TestResult':
        """Create test result from dictionary."""
        timestamp_str = data.get("timestamp")
        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else None
        
        return cls(
            question=data.get("question", ""),
            response=data.get("response"),
            expected=data.get("expected"),
            duration=data.get("duration", 0.0),
            success=data.get("success", False),
            error_message=data.get("error_message"),
            timestamp=timestamp
        ) 