"""
Enhanced Client library for EDMCOverlay with improved error handling and security
"""

from __future__ import print_function

import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

# Configuration
DEFAULT_SERVER_ADDRESS = "127.0.0.1"
DEFAULT_SERVER_PORT = 5010
CONNECT_TIMEOUT = 5.0
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 1.0

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = "EDMCOverlay.exe"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def trace(msg):
    """
    Compatibility function - print a trace message
    :param msg: Message to trace
    :return: The message (for compatibility with legacy code)
    """
    print("EDMCOverlay: {}".format(msg), file=sys.stderr)
    logger.info(f"Trace: {msg}")
    return msg


try:
    import monitor
except ImportError:
    monitor = None


class OverlayConnectionError(Exception):
    """Exception raised when overlay connection fails"""

    pass


class OverlayServiceError(Exception):
    """Exception raised when overlay service fails to start"""

    pass


def trace(msg: str) -> str:
    """
    Print a trace message with proper logging
    :param msg: Message to trace
    :return: The message
    """
    logger.info(f"EDMCOverlay: {msg}")
    return msg


class ServiceManager:
    """Manages the overlay service lifecycle"""

    def __init__(self):
        self._service: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._program_path: Optional[str] = None

    def find_server_program(self) -> Optional[str]:
        """
        Look for EDMCOverlay.exe in common locations
        :return: Path to executable or None if not found
        """
        if self._program_path is not None:
            return self._program_path

        locations = [
            os.path.join(HERE, PROG),
            os.path.join(HERE, "EDMCOverlay", PROG),
            os.path.join(HERE, "EDMCOverlay", "EDMCOverlay", "bin", "Release", PROG),
            os.path.join(HERE, "EDMCOverlay", "EDMCOverlay", "bin", "Debug", PROG),
        ]

        for path in locations:
            if os.path.isfile(path):
                trace(f"exe found at {path}")
                self._program_path = path
                return path

        return None

    def check_game_running(self) -> bool:
        """Check if Elite Dangerous is running"""
        if not monitor:
            return True
        return monitor.monitor.game_running()

    def is_service_alive(self) -> bool:
        """Check if the overlay service is responding"""
        try:
            test_overlay = Overlay()
            test_overlay.connect()
            test_overlay.send_message(0, ".", "black", 0, 0, 1)
            test_overlay.disconnect()
            return True
        except Exception:
            return False

    def ensure_service(self, args: List[str] = None) -> None:
        """
        Start the overlay service program with proper error handling
        :param args: Additional arguments for the service
        """
        if args is None:
            args = []

        if not self.check_game_running():
            return

        with self._lock:
            if self.is_service_alive():
                return

            program = self.find_server_program()
            if not program:
                raise OverlayServiceError("EDMCOverlay.exe not found")

            exedir = os.path.abspath(os.path.dirname(program))

            try:
                # Check if existing service is still running
                if self._service and self._service.poll() is None:
                    return

                if self.check_game_running():
                    trace(f"Starting {program} with {args}")
                    prog_args = [program] + args
                    self._service = subprocess.Popen(
                        prog_args,
                        cwd=exedir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )

                    # Wait a bit for service to start
                    time.sleep(2)

                    # Check if service started successfully
                    if self._service.poll() is not None:
                        stdout, stderr = self._service.communicate()
                        error_msg = (
                            f"{program} exited with code {self._service.returncode}"
                        )
                        if stderr:
                            error_msg += (
                                f", stderr: {stderr.decode('utf-8', errors='ignore')}"
                            )
                        raise OverlayServiceError(error_msg)

            except Exception as err:
                if self.check_game_running():
                    trace(f"Error in ensure_service: {err}")
                    raise OverlayServiceError(f"Failed to start overlay service: {err}")

    def stop_service(self) -> None:
        """Stop the overlay service"""
        with self._lock:
            if self._service:
                try:
                    self._service.terminate()
                    self._service.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._service.kill()
                except Exception as e:
                    logger.warning(f"Error stopping service: {e}")
                finally:
                    self._service = None


# Global service manager instance
_service_manager = ServiceManager()


