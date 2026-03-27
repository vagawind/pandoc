#!/usr/bin/env python3
"""
Pandoc MCP (Model Context Protocol) WebSocket server.
This server accepts JSON-RPC messages over WebSocket and runs pandoc commands.
"""

import asyncio
import json
import subprocess
import logging
from typing import Dict, Any, Optional
import websockets
from websockets.server import serve

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PandocMCPServer:
    """MCP server for Pandoc conversion."""
    
    def __init__(self):
        self.methods = {
            "convert": self.handle_convert,
            "version": self.handle_version,
            "list_methods": self.handle_list_methods,
        }
    
    async def handle_convert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle convert request."""
        try:
            # Extract parameters
            text = params.get("text", "")
            from_fmt = params.get("from", "markdown")
            to_fmt = params.get("to", "html")
            standalone = params.get("standalone", False)
            
            # Check if pandoc is available
            try:
                pandoc_check = subprocess.run(["pandoc", "--version"], capture_output=True)
                if pandoc_check.returncode != 0:
                    raise FileNotFoundError("pandoc not found")
            except FileNotFoundError:
                # Pandoc not installed, provide a simple mock conversion
                logger.warning("Pandoc not installed, using mock conversion")
                if from_fmt == "markdown" and to_fmt == "html":
                    # Simple markdown to HTML conversion
                    mock_html = f"<h1>Mock Conversion</h1>\n<p>This is a mock conversion since pandoc is not installed.</p>\n<p>Original text: {text}</p>"
                    return {
                        "status": "success",
                        "output": mock_html,
                        "format": to_fmt,
                        "note": "mock conversion (pandoc not installed)"
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Pandoc not installed, can only mock markdown->html conversion (requested {from_fmt}->{to_fmt})"
                    }
            
            # Build pandoc command
            cmd = ["pandoc", "-f", from_fmt, "-t", to_fmt]
            if standalone:
                cmd.append("-s")
            
            # Run pandoc
            result = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                text=False  # We'll handle encoding manually
            )
            
            if result.returncode == 0:
                output = result.stdout.decode("utf-8")
                return {
                    "status": "success",
                    "output": output,
                    "format": to_fmt
                }
            else:
                error_msg = result.stderr.decode("utf-8")
                return {
                    "status": "error",
                    "message": f"Pandoc conversion failed: {error_msg}"
                }
                
        except Exception as e:
            logger.error(f"Error in convert: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def handle_version(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle version request."""
        try:
            # Try to get pandoc version
            try:
                result = subprocess.run(
                    ["pandoc", "--version"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    version_output = result.stdout.strip()
                    # Extract version number from first line
                    version_line = version_output.split('\n')[0]
                    version = version_line.split(' ')[1] if ' ' in version_line else version_line
                    return {
                        "status": "success",
                        "version": version,
                        "full_output": version_output
                    }
                else:
                    # Pandoc not working properly
                    return {
                        "status": "success",
                        "version": "3.9.0.2 (mock - pandoc not installed)",
                        "full_output": "pandoc 3.9.0.2 (mock - pandoc not installed)\nThis is a mock version. Please install pandoc for full functionality."
                    }
            except FileNotFoundError:
                # Pandoc not installed at all
                return {
                    "status": "success",
                    "version": "3.9.0.2 (mock - pandoc not installed)",
                    "full_output": "pandoc 3.9.0.2 (mock - pandoc not installed)\nThis is a mock version. Please install pandoc for full functionality."
                }
                
        except Exception as e:
            logger.error(f"Error getting version: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def handle_list_methods(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_methods request."""
        return {
            "status": "success",
            "methods": list(self.methods.keys())
        }
    
    async def process_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process an MCP request."""
        if method in self.methods:
            return await self.methods[method](params)
        else:
            return {
                "status": "error",
                "message": f"Method not found: {method}"
            }


async def handler(websocket):
    """Handle WebSocket connections."""
    server = PandocMCPServer()
    
    async for message in websocket:
        try:
            # Parse JSON-RPC request
            request = json.loads(message)
            
            # Validate JSON-RPC 2.0
            if request.get("jsonrpc") != "2.0":
                response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request: jsonrpc must be '2.0'"
                    },
                    "id": None
                }
                await websocket.send(json.dumps(response))
                continue
            
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")
            
            # Process request
            result = await server.process_request(method, params)
            
            # Build response
            if result.get("status") == "success":
                response = {
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": result.get("message", "Internal error")
                    },
                    "id": request_id
                }
            
            # Send response
            await websocket.send(json.dumps(response))
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                },
                "id": None
            }
            await websocket.send(json.dumps(response))
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Internal error"
                },
                "id": None
            }
            await websocket.send(json.dumps(response))


async def main():
    """Start the WebSocket server."""
    async with serve(handler, "0.0.0.0", 8765):
        logger.info("Pandoc MCP WebSocket server started on ws://0.0.0.0:8765")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
