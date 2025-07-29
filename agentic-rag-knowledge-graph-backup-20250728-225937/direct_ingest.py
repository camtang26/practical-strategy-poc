#!/usr/bin/env python3
import sys
import os

# Apply Jina patches
from agent.providers_jina_patch import patch_providers
patch_providers()

# Run the ingestion
if __name__ == "__main__":
    sys.argv = ['ingest.py', '--documents', 'documents', '--chunk-size', '800', '--chunk-overlap', '150', '--verbose']
    exec(open('ingestion/ingest.py').read())
