# EDMC Overlay (c) 2020-2025 Ian Norton and Contributors

## About

EDMC Overlay is a robust helper program for Elite: Dangerous that enables programs like EDMC to display overlay messages in the game's DirectX window. This enhanced version includes significant security improvements, performance monitoring, and better error handling.

## ✨ New Features (v0.3.0)

- **🔒 Enhanced Security**: Input validation, rate limiting, and message sanitization
- **📊 Performance Monitoring**: Real-time metrics and performance tracking
- **🛡️ Improved Error Handling**: Better error messages and recovery mechanisms
- **⚙️ Configuration Management**: JSON-based configuration system
- **🧪 Comprehensive Testing**: Full test suite with unit and integration tests
- **🚀 CI/CD Pipeline**: Automated testing and building with GitHub Actions
- **🔧 Modern C# Support**: Updated to .NET 8.0 LTS with latest language features

## Compatibility

* Supports 64-bit Elite: Dangerous (Horizons and Odyssey) on Windows
* Requires .NET 8.0 Runtime for modern C# server components
* 64-bit Non-Horizons should work (YMMV)
* Apple support is not likely (no Mac development environment available)
* Requires "Windowed" or "Borderless Fullscreen" mode
* **New**: Enhanced compatibility with modern Windows versions

## Installation

