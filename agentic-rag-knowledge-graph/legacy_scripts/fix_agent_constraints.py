# Fix to allow more flexible search constraints
import fileinput
import sys

# Read the file
with open('agent/agent.py', 'r') as f:
    content = f.read()

# Replace the constraint check in hybrid_search to be more lenient
old_code = '''    # Enforce search_type constraint
    if ctx.deps.search_type and ctx.deps.search_type not in ["hybrid", None]:
        logger.warning(f"hybrid_search called but search_type is {ctx.deps.search_type}")
        return []'''

new_code = '''    # Log search_type mismatch but allow search to proceed
    if ctx.deps.search_type and ctx.deps.search_type not in ["hybrid", None]:
        logger.warning(f"hybrid_search called but search_type is {ctx.deps.search_type}")
        # Continue with search anyway to avoid empty results'''

content = content.replace(old_code, new_code)

# Write back
with open('agent/agent.py', 'w') as f:
    f.write(content)

print("Fixed agent constraints to be more flexible")
