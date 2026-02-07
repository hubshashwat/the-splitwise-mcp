from splitwise_mcp.server import mcp

# Expose the ASGI app for uvicorn
app = mcp.sse_app
