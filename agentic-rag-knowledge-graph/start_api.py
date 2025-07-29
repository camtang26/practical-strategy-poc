#!/usr/bin/env python3
"""Start the API server."""
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Start the API
import uvicorn
from agent.api import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8058)
