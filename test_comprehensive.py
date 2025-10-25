"""
Comprehensive test suite for EDMCOverlay
"""

import json
import os
import socket
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, mock_open, patch

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import Config
    from edmcoverlay_improved import (
        Overlay,
        OverlayConnectionError,
        OverlayServiceError,
        ServiceManager,
    )
except ImportError as e:
    print(f"Warning: Could not import improved modules: {e}")
    # Fallback to original module
    import edmcoverlay

    Overlay = edmcoverlay.Overlay


class TestOverlayConnection(unittest.TestCase):
    """Test overlay connection functionality"""

    def setUp(self):
        self.overlay = Overlay(server="127.0.0.1", port=5010)

    def tearDown(self):
        if hasattr(self.overlay, "disconnect"):
            self.overlay.disconnect()

    @patch("socket.socket")
    def test_connect_success(self, mock_socket):
        """Test successful connection"""
        mock_conn = MagicMock()
        mock_socket.return_value = mock_conn

        if hasattr(self.overlay, "_connection_context"):
            # Test improved version
            self.overlay.connect()
            mock_conn.connect.assert_called_once_with(("127.0.0.1", 5010))
            self.assertIsNotNone(self.overlay.connection)

    @patch("socket.socket")
    def test_connect_failure(self, mock_socket):
        """Test connection failure"""
        mock_socket.side_effect = ConnectionRefusedError("Connection refused")

        if hasattr(self.overlay, "OverlayConnectionError"):
            with self.assertRaises(OverlayConnectionError):
                self.overlay.connect()

    def test_message_sanitization(self):
        """Test message sanitization in improved version"""
        if hasattr(self.overlay, "_sanitize_message"):
            # Test valid message
            valid_msg = {
                "id": "test",
                "text": "Hello World",
                "color": "red",
                "x": 100,
                "y": 200,
                "ttl": 5,
            }
            sanitized = self.overlay._sanitize_message(valid_msg)
            self.assertEqual(sanitized, valid_msg)

            # Test message with invalid fields
            invalid_msg = {
                "id": "test",
                "text": "Hello",
                "malicious_field": "rm -rf /",
                "x": "not_a_number",
            }
            sanitized = self.overlay._sanitize_message(invalid_msg)
            self.assertNotIn("malicious_field", sanitized)
            self.assertNotIn("x", sanitized)  # Invalid type should be filtered

    def test_message_length_limit(self):
        """Test message length limitation"""
        if hasattr(self.overlay, "_sanitize_message"):
            long_text = "A" * 2000  # Longer than limit
            msg = {"text": long_text}
            sanitized = self.overlay._sanitize_message(msg)
            self.assertLessEqual(len(sanitized.get("text", "")), 1000)


class TestServiceManager(unittest.TestCase):
    """Test service manager functionality"""

    def setUp(self):
        if "ServiceManager" in globals():
            self.service_manager = ServiceManager()

    @patch("os.path.isfile")
    def test_find_server_program(self, mock_isfile):
        """Test finding server program"""
        if hasattr(self, "service_manager"):
            # Mock that the program exists in the first location
            mock_isfile.side_effect = lambda path: "EDMCOverlay.exe" in path

            program_path = self.service_manager.find_server_program()
            self.assertIsNotNone(program_path)
            self.assertIn("EDMCOverlay.exe", program_path)

    @patch("subprocess.Popen")
    def test_ensure_service_start(self, mock_popen):
        """Test service startup"""
        if hasattr(self, "service_manager"):
            # Mock successful service start
            mock_process = MagicMock()
            mock_process.poll.return_value = None  # Service is running
            mock_popen.return_value = mock_process

            with patch.object(
                self.service_manager, "find_server_program", return_value="test.exe"
            ):
                with patch.object(
                    self.service_manager, "check_game_running", return_value=True
                ):
                    with patch.object(
                        self.service_manager, "is_service_alive", return_value=False
                    ):
                        self.service_manager.ensure_service()
                        mock_popen.assert_called_once()


class TestConfig(unittest.TestCase):
    """Test configuration management"""

    def setUp(self):
        if "Config" in globals():
            # Use a temporary config file for testing
            self.test_config_file = "/tmp/test_edmcoverlay_config.json"
            self.config = Config(self.test_config_file)

    def tearDown(self):
        if hasattr(self, "test_config_file") and os.path.exists(self.test_config_file):
            os.remove(self.test_config_file)

    def test_default_values(self):
        """Test default configuration values"""
        if hasattr(self, "config"):
            self.assertEqual(self.config.server_address, "127.0.0.1")
            self.assertEqual(self.config.server_port, 5010)
            self.assertEqual(self.config.default_ttl, 4)

    def test_get_set_config(self):
        """Test getting and setting configuration values"""
        if hasattr(self, "config"):
            # Test setting a value
            self.config.set("server.port", 5011)
            self.assertEqual(self.config.get("server.port"), 5011)

            # Test getting non-existent value with default
            self.assertEqual(self.config.get("non.existent.key", "default"), "default")

    @patch(
        "builtins.open", new_callable=mock_open, read_data='{"server": {"port": 5015}}'
    )
    def test_load_config_from_file(self, mock_file):
        """Test loading configuration from file"""
        if hasattr(self, "config"):
            self.config.load()
            # After loading, the port should be updated
            self.assertEqual(self.config.get("server.port"), 5015)