class Overlay:
    """
    Enhanced client for EDMCOverlay with improved error handling and connection management
    """

    def __init__(
        self,
        server: str = DEFAULT_SERVER_ADDRESS,
        port: int = DEFAULT_SERVER_PORT,
        args: List[str] = None,
    ):
        self.server = server
        self.port = port
        self.args = args or []
        self.connection: Optional[socket.socket] = None
        self._lock = threading.Lock()

    @contextmanager
    def _connection_context(self):
        """Context manager for connection handling"""
        try:
            if not self.connection:
                self.connect()
            yield self.connection
        except Exception as e:
            self.disconnect()
            raise OverlayConnectionError(f"Connection error: {e}")

    def connect(self) -> None:
        """
        Open the connection with timeout and retry logic
        """
        with self._lock:
            if self.connection:
                return

            for attempt in range(RECONNECT_ATTEMPTS):
                try:
                    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    connection.settimeout(CONNECT_TIMEOUT)
                    connection.connect((self.server, self.port))
                    self.connection = connection
                    logger.debug(
                        f"Connected to overlay server at {self.server}:{self.port}"
                    )
                    return

                except (socket.timeout, ConnectionRefusedError, OSError) as e:
                    if attempt < RECONNECT_ATTEMPTS - 1:
                        logger.warning(
                            f"Connection attempt {attempt + 1} failed: {e}, retrying..."
                        )
                        time.sleep(RECONNECT_DELAY)
                    else:
                        raise OverlayConnectionError(
                            f"Failed to connect after {RECONNECT_ATTEMPTS} attempts: {e}"
                        )

    def disconnect(self) -> None:
        """Close the connection"""
        with self._lock:
            if self.connection:
                try:
                    self.connection.close()
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
                finally:
                    self.connection = None

    def send_raw(self, msg: Dict[str, Any]) -> None:
        """
        Encode a dict and send it to the server with proper error handling
        :param msg: Message dictionary to send
        """
        if not isinstance(msg, dict):
            raise ValueError("Message must be a dictionary")

        try:
            with self._connection_context() as conn:
                # Validate and sanitize the message
                sanitized_msg = self._sanitize_message(msg)
                data = json.dumps(sanitized_msg, ensure_ascii=True)

                if sys.version_info.major >= 3:
                    conn.send(data.encode("utf-8"))
                    conn.send(b"\n")
                else:
                    conn.send(data)
                    conn.send("\n")

                logger.debug(f"Sent message: {sanitized_msg}")

        except (BrokenPipeError, ConnectionResetError):
            self.disconnect()
            raise OverlayConnectionError("Connection lost")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise

    def _sanitize_message(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize message to prevent injection attacks
        :param msg: Original message
        :return: Sanitized message
        """
        sanitized = {}

        # Whitelist of allowed keys and their types
        allowed_fields = {
            "id": (str, int),
            "text": str,
            "color": str,
            "size": str,
            "x": (int, float),
            "y": (int, float),
            "ttl": (int, float),
            "shape": str,
            "fill": str,
            "w": (int, float),
            "h": (int, float),
            "command": str,
        }

        for key, value in msg.items():
            if key in allowed_fields:
                expected_types = allowed_fields[key]
                if not isinstance(expected_types, tuple):
                    expected_types = (expected_types,)

                if isinstance(value, expected_types):
                    # Additional validation for specific fields
                    if key in ["text", "color", "size", "shape", "fill", "command"]:
                        # Limit string length and remove potentially dangerous characters
                        if isinstance(value, str):
                            sanitized[key] = str(value)[:1000]  # Limit length
                    else:
                        sanitized[key] = value

        return sanitized

    def send_message(
        self,
        msgid: str,
        text: str,
        color: str,
        x: int,
        y: int,
        ttl: int = 4,
        size: str = "normal",
    ) -> None:
        """
        Send a text message to the overlay
        """
        if not self.connection:
            _service_manager.ensure_service(self.args)
            self.connect()

        msg = {
            "id": msgid,
            "color": color,
            "text": text,
            "size": size,
            "x": x,
            "y": y,
            "ttl": ttl,
        }
        self.send_raw(msg)

    def send_shape(
        self,
        shapeid: str,
        shape: str,
        color: str,
        fill: str,
        x: int,
        y: int,
        w: int,
        h: int,
        ttl: int,
    ) -> None:
        """
        Send a shape to the overlay
        """
        if not self.connection:
            _service_manager.ensure_service(self.args)
            self.connect()

        msg = {
            "id": shapeid,
            "shape": shape,
            "color": color,
            "fill": fill,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "ttl": ttl,
        }
        self.send_raw(msg)

    def send_command(self, command: str) -> None:
        """
        Send a command to the overlay server
        """
        if not self.connection:
            _service_manager.ensure_service(self.args)
            self.connect()

        msg = {"command": command}
        self.send_raw(msg)

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


def debugconsole():
    """
    Interactive debug console for testing
    """
    import load as loader

    loader.plugin_start()

    with Overlay() as cl:
        print("EDMCOverlay Debug Console - Type messages to send (Ctrl+C to exit)")
        try:
            while True:
                line = input("> ").strip()
                if line.lower() in ["exit", "quit"]:
                    break
                cl.send_message("debug", line, "red", 100, 100)
        except KeyboardInterrupt:
            print("\nExiting...")
        except Exception as e:
            print(f"Error: {e}")


# Global overlay instance for backward compatibility
internal = Overlay()


# Expose service manager functions for backward compatibility
def ensure_service(args: List[str] = None) -> None:
    """Ensure overlay service is running"""
    _service_manager.ensure_service(args)


def stop_service() -> None:
    """Stop overlay service"""
    _service_manager.stop_service()


if __name__ == "__main__":
    debugconsole()
