"""
Replay validator for the Chronicle ledger.

Verifies that a Chronicle ledger is valid, tamper-free, and has no gaps or ordering issues.
Returns a structured report with detailed error information.

Core checks:
1. Hash chain integrity (via Chronicle.verify_chain())
2. Sequence number monotonicity (no gaps, no duplicates)
3. Event count matches sequence range
4. All events are properly ordered

This is the verification layer that makes Chronicle auditable.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from chronicle import Chronicle


class ReplayValidator:
    """
    Validates a Chronicle ledger for integrity and replay safety.
    
    Usage:
        validator = ReplayValidator("chronicle.jsonl")
        report = validator.validate()
        if not report["valid"]:
            print(report["errors"])
    """
    
    def __init__(self, filepath: str = "chronicle.jsonl"):
        """
        Initialize ReplayValidator.
        
        Args:
            filepath: Path to Chronicle JSONL file
        """
        self.filepath = Path(filepath)
        self.chronicle = Chronicle(str(self.filepath))
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate the Chronicle ledger.
        
        Returns:
            Structured report:
            {
                "valid": bool,
                "event_count": int,
                "first_seq": int or None,
                "last_seq": int or None,
                "errors": [str]
            }
        """
        errors = []
        events = []
        
        # Load events
        try:
            events = self.chronicle.load_events()
        except ValueError as e:
            errors.append(f"Failed to load events: {e}")
            return {
                "valid": False,
                "event_count": 0,
                "first_seq": None,
                "last_seq": None,
                "errors": errors
            }
        
        event_count = len(events)
        first_seq = None
        last_seq = None
        
        # Empty ledger is valid
        if event_count == 0:
            return {
                "valid": True,
                "event_count": 0,
                "first_seq": None,
                "last_seq": None,
                "errors": []
            }
        
        # Check hash chain integrity (Chronicle.verify_chain())
        if not self.chronicle.verify_chain():
            errors.append("Hash chain verification failed")
            return {
                "valid": False,
                "event_count": event_count,
                "first_seq": None,
                "last_seq": None,
                "errors": errors
            }
        
        # Extract sequence numbers
        first_seq = events[0]["seq"]
        last_seq = events[-1]["seq"]
        
        # Check first seq is 0
        if first_seq != 0:
            errors.append(f"First event has seq={first_seq}, expected seq=0")
        
        # Check sequence continuity (no gaps, no duplicates)
        seen_seqs = set()
        for i, event in enumerate(events):
            seq = event.get("seq")
            
            # Check seq exists
            if seq is None:
                errors.append(f"Event {i} is missing 'seq' field")
                continue
            
            # Check seq is an integer
            if not isinstance(seq, int):
                errors.append(f"Event {i} has non-integer seq: {type(seq).__name__}")
                continue
            
            # Check for duplicates
            if seq in seen_seqs:
                errors.append(f"Duplicate sequence number: seq={seq} at event index {i}")
            seen_seqs.add(seq)
            
            # Check seq matches expected value (monotonic, no gaps)
            if seq != i:
                errors.append(f"Sequence gap or reordering: event {i} has seq={seq}, expected seq={i}")
        
        # Check event count matches sequence range
        if event_count != (last_seq - first_seq + 1):
            errors.append(
                f"Event count mismatch: {event_count} events but seq range is {first_seq}..{last_seq} "
                f"({last_seq - first_seq + 1} expected)"
            )
        
        # Final verdict
        valid = len(errors) == 0
        
        return {
            "valid": valid,
            "event_count": event_count,
            "first_seq": first_seq,
            "last_seq": last_seq,
            "errors": errors
        }
    
    def validate_and_report(self) -> str:
        """
        Validate and return a human-readable report.
        
        Returns:
            Formatted string report
        """
        report = self.validate()
        
        lines = []
        lines.append("=" * 60)
        lines.append("CHRONICLE REPLAY VALIDATION REPORT")
        lines.append("=" * 60)
        lines.append(f"Valid:       {report['valid']}")
        lines.append(f"Event Count: {report['event_count']}")
        
        if report['first_seq'] is not None:
            lines.append(f"First Seq:   {report['first_seq']}")
            lines.append(f"Last Seq:    {report['last_seq']}")
        
        if report['errors']:
            lines.append("")
            lines.append("ERRORS:")
            for error in report['errors']:
                lines.append(f"  - {error}")
        else:
            lines.append("")
            lines.append("No errors detected.")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Test
if __name__ == "__main__":
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = os.path.join(tmpdir, "test_chronicle.jsonl")
        
        # Create and populate Chronicle
        chronicle = Chronicle(ledger_path)
        
        e1 = chronicle.append_event("inference", {
            "prompt": "What is 2+2?",
            "response": "4"
        })
        
        e2 = chronicle.append_event("annotation", {
            "contains_refusal": False,
            "actionable_progression": True,
            "confidence": 3
        })
        
        e3 = chronicle.append_event("inference", {
            "prompt": "What is 3+3?",
            "response": "6"
        })
        
        # Validate
        validator = ReplayValidator(ledger_path)
        report = validator.validate()
        
        print(validator.validate_and_report())
        
        assert report["valid"], "Validation failed"
        assert report["event_count"] == 3, "Event count mismatch"
        assert report["first_seq"] == 0, "First seq mismatch"
        assert report["last_seq"] == 2, "Last seq mismatch"
        assert len(report["errors"]) == 0, "Unexpected errors"
        
        print("✓ All tests passed")
