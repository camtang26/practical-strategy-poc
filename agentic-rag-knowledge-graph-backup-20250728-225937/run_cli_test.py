#!/usr/bin/env python3
"""Test the CLI with automated queries to demonstrate tool selection."""

import subprocess
import time
import sys

def run_cli_with_query(query):
    """Run CLI with a specific query and capture output."""
    print(f"\n{'='*60}")
    print(f"Sending query: {query}")
    print('='*60)
    
    # Create input for the CLI
    cli_input = f"{query}\nexit\n"
    
    # Run the CLI with the input
    process = subprocess.Popen(
        ['python3', 'cli.py'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd='/opt/practical-strategy-poc/agentic-rag-knowledge-graph'
    )
    
    # Send input and get output
    stdout, stderr = process.communicate(input=cli_input)
    
    # Print the output
    print("CLI Output:")
    print(stdout)
    if stderr:
        print("Errors:")
        print(stderr)
    
    return stdout

# Test queries
queries = [
    # Vector search query
    "What are the 6 myths of strategy?",
    
    # Graph search query  
    "Show me relationships between CEO and strategic planning",
    
    # Hybrid query
    "How does the Practical Strategy methodology implement cause-and-effect thinking across all perspectives?"
]

print("Running CLI tests with different query types...")

for query in queries:
    output = run_cli_with_query(query)
    time.sleep(2)  # Brief pause between queries

print("\nCLI tests completed!")