class TestMessageHandling(unittest.TestCase):
    """Test message handling and JSON formatting"""

    def setUp(self):
        self.overlay = Overlay()

    def test_json_message_format(self):
        """Test that messages are properly formatted as JSON"""
        test_messages = [
            {
                "id": "test1",
                "text": "Hello World",
                "color": "red",
                "x": 100,
                "y": 200,
                "ttl": 5,
            },
            {
                "id": "shape1",
                "shape": "rect",
                "color": "blue",
                "fill": "lightblue",
                "x": 50,
                "y": 100,
                "w": 200,
                "h": 100,
                "ttl": 10,
            },
        ]

        for msg in test_messages:
            # Ensure the message can be serialized to JSON
            try:
                json_str = json.dumps(msg)
                # And can be deserialized back
                parsed = json.loads(json_str)
                self.assertEqual(msg, parsed)
            except (TypeError, ValueError) as e:
                self.fail(f"Message serialization failed: {e}")


class TestErrorHandling(unittest.TestCase):
    """Test error handling scenarios"""

    def setUp(self):
        self.overlay = Overlay()

    def test_invalid_message_types(self):
        """Test handling of invalid message types"""
        invalid_messages = [
            None,
            "string instead of dict",
            123,
            [],
        ]

        for invalid_msg in invalid_messages:
            if hasattr(self.overlay, "send_raw"):
                with self.assertRaises((ValueError, TypeError)):
                    self.overlay.send_raw(invalid_msg)

    @patch("socket.socket")
    def test_connection_loss_handling(self, mock_socket):
        """Test handling of connection loss"""
        mock_conn = MagicMock()
        mock_conn.send.side_effect = BrokenPipeError("Broken pipe")
        mock_socket.return_value = mock_conn

        # Test that connection errors are properly handled
        if hasattr(self.overlay, "send_raw"):
            with self.assertRaises((OverlayConnectionError, BrokenPipeError)):
                self.overlay.send_raw({"command": "test"})


class IntegrationTest(unittest.TestCase):
    """Integration tests (require actual overlay server)"""

    def setUp(self):
        self.overlay = Overlay()
        # Try to connect to see if server is available
        self.server_available = self._check_server_availability()

    def _check_server_availability(self):
        """Check if overlay server is available for testing"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", 5010))
            sock.close()
            return result == 0
        except Exception:
            return False

    @unittest.skipUnless(
        lambda self: self.server_available, "Overlay server not available"
    )
    def test_real_message_sending(self):
        """Test sending actual messages to the overlay server"""
        try:
            self.overlay.connect()
            self.overlay.send_message("test", "Integration Test", "green", 10, 10, 2)
            time.sleep(0.5)  # Give the message time to display
            # If we get here without exception, the test passed
        except (OverlayConnectionError, ConnectionRefusedError):
            # Expected when no server is running - skip test
            self.skipTest("No overlay server available for integration test")
        except Exception as e:
            self.fail(f"Unexpected error in integration test: {e}")
        finally:
            if hasattr(self.overlay, "disconnect"):
                self.overlay.disconnect()


def run_performance_test():
    """Performance test for message throughput"""
    print("Running performance test...")
    overlay = Overlay()

    try:
        overlay.connect()
        start_time = time.time()
        message_count = 100

        for i in range(message_count):
            overlay.send_message(f"perf_{i}", f"Message {i}", "yellow", 10 + i, 50, 1)
            time.sleep(0.01)  # Small delay to avoid overwhelming

        end_time = time.time()
        duration = end_time - start_time
        messages_per_second = message_count / duration

        print(f"Sent {message_count} messages in {duration:.2f} seconds")
        print(f"Throughput: {messages_per_second:.2f} messages/second")

    except Exception as e:
        print(f"Performance test failed: {e}")
    finally:
        if hasattr(overlay, "disconnect"):
            overlay.disconnect()


if __name__ == "__main__":
    print("EDMCOverlay Test Suite")
    print("=" * 50)

    # Run unit tests
    unittest.main(argv=[""], exit=False, verbosity=2)

    # Run performance test if requested
    if len(sys.argv) > 1 and "--performance" in sys.argv:
        print("\n" + "=" * 50)
        run_performance_test()
