# Fix api.py properly
import re

with open('agent/api.py', 'r') as f:
    content = f.read()

# Add import after other imports
if "from .experimental_error_handler import GlobalErrorHandler" not in content:
    content = content.replace(
        "from .providers import get_llm_client",
        "from .providers import get_llm_client\nfrom .experimental_error_handler import GlobalErrorHandler"
    )

# Find the app creation and add error handler after it
lines = content.split('\n')
for i, line in enumerate(lines):
    if line.strip() == ')' and i > 0 and 'FastAPI(' in lines[i-5:i]:
        # Found the closing of FastAPI constructor
        lines.insert(i+1, "\n# Initialize global error handler")
        lines.insert(i+2, "error_handler = GlobalErrorHandler()")
        break

with open('agent/api.py', 'w') as f:
    f.write('\n'.join(lines))

print("Fixed api.py")
