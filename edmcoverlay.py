"""
Client library for EDMCOverlay
"""

from __future__ import print_function

import json
import os
import socket
import subprocess
import sys
import time

SERVER_ADDRESS = "127.0.0.1"
SERVER_PORT = 5010

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = "EDMCOverlay.exe"

try:
    import monitor
except ImportError:
    monitor = None


def trace(msg):
    """
    Print a trace message
    :param msg:
    :return:
    """
    print("EDMCOverlay: {}".format(msg), file=sys.stderr)
    return msg


_prog = None


def find_server_program():
    """
    Look for EDMCOverlay.exe
    :return:
    """
    global _prog
    if _prog is not None:
        return _prog

    locations = [
        os.path.join(HERE, PROG),
        os.path.join(HERE, "EDMCOverlay", PROG),
        os.path.join(HERE, "EDMCOverlay", "EDMCOverlay", "bin", "Release", PROG),
        os.path.join(HERE, "EDMCOverlay", "EDMCOverlay", "bin", "Debug", PROG),
    ]
    for item in locations:
        if os.path.isfile(item):
            trace("EDMCOverlay: exe found at {}...".format(item))
            _prog = item
            return item
    return None


_service = None


def check_game_running():
    if not monitor:
        return True

    return monitor.monitor.game_running()


def ensure_service(args=[]):
    """
    Start the overlay service program
    :return:
    """
    if HERE not in sys.path:
        sys.path.append(HERE)

    if not check_game_running():
        return

    global _service
    program = find_server_program()
    if not program:
        trace("EDMCOverlay.exe not found in any expected location")
        return

    exedir = os.path.abspath(os.path.dirname(program))

    # see if it is alive
    try:
        internal.connect()
        internal.send_message(0, ".", "black", 0, 0, 1)
        return
    except (ConnectionRefusedError, OSError) as conn_err:
        trace(f"Overlay server connection failed: {conn_err}")
    except Exception as err:
        trace(f"Unexpected error checking server status: {err}")

    trace("Overlay server is not running, attempting to start...")

    # if it isnt running, start it
    try:
        if _service:
            if _service.poll() is not None:
                _service = None

        if not _service:
            if check_game_running():
                trace("EDMCOverlay is starting {} with {}".format(program, args))
                prog_args = [program] + args if args else [program]
                try:
                    _service = subprocess.Popen(
                        prog_args,
                        cwd=exedir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except FileNotFoundError as file_err:
                    trace(
                        f"Failed to start overlay server - file not found: {file_err}"
                    )
                    return
                except PermissionError as perm_err:
                    trace(
                        f"Failed to start overlay server - permission denied: {perm_err}"
                    )
                    return

        time.sleep(2)
        if _service and _service.poll() is not None:
            stdout, stderr = _service.communicate()
            error_details = f"Exit code: {_service.returncode}"
            if stderr:
                error_details += (
                    f", Error output: {stderr.decode('utf-8', errors='ignore')}"
                )
            trace(f"Overlay server failed to start properly - {error_details}")
            try:
                subprocess.check_call(prog_args, cwd=exedir)
            except subprocess.CalledProcessError as proc_err:
                trace(f"Overlay server startup verification failed: {proc_err}")
                return
            raise RuntimeError(
                f"{program} exited with {_service.returncode}: {error_details}"
            )

    except subprocess.SubprocessError as sub_err:
        if check_game_running():
            trace(f"Subprocess error starting overlay server: {sub_err}")
    except OSError as os_err:
        if check_game_running():
            trace(f"OS error starting overlay server: {os_err}")
    except Exception as err:
        if check_game_running():
            trace(f"Unexpected error in ensure_service: {err}")


class Overlay(object):
    """
    Client for EDMCOverlay with improved error handling
    """

    def __init__(self, server=SERVER_ADDRESS, port=SERVER_PORT, args=[]):
        self.server = server
        self.port = port
        self.args = args if args is not None else []
        self.connection = None

    def connect(self):
        """
        Open the connection with better error handling
        :return:
        :raises: ConnectionError for connection issues
        """
        try:
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection.settimeout(10.0)  # Add timeout
            connection.connect((self.server, self.port))
            self.connection = connection
            trace(
                f"Successfully connected to overlay server at {self.server}:{self.port}"
            )
        except socket.timeout:
            raise ConnectionError(
                f"Timeout connecting to overlay server at {self.server}:{self.port}"
            )
        except ConnectionRefusedError:
            raise ConnectionError(
                f"Connection refused by overlay server at {self.server}:{self.port}"
            )
        except socket.gaierror as e:
            raise ConnectionError(f"DNS resolution failed for {self.server}: {e}")
        except OSError as e:
            raise ConnectionError(f"Network error connecting to overlay server: {e}")

    def send_raw(self, msg):
        """
        Encode a dict and send it to the server with improved error handling
        :param msg: Message dictionary to send
        :return: None
        :raises: ValueError for invalid messages, ConnectionError for network issues
        """
        if not self.connection:
            trace("No connection available, cannot send message")
            return None

        if not isinstance(msg, dict):
            raise ValueError("Message must be a dictionary")

        try:
            # Validate message structure
            if "id" not in msg:
                trace(
                    "Warning: Message without 'id' field may not be processed correctly"
                )

            data = json.dumps(msg, ensure_ascii=True)

            # Add length validation
            if len(data) > 10000:  # 10KB limit
                raise ValueError(f"Message too large: {len(data)} bytes (max 10000)")

            if sys.version_info.major >= 3:
                encoded_data = data.encode("utf-8")
                self.connection.send(encoded_data)
                self.connection.send(b"\n")
            else:
                self.connection.send(data)
                self.connection.send("\n")

            trace(f"Successfully sent message with ID: {msg.get('id', 'unknown')}")

        except json.JSONEncodeError as json_err:
            self.connection = None
            raise ValueError(f"Failed to encode message as JSON: {json_err}")
        except (BrokenPipeError, ConnectionResetError) as conn_err:
            self.connection = None
            raise ConnectionError(f"Connection lost while sending message: {conn_err}")
        except socket.timeout:
            self.connection = None
            raise ConnectionError("Timeout while sending message to overlay server")
        except OSError as os_err:
            self.connection = None
            raise ConnectionError(f"Network error while sending message: {os_err}")
        except Exception as err:
            self.connection = None
            trace(f"Unexpected error in send_raw: {err}")
            raise

    def send_shape(self, shapeid, shape, color, fill, x, y, w, h, ttl):
        """
        Send a shape
        :param shapeid:
        :param shape:
        :param color:
        :param fill:
        :param x:
        :param y:
        :param w:
        :param h:
        :param ttl:
        :return:
        """
        if not self.connection:
            ensure_service(self.args)
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

    def send_message(self, msgid, text, color, x, y, ttl=4, size="normal"):
        """
        Send a message
        :param msgid:
        :param text:
        :param color:
        :param x:
        :param y:
        :param ttl:
        :param size:
        :return:
        """
        if not self.connection:
            ensure_service(self.args)
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


def debugconsole():
    """
    Print stuff
    """
    import load as loader

    loader.plugin_start()

    cl = Overlay()

    while True:
        line = sys.stdin.readline().strip()
        cl.send_message("msg", line, "red", 100, 100)


if __name__ == "__main__":
    debugconsole()

internal = Overlay()