### Standard Installation
Download the MSI file from the [Releases page](https://github.com/inorton/EDMCOverlay/releases) and run the installer as the same Windows user you use to play Elite: Dangerous.

### Developer Installation
For the enhanced version with new features:

1. Clone the repository
2. Install Python dependencies: `pip install -r requirements.txt` (if available)
3. Use the improved Python client: `from edmcoverlay_improved import Overlay`

## Security & Trust

The installer and server program are digitally signed. EDMCOverlay uses a certificate authority (CA) for code signing.

**CA Certificate Details:**
- Thumbprint: `0c2120b504788afd322dc7c45a8a023ca6850787`
- Location: [edmcoverlay-rootca.cer](https://github.com/inorton/EDMCOverlay/blob/master/edmcoverlay-rootca.cer)

### Security Features (New)
- Input validation and sanitization
- Rate limiting (100 messages/second per client)
- Message size limits (10KB max)
- Command whitelisting
- Connection monitoring and logging

## Quick Start

### Basic Usage (Original API)
```python
import edmcoverlay

# Create overlay client
overlay = edmcoverlay.Overlay()

# Send a message
overlay.send_message("fuel_warning", "You are low on fuel!", "red", 200, 100, 8)

# Send a shape
overlay.send_shape("fuel_bar", "rect", "red", "darkred", 100, 50, 200, 20, 10)
```

### Enhanced Usage (New API)
```python
from edmcoverlay_improved import Overlay
from config import config

# Configure if needed
config.set("server.port", 5011)
config.save()

# Use context manager for automatic cleanup
with Overlay() as overlay:
    overlay.send_message("welcome", "EDMC Ready", "green", 30, 165, 6)
    overlay.send_shape("status", "rect", "blue", "lightblue", 10, 10, 100, 50, 5)
```

### Performance Monitoring
```python
from performance_monitor import get_performance_summary, export_performance_metrics

# Get real-time performance data
stats = get_performance_summary()
print(f"Messages sent: {stats['messages']['total_sent']}")
print(f"Error rate: {stats['errors']['rate_percent']:.2f}%")

# Export metrics for analysis
# Export metrics for analysis
export_performance_metrics("overlay_metrics.json")
```

## Protocol Documentation

EDMC Overlay uses a simple line-based JSON protocol over TCP.

**Connection Details:**
- Default Server: `127.0.0.1:5010`
- Protocol: TCP with newline-delimited JSON messages
- Encoding: UTF-8

### Message Format

#### Text Messages
```json
{
  "id": "unique_message_id",
  "text": "Your message here",
  "color": "red",
  "x": 200,
  "y": 100,
  "ttl": 8,
  "size": "normal"
}
```

#### Shape Messages
```json
{
  "id": "unique_shape_id",
  "shape": "rect",
  "color": "#ff0000",
  "fill": "#800000",
  "x": 100,
  "y": 50,
  "w": 200,
  "h": 20,
  "ttl": 10
}
```

#### Vector Graphics (Advanced)
```json
{
  "id": "vector_id",
  "shape": "vect",
  "color": "#00ff00",
  "ttl": 15,
  "vector": [
    {"x": 100, "y": 200, "color": "#00ff00", "text": "Point A", "marker": "cross"},
    {"x": 200, "y": 300, "color": "#ff0000", "text": "Point B", "marker": "circle"}
  ]
}
```

### Supported Values

**Colors:**
- Named colors: `"red"`, `"green"`, `"yellow"`, `"blue"`, `"white"`, `"black"`
- Hex colors: `"#rrggbb"` (e.g., `"#ff0000"` for red)

**Sizes:**
- `"normal"`: Standard text size
- `"large"`: Larger text size

**Shapes:**
- `"rect"`: Rectangle
- `"vect"`: Vector graphics with multiple points

**Commands:**
```json
{"command": "exit"}    // Shutdown server
{"command": "clear"}   // Clear all graphics
{"command": "status"}  // Get server status
```

## Configuration

### Python Configuration
Create `edmcoverlay_config.json`:
```json
{
  "server": {
    "address": "127.0.0.1",
    "port": 5010,
    "timeout": 10.0,
    "reconnect_attempts": 3
  },
  "security": {
    "max_message_length": 1000,
    "allowed_commands": ["exit", "clear", "status"]
  },
  "logging": {
    "level": "INFO"
  }
}
```

### Environment Variables
- `EDMCOVERLAY_PORT`: Override default port
- `EDMCOVERLAY_DEBUG`: Enable debug logging

## Testing

### Run Unit Tests
```bash
# Run all tests
python test_comprehensive.py

# Run with performance tests
python test_comprehensive.py --performance

# Run specific test categories
python -m pytest test_comprehensive.py::TestOverlayConnection -v
```

### Manual Testing
```python
# Test the improved overlay
python -c "
from edmcoverlay_improved import Overlay
with Overlay() as overlay:
    overlay.send_message('test', 'Hello World!', 'green', 100, 100, 5)
    print('Test message sent successfully')
"
```

## Development

### Build Requirements
- **Python**: 3.11+ with packages: `json`, `socket`, `threading`
- **C#**: .NET 8.0 LTS SDK
- **Tools**: Visual Studio 2022 or VS Code with C# extension

### Building
```bash
# Build modern C# application (.NET 8.0)
cd EDMCOverlay/EDMCOverlay
dotnet build EDMCOverlay_Modern.csproj --configuration Release

# Run Python tests
python -m pytest test_comprehensive.py

# Build with full optimizations
dotnet publish EDMCOverlay_Modern.csproj --configuration Release --self-contained false
```

### Contributing
1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes with tests
4. Run the full test suite: `python test_comprehensive.py`
5. Submit a pull request

### Code Quality
The project uses:
- **Python**: Type hints, proper error handling, comprehensive tests
- **C#**: .NET 6.0+, nullable reference types, modern async patterns
- **CI/CD**: GitHub Actions for automated testing and building

## Troubleshooting

### Common Issues

**Connection Refused**
```
Error: Connection refused by overlay server at 127.0.0.1:5010
```
- Ensure Elite: Dangerous is running
- Check if another program is using port 5010
- Verify EDMCOverlay.exe is in the correct location

**Permission Denied**
```
Error: Permission denied starting overlay server
```
- Run EDMC as administrator
- Check Windows Defender / antivirus settings
- Verify EDMCOverlay.exe is not blocked

**High Error Rate**
```
Error rate: 15.23%
```
- Check network stability
- Reduce message frequency
- Review performance metrics: `export_performance_metrics()`

### Debug Mode
```python
from config import config
import logging

# Enable debug logging
config.set("logging.level", "DEBUG")
logging.basicConfig(level=logging.DEBUG)

# Test with verbose output
from edmcoverlay_improved import Overlay
overlay = Overlay()
overlay.connect()  # Will show detailed connection info
```

## Migration Guide

### From v0.2.x to v0.3.x

**Backward Compatibility**: All existing code continues to work unchanged.

**New Features** (Optional):
```python
# Old way (still works)
import edmcoverlay
overlay = edmcoverlay.Overlay()
overlay.send_message("id", "text", "color", x, y)

# New enhanced way
from edmcoverlay_improved import Overlay
with Overlay() as overlay:  # Automatic cleanup
    overlay.send_message("id", "text", "color", x, y)
```

**Performance Monitoring** (New):
```python
from performance_monitor import monitor_operation, get_performance_summary

# Monitor specific operations
with monitor_operation("fuel_check", "message"):
    overlay.send_message("fuel", "Low fuel", "red", 100, 100)

# Get performance data
stats = get_performance_summary()
```

## License

**MIT License**

Copyright (c) 2020-2025 Ian Norton and Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Changelog

### v0.4.0 (2025-10-25) - .NET 8.0 LTS Update
- 🚀 **Major**: Upgraded to .NET 8.0 LTS for long-term support
- ✨ **New**: Modern C# features (Source Generators, Global Using, File-scoped namespaces)
- ✨ **New**: Enhanced SecureOverlayJsonServer with .NET 8.0 optimizations
- ✨ **New**: System.Text.Json for better performance over Newtonsoft.Json
- ✨ **New**: IHostedService pattern for proper service lifecycle management
- ✨ **New**: Built-in dependency injection and configuration management
- 🔧 **Improved**: NuGet packages updated to latest versions
- 🔧 **Improved**: CI/CD pipeline updated for .NET 8.0 and Python 3.12
- 🔧 **Improved**: Performance optimizations with compiled regex patterns
- 📊 **Enhanced**: Better performance metrics and monitoring

### v0.3.0 (2025-10-25)
- ✨ **New**: Enhanced security with input validation and rate limiting
- ✨ **New**: Performance monitoring and metrics collection
- ✨ **New**: Improved error handling with specific exception types
- ✨ **New**: Configuration management system
- ✨ **New**: Comprehensive test suite
- ✨ **New**: GitHub Actions CI/CD pipeline
- 🔧 **Improved**: Modern C# project structure (.NET 6.0+)
- 🔧 **Improved**: Thread-safe operations
- 🔧 **Improved**: Resource management with context managers
- 🐛 **Fixed**: Duplicate method definition in edmcoverlay.py
- 🐛 **Fixed**: Various spelling errors in documentation

### v0.2.5.2 (Previous)
- Original stable release
- Basic overlay functionality
- Windows-only support
```

# Protocol

EDMC Overlay offers a very very simple line-json based network protocol.

The service when started will listen on TCP 127.0.0.1:5010.  If EDMCOverlay cannot
detect EliteDangerous64.exe it will exit silently.
 
Assuming EliteDangerous64.exe is running, you may send a single JSON message (on one line)
Like so:

```
{"id": "test1", "text": "You are low on fuel!", "size": "normal", "color": "red", "x": 200, "y": 100, "ttl": 8}
```
Supported colors values are:
 "red", "green", "yellow", "blue" or "#rrggbb".

Supported size values are: 
 "normal" and "large"

Additionally, you may draw rectangles by setting the "shape" to "rect" and setting the "color" and/or "fill" values.

```
{"id": "fred", "shape": "rect", "x": 100, "y": 10, "w": 30:, "h": 5, "fill": "red", "color", "#ccff00"}
```

The server will process this as an instruction to display the message "You are low on fuel!"
in red text at 200,100 for 8 seconds.
 
Be sure to send a newline ("\n") character after your message. You may need to flush the 
socket.

There are (currently) no response values from the service.

