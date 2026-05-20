"""
Append-only event ledger with SHA256 hash chaining and deterministic serialization.

Core invariants:
1. Events are immutable once written
2. Every event is hash-chained to the previous event
3. JSON serialization is deterministic (sorted keys, no randomness)
4. Chronicle file is append-only JSONL
5. Verification must reproduce identical hash sequence

This is the foundation. Everything else depends on this being correct.
"""

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class Chronicle:
    """
    Append-only event ledger with cryptographic hash chaining.
    
    Usage:
        chronicle = Chronicle("events.jsonl")
        chronicle.append_event("inference", {"prompt": "...", "response": "..."})
        assert chronicle.verify_chain()
    """
    
    def __init__(self, filepath: str = "chronicle.jsonl"):
        """
        Initialize Chronicle.
        
        Args:
            filepath: Path to append-only JSONL file. Created if doesn't exist.
        """
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        
    def _serialize_deterministically(self, obj: Any) -> str:
        """
        Serialize object to JSON with deterministic ordering.
        
        Args:
            obj: Object to serialize
            
        Returns:
            JSON string with sorted keys, no whitespace
            
        Why deterministic?
        - Ensures same input always produces same hash
        - Prevents replay attacks via JSON reordering
        - Enables bit-for-bit verification
        """
        return json.dumps(obj, sort_keys=True, separators=(',', ':'))
    
    def _compute_hash(self, data: str) -> str:
        """
        Compute SHA256 hash of data.
        
        Args:
            data: String to hash
            
        Returns:
            Hex digest of SHA256(data)
        """
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _get_prev_hash(self) -> str:
        """
        Get hash of the last event in the ledger.
        
        Returns:
            Hex digest of last event's hash, or "0" if empty
        """
        if not self.filepath.exists() or self.filepath.stat().st_size == 0:
            return "0"
        
        with open(self.filepath, 'r') as f:
            last_line = None
            for last_line in f:
                pass
        
        if last_line is None:
            return "0"
        
        event = json.loads(last_line)
        return event["hash"]
    
    def append_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Append a new event to the ledger.
        
        Args:
            event_type: Type of event (e.g., "inference", "annotation")
            payload: Event payload (dict)
            
        Returns:
            The complete event object that was written
            
        Guarantees:
        - Event is hash-chained to previous event
        - Event is written atomically to disk
        - Event is immutable after this call
        """
        # Get previous hash
        prev_hash = self._get_prev_hash()
        
        # Create event structure
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        
        # Compute hash (hash of everything except the hash field itself)
        hashable = {
            "event_id": event["event_id"],
            "timestamp": event["timestamp"],
            "event_type": event["event_type"],
            "payload": event["payload"],
            "prev_hash": event["prev_hash"],
        }
        hashable_str = self._serialize_deterministically(hashable)
        event["hash"] = self._compute_hash(hashable_str)
        
        # Write to ledger (append-only)
        with open(self.filepath, 'a') as f:
            f.write(self._serialize_deterministically(event) + '\n')
        
        return event
    
    def load_events(self) -> List[Dict[str, Any]]:
        """
        Load all events from the ledger.
        
        Returns:
            List of events in order, or empty list if ledger is empty
        """
        events = []
        
        if not self.filepath.exists():
            return events
        
        with open(self.filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        
        return events
    
    def verify_chain(self) -> bool:
        """
        Verify hash chain integrity.
        
        Checks:
        1. Each event's hash is correct
        2. Each event's prev_hash matches previous event's hash
        3. First event's prev_hash is "0"
        
        Returns:
            True if chain is valid, False otherwise
            
        Why verify?
        - Detects tampering (event modified on disk)
        - Detects missing events (hash chain broken)
        - Detects reordered events (prev_hash doesn't match)
        """
        events = self.load_events()
        
        if not events:
            return True  # Empty ledger is valid
        
        # Check first event's prev_hash
        if events[0]["prev_hash"] != "0":
            return False
        
        prev_hash = "0"
        
        for event in events:
            # Verify prev_hash matches
            if event["prev_hash"] != prev_hash:
                return False
            
            # Recompute hash
            hashable = {
                "event_id": event["event_id"],
                "timestamp": event["timestamp"],
                "event_type": event["event_type"],
                "payload": event["payload"],
                "prev_hash": event["prev_hash"],
            }
            hashable_str = self._serialize_deterministically(hashable)
            computed_hash = self._compute_hash(hashable_str)
            
            # Verify hash matches
            if event["hash"] != computed_hash:
                return False
            
            prev_hash = event["hash"]
        
        return True
    
    def get_event_count(self) -> int:
        """Get the total number of events in the ledger."""
        return len(self.load_events())
    
    def get_last_event(self) -> Optional[Dict[str, Any]]:
        """Get the most recent event, or None if ledger is empty."""
        events = self.load_events()
        return events[-1] if events else None


# Simple test
if __name__ == "__main__":
    import tempfile
    import os
    
    # Use temp file for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = os.path.join(tmpdir, "test_chronicle.jsonl")
        
        # Create chronicle
        chronicle = Chronicle(ledger_path)
        
        # Append some events
        e1 = chronicle.append_event("inference", {
            "prompt": "What is 2+2?",
            "response": "4"
        })
        print(f"Event 1: {e1['event_id']}")
        
        e2 = chronicle.append_event("annotation", {
            "contains_refusal": False,
            "actionable_progression": True,
            "confidence": 3
        })
        print(f"Event 2: {e2['event_id']}")
        
        # Load and verify
        events = chronicle.load_events()
        print(f"Total events: {len(events)}")
        
        valid = chronicle.verify_chain()
        print(f"Chain valid: {valid}")
        
        assert valid, "Chain verification failed"
        assert chronicle.get_event_count() == 2, "Event count mismatch"
        print("✓ All tests passed")
