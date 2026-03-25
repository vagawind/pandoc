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

# Expose WebSocket port
EXPOSE 8765

# Run the server
CMD ["python", "mcp_server.py"]
