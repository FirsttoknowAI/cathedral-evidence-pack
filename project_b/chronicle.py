"""
Append-only event ledger with SHA256 hash chaining and deterministic serialization.

Core invariants:
1. Events are immutable once written
2. Every event is hash-chained to the previous event
3. JSON serialization is deterministic (sorted keys, no randomness)
4. Chronicle file is append-only JSONL with fsync durability
5. Verification must reproduce identical hash sequence
6. Sequence numbers prevent timestamp collisions and enable ordering

This is the foundation. Everything else depends on this being correct.
"""

import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class Chronicle:
    """
    Append-only event ledger with cryptographic hash chaining.
    
    Each event includes:
    - event_id: unique identifier (UUID)
    - seq: monotonic sequence number (prevents timestamp collisions)
    - timestamp: ISO8601 UTC timestamp
    - event_type: category of event (e.g., "inference", "annotation")
    - payload: event data (dict)
    - prev_hash: hash of previous event (or "0" if first)
    - hash: SHA256 of all above fields
    
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
    
    def _get_next_seq_and_prev_hash(self) -> tuple[int, str]:
        """
        Get the next sequence number and hash of the last event in the ledger.
        
        Sequence numbers are monotonic and prevent timestamp collisions.
        
        Returns:
            Tuple of (next_seq, prev_hash)
            - next_seq: sequence number for next event (0 if ledger empty)
            - prev_hash: hex digest of last event's hash, or "0" if empty
        """
        if not self.filepath.exists() or self.filepath.stat().st_size == 0:
            return 0, "0"
        
        last_seq = -1
        last_hash = "0"
        
        try:
            with open(self.filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        event = json.loads(line)
                        last_seq = event["seq"]
                        last_hash = event["hash"]
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(
                f"Corrupted chronicle file at {self.filepath}: {e}"
            ) from e
        
        return last_seq + 1, last_hash
    
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
        - Event is durably written to disk (fsync)
        - Event is immutable after this call
        - Sequence number is monotonic (prevents timestamp collisions)
        """
        # Get next sequence number and previous hash
        next_seq, prev_hash = self._get_next_seq_and_prev_hash()
        
        # Create event structure
        event = {
            "event_id": str(uuid.uuid4()),
            "seq": next_seq,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        
        # Compute hash (hash of everything except the hash field itself)
        hashable = {
            "event_id": event["event_id"],
            "seq": event["seq"],
            "timestamp": event["timestamp"],
            "event_type": event["event_type"],
            "payload": event["payload"],
            "prev_hash": event["prev_hash"],
        }
        hashable_str = self._serialize_deterministically(hashable)
        event["hash"] = self._compute_hash(hashable_str)
        
        # Write to ledger (append-only) with fsync durability
        with open(self.filepath, 'a') as f:
            f.write(self._serialize_deterministically(event) + '\n')
            f.flush()
            os.fsync(f.fileno())
        
        return event
    
    def load_events(self) -> List[Dict[str, Any]]:
        """
        Load all events from the ledger.
        
        Returns:
            List of events in order, or empty list if ledger is empty
            
        Raises:
            ValueError: If any line contains corrupted JSON
        """
        events = []
        
        if not self.filepath.exists():
            return events
        
        try:
            with open(self.filepath, 'r') as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            raise ValueError(
                                f"Corrupted JSON at {self.filepath}:{line_num}: {e}"
                            ) from e
        except IOError as e:
            raise ValueError(f"Failed to read chronicle file {self.filepath}: {e}") from e
        
        return events
    
    def verify_chain(self) -> bool:
        """
        Verify hash chain integrity.
        
        Checks:
        1. Each event's hash is correct
        2. Each event's prev_hash matches previous event's hash
        3. First event's prev_hash is "0"
        4. Sequence numbers are monotonic
        
        Returns:
            True if chain is valid, False otherwise
            
        Why verify?
        - Detects tampering (event modified on disk)
        - Detects missing events (hash chain broken)
        - Detects reordered events (prev_hash doesn't match)
        - Detects sequence number gaps (indicates deletion)
        """
        events = self.load_events()
        
        if not events:
            return True  # Empty ledger is valid
        
        # Check first event's prev_hash
        if events[0]["prev_hash"] != "0":
            return False
        
        # Check first event's seq
        if events[0]["seq"] != 0:
            return False
        
        prev_hash = "0"
        prev_seq = -1
        
        for event in events:
            # Verify seq is monotonic
            if event["seq"] != prev_seq + 1:
                return False
            
            # Verify prev_hash matches
            if event["prev_hash"] != prev_hash:
                return False
            
            # Recompute hash
            hashable = {
                "event_id": event["event_id"],
                "seq": event["seq"],
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
            prev_seq = event["seq"]
        
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
        print(f"Event 1: seq={e1['seq']}, event_id={e1['event_id'][:8]}...")
        assert e1["seq"] == 0, "First event should have seq=0"
        assert e1["prev_hash"] == "0", "First event should have prev_hash='0'"
        
        e2 = chronicle.append_event("annotation", {
            "contains_refusal": False,
            "actionable_progression": True,
            "confidence": 3
        })
        print(f"Event 2: seq={e2['seq']}, event_id={e2['event_id'][:8]}...")
        assert e2["seq"] == 1, "Second event should have seq=1"
        assert e2["prev_hash"] == e1["hash"], "Event 2 should chain to Event 1"
        
        # Load and verify
        events = chronicle.load_events()
        print(f"Total events: {len(events)}")
        assert len(events) == 2, "Should have 2 events"
        
        valid = chronicle.verify_chain()
        print(f"Chain valid: {valid}")
        assert valid, "Chain verification failed"
        
        assert chronicle.get_event_count() == 2, "Event count mismatch"
        
        last = chronicle.get_last_event()
        assert last["seq"] == 1, "Last event seq mismatch"
        
        print("✓ All tests passed")
