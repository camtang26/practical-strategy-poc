from pathlib import Path

def fix_import():
    api_path = Path("agent/api.py")
    content = api_path.read_text()
    
    # Find the imports section and add cleanup_embedder import
    lines = content.split('\n')
    
    # Find where to insert the import (after other local imports)
    insert_index = None
    for i, line in enumerate(lines):
        if line.startswith('from .graph_utils import'):
            insert_index = i + 1
            break
        elif line.startswith('from .') and 'close_graph' in line:
            insert_index = i + 1
            break
    
    if insert_index is None:
        # Find after db_utils imports
        for i, line in enumerate(lines):
            if 'close_database' in line and ')' in lines[i+1]:
                insert_index = i + 2
                break
    
    if insert_index:
        # Add the import
        lines.insert(insert_index, 'from .providers_extended import cleanup_embedder')
        content = '\n'.join(lines)
        api_path.write_text(content)
        print(f"✅ Added import at line {insert_index + 1}")
    else:
        print("❌ Could not find appropriate place to add import")

if __name__ == "__main__":
    fix_import()
