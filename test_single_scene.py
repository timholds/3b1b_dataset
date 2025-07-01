#!/usr/bin/env python3
"""
Test a single converted scene to see if the runtime fixes work
"""

import sys
from pathlib import Path

# Test the SimpleText scene with a simple one-liner
scene_file = Path("outputs/2015/inventing-math/validated_snippets/SimpleText.py")

# Add initials function manually for this test
with open(scene_file, 'r') as f:
    content = f.read()

# Insert initials function after imports
lines = content.split('\n')
import_end = None
for i, line in enumerate(lines):
    if line.startswith('# Helper functions'):
        import_end = i
        break

if import_end is not None:
    # Insert initials function
    initials_func = '''
def initials(word_list):
    """Extract first letter of each word from a list of characters"""
    words = ''.join(word_list).split()
    return ''.join([w[0] for w in words if w])
'''
    lines.insert(import_end + 1, initials_func)
    
    # Write modified content
    with open("test_simple_text_fixed.py", 'w') as f:
        f.write('\n'.join(lines))
    
    print("✅ Created test_simple_text_fixed.py with initials function")
    print("🎯 Testing rendering...")
    
    # Try to render it
    import subprocess
    try:
        result = subprocess.run([
            "manim", "test_simple_text_fixed.py", "SimpleText", "-ql", "--output_file", "test_output"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("🎉 SUCCESS! Scene rendered without errors!")
            print("stdout:", result.stdout[-500:])  # Last 500 chars
        else:
            print("❌ Rendering failed:")
            print("stderr:", result.stderr[-500:])  # Last 500 chars
            
    except subprocess.TimeoutExpired:
        print("⏰ Rendering timed out")
    except Exception as e:
        print(f"❌ Error running manim: {e}")
else:
    print("❌ Could not find insertion point for initials function")