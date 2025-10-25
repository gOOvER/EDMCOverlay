"""
Plugin for EDMCOverlay - Enhanced Version
"""
import os
import logging
from typing import Optional

# Try to use the improved version first, fallback to legacy if needed
try:
    from edmcoverlay_improved import Overlay, ServiceManager, OverlayConnectionError, trace
    from edmcoverlay import ensure_service  # Keep legacy service management for compatibility
    USING_IMPROVED = True
except ImportError:
    from edmcoverlay import ensure_service, Overlay, trace
    USING_IMPROVED = False

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGDIR = os.path.dirname(HERE)

# Initialize client with improved version if available
if USING_IMPROVED:
    service_manager = ServiceManager()
    client: Optional[Overlay] = None
else:
    client = Overlay()


def plugin_start3(plugin_dir):
    return plugin_start()


def plugin_start():
    """
    Start our plugin, add this dir to the search path so others can use our module
    Enhanced version with improved error handling and service management
    :return:
    """
    global client
    
    if USING_IMPROVED:
        # Use improved version with context management
        try:
            service_manager.ensure_service()
            client = Overlay()
            
            with client:
                client.send_message("edmcintro", trace("EDMC Ready (Enhanced)"), "green", 30, 165, ttl=6)
                
        except OverlayConnectionError as err:
            print(f"Enhanced overlay connection failed: {err}")
            # Fallback to legacy service management
            ensure_service()
            client = Overlay()
            try:
                client.send_message("edmcintro", trace("EDMC Ready (Fallback)"), "yellow", 30, 165, ttl=6)
            except Exception as fallback_err:
                print(f"Fallback also failed: {fallback_err}")
        except Exception as err:
            print(f"Unexpected error in enhanced plugin_start(): {err}")
            # Complete fallback
            ensure_service()
            client = Overlay()
    else:
        # Legacy version
        ensure_service()
        try:
            client.send_message("edmcintro", trace("EDMC Ready"), "yellow", 30, 165, ttl=6)
        except Exception as err:
            print("Error sending message in plugin_start() : {}".format(err))
            
    return "EDMCOverlay"


def journal_entry(cmdr, is_beta, system, station, entry, state):
    """
    Make sure the service is up and running
    Enhanced version with better service monitoring
    :param cmdr: Commander name
    :param is_beta: Beta flag
    :param system: Current system
    :param station: Current station
    :param entry: Journal entry
    :param state: Current state
    :return:
    """
    if USING_IMPROVED:
        # Use improved service monitoring
        if service_manager and not service_manager.is_service_alive():
            try:
                service_manager.ensure_service()
            except Exception as err:
                print(f"Failed to restart service: {err}")
                # Fallback to legacy
                ensure_service()
    else:
        # Legacy version
        ensure_service()


def plugin_stop():
    """
    EDMC is going to exit.
    Enhanced version with proper cleanup
    :return:
    """
    global client, service_manager
    
    if USING_IMPROVED:
        # Use improved cleanup
        try:
            if client:
                # Send exit command with context manager
                with client:
                    client.send_raw({"command": "exit"})
                client = None
                
            if service_manager:
                service_manager.stop_service()
                
        except Exception as err:
            print(f"Error during enhanced cleanup: {err}")
    else:
        # Legacy cleanup
        try:
            client.send_raw({"command": "exit"})
        except Exception as err:
            print(f"Error during legacy cleanup: {err}")


def get_client_info():
    """
    Get information about the current client implementation
    :return: Dict with client info
    """
    return {
        "using_improved": USING_IMPROVED,
        "client_type": "Enhanced" if USING_IMPROVED else "Legacy",
        "has_service_manager": USING_IMPROVED and service_manager is not None,
        "client_active": client is not None
    }
