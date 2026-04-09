#!/usr/bin/env python3
"""
Test script for Pandoc MCP server with HTTP and WebSocket support.
"""

import asyncio
import json
import aiohttp
import websockets
import time
import sys
import subprocess

async def test_http_server():
    """Test HTTP MCP server."""
    print("Testing HTTP MCP server...")
    
    # Test data
    test_data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "version",
        "params": {}
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post('http://localhost:8080/', 
                                  json=test_data,
                                  timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"HTTP Server Response: {json.dumps(result, indent=2)}")
                    return True
                else:
                    print(f"HTTP Server Error: Status {response.status}")
                    return False
    except Exception as e:
        print(f"HTTP Server Test Failed: {e}")
        return False

async def test_websocket_server():
    """Test WebSocket MCP server."""
    print("Testing WebSocket MCP server...")
    
    # Test data
    test_data = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "list_methods",
        "params": {}
    }
    
    try:
        async with websockets.connect('ws://localhost:8765', timeout=5) as websocket:
            await websocket.send(json.dumps(test_data))
            response = await websocket.recv()
            result = json.loads(response)
            print(f"WebSocket Server Response: {json.dumps(result, indent=2)}")
            return True
    except Exception as e:
        print(f"WebSocket Server Test Failed: {e}")
        return False

async def test_convert_method():
    """Test convert method via HTTP."""
    print("Testing convert method via HTTP...")
    
    test_data = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "convert",
        "params": {
            "text": "# Hello World\n\nThis is a test.",
            "from": "markdown",
            "to": "html",
            "standalone": False
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post('http://localhost:8080/', 
                                  json=test_data,
                                  timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"Convert Response: {json.dumps(result, indent=2)}")
                    
                    # Check if conversion was successful
                    if 'result' in result and result['result'].get('status') == 'success':
                        print("Convert test PASSED")
                        return True
                    else:
                        print("Convert test FAILED - No successful conversion")
                        return False
                else:
                    print(f"Convert Test Error: Status {response.status}")
                    return False
    except Exception as e:
        print(f"Convert Test Failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("Starting Pandoc MCP Server Tests")
    print("=" * 50)
    
    # Check if pandoc is available
    try:
        result = subprocess.run(["pandoc", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Pandoc found: {result.stdout.split()[1]}")
        else:
            print("Pandoc not found or not working properly")
    except FileNotFoundError:
        print("Pandoc not installed - server will use mock conversions")
    
    # Start server in background (for testing, we assume it's already running)
    print("\nNote: Ensure the MCP server is running before tests")
    print("To start server: python mcp_server.py")
    print("=" * 50)
    
    # Run tests
    http_ok = await test_http_server()
    ws_ok = await test_websocket_server()
    convert_ok = await test_convert_method()
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY:")
    print(f"HTTP Server: {'PASS' if http_ok else 'FAIL'}")
    print(f"WebSocket Server: {'PASS' if ws_ok else 'FAIL'}")
    print(f"Convert Method: {'PASS' if convert_ok else 'FAIL'}")
    
    if http_ok and ws_ok and convert_ok:
        print("\nAll tests PASSED! ✓")
        return 0
    else:
        print("\nSome tests FAILED! ✗")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
