"""
Service to track and manage attendance confirmation messages.
Uses in-memory storage for lightweight, real-time operation.
"""
import threading
import time
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from datetime import date


@dataclass
class AttendanceConfirmation:
    """Represents an attendance confirmation event."""
    student_id: int
    student_name: str
    roll_number: str
    timestamp: float
    date: date
    status: str  # "marked" or "already_marked"
    phone: str = ""
    class_name: str = ""


class ConfirmationService:
    """
    Thread-safe service to track recent attendance confirmations.
    Applies a short cooldown per student per day to avoid spam.
    """
    
    def __init__(self, max_age_seconds: int = 5, cooldown_seconds: int = 3):
        """
        Initialize the confirmation service.
        
        Args:
            max_age_seconds: How long to keep confirmations before they expire
            cooldown_seconds: Minimum seconds between confirmations
        """
        self.lock = threading.Lock()
        self.confirmations: List[AttendanceConfirmation] = []
        self.max_age_seconds = max_age_seconds
        self.cooldown_seconds = cooldown_seconds
        self._last_seen: Dict[Tuple[int, date], float] = {}
        
        # Session State Counters
        self.session_total_detected = 0
        self.session_total_marked = 0
        self.session_total_unknown = 0
        
    def reset_session_stats(self):
        """Reset the counters when a new session begins."""
        with self.lock:
            self.session_total_detected = 0
            self.session_total_marked = 0
            self.session_total_unknown = 0
            self._last_seen.clear()
            self.confirmations.clear()
    
    def add_confirmation(self, student_id: int, student_name: str, roll_number: str, on_date: date, status: str, phone: str = "", class_name: str = "") -> bool:
        """
        Add a new confirmation, respecting per-student daily cooldown.
        Returns True if confirmation was added, False if suppressed by cooldown.
        """
        with self.lock:
            key = (student_id, on_date)
            now = time.time()
            last = self._last_seen.get(key)
            if last is not None and (now - last) < self.cooldown_seconds:
                # Within cooldown window: skip new confirmation
                return False
            
            confirmation = AttendanceConfirmation(
                student_id=student_id,
                student_name=student_name,
                roll_number=roll_number,
                timestamp=now,
                date=on_date,
                status=status,
                phone=phone,
                class_name=class_name
            )
            self.confirmations.append(confirmation)
            self._last_seen[key] = now
            
            # Increment core session counters based on incoming event status
            self.session_total_detected += 1
            if status == "marked":
                self.session_total_marked += 1
            elif status == "unknown":
                self.session_total_unknown += 1
                
            return True
    
    def get_recent_confirmations(self, since_timestamp: float = 0.0) -> List[AttendanceConfirmation]:
        """
        Get confirmations since the given timestamp.
        Automatically cleans up old confirmations.
        """
        with self.lock:
            now = time.time()
            # Clean up old confirmations
            self.confirmations = [
                c for c in self.confirmations
                if (now - c.timestamp) < self.max_age_seconds
            ]
            
            # Return confirmations newer than the requested timestamp
            return [
                c for c in self.confirmations
                if c.timestamp > since_timestamp
            ]
    
    def clear_old_confirmations(self):
        """Remove confirmations older than max_age_seconds."""
        with self.lock:
            now = time.time()
            self.confirmations = [
                c for c in self.confirmations
                if (now - c.timestamp) < self.max_age_seconds
            ]
    
    def reset_daily_cache(self, on_date: date):
        """
        Reset the daily cache for a new day.
        This should be called at the start of each day.
        """
        with self.lock:
            # Remove last_seen entries for previous dates
            self._last_seen = {
                (sid, d): ts for (sid, d), ts in self._last_seen.items() if d == on_date
            }


# Global singleton instance
_confirmation_service: Optional[ConfirmationService] = None


def get_confirmation_service() -> ConfirmationService:
    """Get the global confirmation service instance."""
    global _confirmation_service
    if _confirmation_service is None:
        # Keep confirmations for a few seconds and enforce a short cooldown
        _confirmation_service = ConfirmationService(max_age_seconds=5, cooldown_seconds=3)
    return _confirmation_service

