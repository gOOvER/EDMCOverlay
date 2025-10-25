"""
Test script for the enhanced load.py integration
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from load import (
        get_client_info,
        journal_entry,
        plugin_start,
        plugin_start3,
        plugin_stop,
    )

    print("[TEST] Testing Enhanced Load.py Integration")
    print("=" * 50)

    # Test client info
    info = get_client_info()
    print("[INFO] Client Info:")
    print(f"   Using Improved: {info['using_improved']}")
    print(f"   Client Type: {info['client_type']}")
    print(f"   Service Manager: {info['has_service_manager']}")
    print(f"   Client Active: {info['client_active']}")
    print()

    # Test plugin functions
    print("[RUN] Testing Plugin Functions:")

    # Test plugin start
    try:
        result = plugin_start()
        print(f"[PASS] plugin_start() returned: {result}")
    except Exception as e:
        print(f"[FAIL] plugin_start() failed: {e}")

    # Test journal entry
    try:
        journal_entry("TestCmdr", False, "Sol", "Abraham Lincoln", {}, {})
        print("[PASS] journal_entry() executed successfully")
    except Exception as e:
        print(f"[FAIL] journal_entry() failed: {e}")

    # Test plugin stop
    try:
        plugin_stop()
        print("[PASS] plugin_stop() executed successfully")
    except Exception as e:
        print(f"[FAIL] plugin_stop() failed: {e}")

    print()
    print("[PASS] Integration test completed!")

except ImportError as e:
    print(f"[FAIL] Import error: {e}")
except Exception as e:
    print(f"[FAIL] Unexpected error: {e}")
