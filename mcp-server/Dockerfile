FROM python:3.11-alpine

# Install pandoc and necessary packages
RUN apk add --no-cache pandoc

# Create working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the MCP server code
COPY mcp_server.py .

# Expose both HTTP and WebSocket ports
# HTTP MCP (default): 8080, WebSocket MCP: 8765
EXPOSE 8080 8765

# Run the server (default uses HTTP MCP on port 8080, WebSocket on 8765)
CMD ["python", "mcp_server.py"]
