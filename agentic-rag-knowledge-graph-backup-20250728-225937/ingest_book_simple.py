#!/usr/bin/env python3
"""Simple ingestion script for the Practical Strategy book."""
import asyncio
import sys
import os

# Apply Jina patches first
from agent.providers_jina_patch import patch_providers
patch_providers()

# Now run the main ingestion script
os.system("python3 -m ingestion.ingest --documents documents --chunk-size 800 --chunk-overlap 150 --verbose")
