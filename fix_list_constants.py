#!/usr/bin/env python3
"""
Fix MathTex list constants across all snippets
"""

import os
import re

def fix_list_constants():
    snippets_dir = '/Users/timholdsworth/code/3b1b_dataset/outputs/2015/inventing-math/validated_snippets'
    fixed_count = 0

    for filename in os.listdir(snippets_dir):
        if filename.endswith('.py'):
            filepath = os.path.join(snippets_dir, filename)
            
            with open(filepath, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Fix MathTex(CONSTANT) patterns
            for constant in ['DIVERGENT_SUM_TEXT', 'CONVERGENT_SUM_TEXT', 'PARTIAL_CONVERGENT_SUMS_TEXT', 'CONVERGENT_SUM_TERMS', 'ALT_PARTIAL_SUM_TEXT']:
                # Replace MathTex(CONSTANT) with MathTex(''.join(CONSTANT))
                pattern = rf'\bMathTex\s*\(\s*{constant}\s*\)'
                replacement = f"MathTex(''.join({constant}))"
                content = re.sub(pattern, replacement, content)
                
                # Also handle cases with additional arguments
                pattern = rf'\bMathTex\s*\(\s*{constant}\s*,'
                replacement = f"MathTex(''.join({constant}),"
                content = re.sub(pattern, replacement, content)
            
            if content != original_content:
                with open(filepath, 'w') as f:
                    f.write(content)
                fixed_count += 1
                print(f'Fixed {filename}')

    print(f'Fixed {fixed_count} files')

if __name__ == '__main__':
    fix_list_constants()