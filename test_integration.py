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

    print("🧪 Testing Enhanced Load.py Integration")
    print("=" * 50)

    # Test client info
    info = get_client_info()
    print(f"📊 Client Info:")
    print(f"   Using Improved: {info['using_improved']}")
    print(f"   Client Type: {info['client_type']}")
    print(f"   Service Manager: {info['has_service_manager']}")
    print(f"   Client Active: {info['client_active']}")
    print()

    # Test plugin functions
    print("🚀 Testing Plugin Functions:")

    # Test plugin start
    try:
        result = plugin_start()
        print(f"✅ plugin_start() returned: {result}")
    except Exception as e:
        print(f"❌ plugin_start() failed: {e}")

    # Test journal entry
    try:
        journal_entry("TestCmdr", False, "Sol", "Abraham Lincoln", {}, {})
        print("✅ journal_entry() executed successfully")
    except Exception as e:
        print(f"❌ journal_entry() failed: {e}")

    # Test plugin stop
    try:
        plugin_stop()
        print("✅ plugin_stop() executed successfully")
    except Exception as e:
        print(f"❌ plugin_stop() failed: {e}")

    print()
    print("✅ Integration test completed!")

except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
