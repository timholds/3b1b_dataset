#!/usr/bin/env python3
import os
import re
import glob

# Fix patterns for common syntax errors
fixes = [
    # Fix extra closing parenthesis in Underbrace - both single and double backslash patterns
    (r'result = MathTex\("\\\\Underbrace\{%s\}"\) % \(14 \* \'\\\\quad\'\)\)', r'result = MathTex(r"\\Underbrace{%s}" % (14 * \'\\quad\'))'),
    (r'result = MathTex\("\\\\\\\\Underbrace\{%s\}"\) % \(14 \* \'\\\\\\\\quad\'\)\)', r'result = MathTex(r"\\Underbrace{%s}" % (14 * \'\\quad\'))'),
    (r'result = MathTex\("\\\\Underbrace\{%s\}"\) % \(14 \* \'\\\\quad\'\)\)', r'result = MathTex(r"\\Underbrace{%s}" % (14 * \'\\quad\'))'),
    
    # Fix fraction syntax errors
    (r'MathTex\("\\\\\\\\frac\{%d\}\{%d\}"\) % pair\)', r'MathTex(r"\\frac{%d}{%d}" % pair)'),
    (r'fraction = MathTex\("\\\\\\\\frac\{%d\}\{%d\}"\) % pair\)\.shift', r'fraction = MathTex(r"\\frac{%d}{%d}" % pair).shift'),
]

# Change to the snippets directory
os.chdir('/Users/timholdsworth/code/3b1b_dataset/outputs/2015/inventing-math/validated_snippets')

for filename in glob.glob('*.py'):
    try:
        with open(filename, 'r') as f:
            content = f.read()
        
        original_content = content
        for pattern, replacement in fixes:
            content = re.sub(pattern, replacement, content)
        
        if content != original_content:
            with open(filename, 'w') as f:
                f.write(content)
            print(f'Fixed: {filename}')
    except Exception as e:
        print(f'Error processing {filename}: {e}')

print("Done!")