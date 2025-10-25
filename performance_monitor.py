"""
Performance monitoring and metrics collection for EDMCOverlay
"""

import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Collects and tracks performance metrics for EDMCOverlay"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.lock = threading.Lock()

        # Metrics storage
        self.message_times = deque(maxlen=max_history)
        self.connection_times = deque(maxlen=max_history)
        self.error_counts = defaultdict(int)
        self.message_counts = defaultdict(int)

        # Current session stats
        self.session_start = datetime.utcnow()
        self.total_messages_sent = 0
        self.total_errors = 0
        self.total_connections = 0
        self.current_connections = 0

        # Performance tracking
        self.last_cleanup = datetime.utcnow()
        self.cleanup_interval = timedelta(minutes=5)

    def record_message_sent(self, message_type: str = "unknown", duration: float = 0.0):
        """Record a message being sent"""
        with self.lock:
            now = datetime.utcnow()
            self.message_times.append(
                {"timestamp": now, "type": message_type, "duration": duration}
            )
            self.message_counts[message_type] += 1
            self.total_messages_sent += 1
            self._cleanup_if_needed()

    def record_connection_event(self, event_type: str, duration: float = 0.0):
        """Record connection events (connect, disconnect, error)"""
        with self.lock:
            now = datetime.utcnow()
            self.connection_times.append(
                {"timestamp": now, "event": event_type, "duration": duration}
            )

            if event_type == "connect":
                self.total_connections += 1
                self.current_connections += 1
            elif event_type == "disconnect":
                self.current_connections = max(0, self.current_connections - 1)

    def record_error(self, error_type: str, error_message: str = ""):
        """Record an error occurrence"""
        with self.lock:
            self.error_counts[error_type] += 1
            self.total_errors += 1

            logger.warning(
                f"Error recorded - Type: {error_type}, Message: {error_message}"
            )

    def get_message_rate(self, window_minutes: int = 1) -> float:
        """Get messages per second over the specified time window"""
        with self.lock:
            cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
            recent_messages = [m for m in self.message_times if m["timestamp"] > cutoff]

            if len(recent_messages) == 0:
                return 0.0

            time_span = (
                datetime.utcnow() - recent_messages[0]["timestamp"]
            ).total_seconds()
            return len(recent_messages) / max(time_span, 1.0)

    def get_average_message_duration(self, message_type: str = None) -> float:
        """Get average message processing duration"""
        with self.lock:
            if message_type:
                durations = [
                    m["duration"]
                    for m in self.message_times
                    if m["type"] == message_type and m["duration"] > 0
                ]
            else:
                durations = [
                    m["duration"] for m in self.message_times if m["duration"] > 0
                ]

            return sum(durations) / len(durations) if durations else 0.0

    def get_error_rate(self, window_minutes: int = 5) -> float:
        """Get error rate as a percentage over the specified time window"""
        with self.lock:
            cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
            recent_messages = [m for m in self.message_times if m["timestamp"] > cutoff]

            if len(recent_messages) == 0:
                return 0.0

            # Count errors in the same window (approximation)
            recent_error_count = sum(self.error_counts.values()) * (
                len(recent_messages) / max(self.total_messages_sent, 1)
            )

            return (recent_error_count / len(recent_messages)) * 100.0

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        with self.lock:
            connect_events = [
                c for c in self.connection_times if c["event"] == "connect"
            ]
            disconnect_events = [
                c for c in self.connection_times if c["event"] == "disconnect"
            ]

            avg_connect_time = 0.0
            if connect_events:
                connect_durations = [
                    c["duration"] for c in connect_events if c["duration"] > 0
                ]
                avg_connect_time = (
                    sum(connect_durations) / len(connect_durations)
                    if connect_durations
                    else 0.0
                )

            return {
                "total_connections": self.total_connections,
                "current_connections": self.current_connections,
                "average_connect_time": avg_connect_time,
                "connect_events": len(connect_events),
                "disconnect_events": len(disconnect_events),
            }

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        with self.lock:
            session_duration = (datetime.utcnow() - self.session_start).total_seconds()

            return {
                "session": {
                    "start_time": self.session_start.isoformat(),
                    "duration_seconds": session_duration,
                    "uptime": str(timedelta(seconds=int(session_duration))),
                },
                "messages": {
                    "total_sent": self.total_messages_sent,
                    "rate_per_second": self.get_message_rate(1),
                    "rate_per_minute": self.get_message_rate(1) * 60,
                    "average_duration": self.get_average_message_duration(),
                    "types": dict(self.message_counts),
                },
                "connections": self.get_connection_stats(),
                "errors": {
                    "total": self.total_errors,
                    "rate_percent": self.get_error_rate(5),
                    "by_type": dict(self.error_counts),
                },
                "performance": {
                    "memory_usage_mb": self._get_memory_usage(),
                    "thread_count": threading.active_count(),
                },
            }

    def export_metrics(self, filepath: str) -> bool:
        """Export metrics to JSON file"""
        try:
            stats = self.get_summary_stats()
            stats["export_time"] = datetime.utcnow().isoformat()

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)

            logger.info(f"Metrics exported to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return False

    def _cleanup_if_needed(self):
        """Clean up old data if needed"""
        now = datetime.utcnow()
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_data()
            self.last_cleanup = now

    def _cleanup_old_data(self):
        """Remove data older than 1 hour to save memory"""
        cutoff = datetime.utcnow() - timedelta(hours=1)

        # Clean message times
        while self.message_times and self.message_times[0]["timestamp"] < cutoff:
            self.message_times.popleft()

        # Clean connection times
        while self.connection_times and self.connection_times[0]["timestamp"] < cutoff:
            self.connection_times.popleft()

    def _get_memory_usage(self) -> float:
        """Get approximate memory usage in MB"""
        try:
            import psutil

            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # Fallback calculation
            import sys

            return (
                sys.getsizeof(self.message_times)
                + sys.getsizeof(self.connection_times) / 1024 / 1024
            )


class PerformanceMonitor:
    """Context manager for monitoring operation performance"""

    def __init__(
        self,
        metrics: PerformanceMetrics,
        operation_name: str,
        operation_type: str = "message",
    ):
        self.metrics = metrics
        self.operation_name = operation_name
        self.operation_type = operation_type
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        if exc_type is None:
            # Success
            if self.operation_type == "message":
                self.metrics.record_message_sent(self.operation_name, duration)
            elif self.operation_type == "connection":
                self.metrics.record_connection_event(self.operation_name, duration)
        else:
            # Error occurred
            error_type = exc_type.__name__ if exc_type else "UnknownError"
            error_msg = str(exc_val) if exc_val else ""
            self.metrics.record_error(f"{self.operation_type}_{error_type}", error_msg)


# Global metrics instance
_global_metrics = PerformanceMetrics()


def get_metrics() -> PerformanceMetrics:
    """Get the global metrics instance"""
    return _global_metrics


def monitor_operation(name: str, operation_type: str = "message") -> PerformanceMonitor:
    """Create a performance monitor for an operation"""
    return PerformanceMonitor(_global_metrics, name, operation_type)


def record_message(message_type: str = "unknown", duration: float = 0.0):
    """Convenience function to record a message"""
    _global_metrics.record_message_sent(message_type, duration)


def record_connection(event_type: str, duration: float = 0.0):
    """Convenience function to record a connection event"""
    _global_metrics.record_connection_event(event_type, duration)


def record_error(error_type: str, error_message: str = ""):
    """Convenience function to record an error"""
    _global_metrics.record_error(error_type, error_message)


def get_performance_summary() -> Dict[str, Any]:
    """Get performance summary"""
    return _global_metrics.get_summary_stats()


def export_performance_metrics(filepath: str = None) -> bool:
    """Export performance metrics to file"""
    if filepath is None:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filepath = f"edmcoverlay_metrics_{timestamp}.json"

    return _global_metrics.export_metrics(filepath)


# Performance monitoring decorator
def monitor_performance(operation_name: str = None, operation_type: str = "message"):
    """Decorator for monitoring function performance"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            name = operation_name or func.__name__
            with monitor_operation(name, operation_type):
                return func(*args, **kwargs)

        return wrapper

    return decorator


if __name__ == "__main__":
    # Example usage and testing
    print("Performance Monitoring System Test")
    print("=" * 40)

    metrics = PerformanceMetrics()

    # Simulate some activity
    for i in range(10):
        with PerformanceMonitor(metrics, "test_message", "message"):
            time.sleep(0.01)  # Simulate processing time

    # Simulate some connections
    metrics.record_connection_event("connect", 0.05)
    metrics.record_connection_event("disconnect", 0.01)

    # Simulate some errors
    metrics.record_error("ConnectionError", "Failed to connect")

    # Print summary
    summary = metrics.get_summary_stats()
    print(json.dumps(summary, indent=2))

    # Export metrics
    if metrics.export_metrics("test_metrics.json"):
        print("\nMetrics exported successfully to test_metrics.json")
    else:
        print("\nFailed to export metrics")
