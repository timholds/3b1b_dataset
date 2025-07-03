#!/usr/bin/env python3

"""
Fix validated snippets with syntax and structural issues
Addresses remaining systematic converter problems
"""

import os
import re
import ast
from typing import List, Tuple
import json
from pathlib import Path

class ValidatedSnippetFixer:
    def __init__(self):
        self.fixes_applied = []
        
    def fix_malformed_text_objects(self, content: str) -> str:
        """Fix malformed Text object creation like Text([list]) -> Text(string)"""
        fixes = []
        
        # Fix Text([list of strings]) -> Text(string)
        text_pattern = r'Text\(\[([^\]]+)\]\)'
        matches = list(re.finditer(text_pattern, content))
        
        for match in reversed(matches):  # Process in reverse to maintain positions
            full_match = match.group(0)
            inner_content = match.group(1)
            
            # Extract string elements and join them
            try:
                # Parse the list content more carefully
                if "'" in inner_content or '"' in inner_content:
                    # Extract quoted strings
                    string_parts = re.findall(r'["\']([^"\']*)["\']', inner_content)
                    if string_parts:
                        joined_text = ''.join(string_parts)
                        fixed_text = f'Text("{joined_text}")'
                        content = content[:match.start()] + fixed_text + content[match.end():]
                        fixes.append(f"Fixed malformed Text object: {full_match[:50]}...")
            except Exception as e:
                print(f"Warning: Could not fix Text object {full_match}: {e}")
        
        if fixes:
            self.fixes_applied.extend(fixes)
            
        return content
    
    def fix_hanging_docstrings(self, content: str) -> str:
        """Remove hanging docstring-like content that's not properly formatted"""
        fixes = []
        
        # Pattern for malformed docstring-like content on single lines
        patterns_to_remove = [
            r"'\\nfrom manim import \*\\n\\nSelf-contained scene:.*?'",
            r'"\\nfrom manim import \*\\n\\nSelf-contained scene:.*?"',
            r'"""\\nSelf-contained scene:.*?"""',
            r"'''\\nSelf-contained scene:.*?'''",
        ]
        
        for pattern in patterns_to_remove:
            matches = list(re.finditer(pattern, content, re.DOTALL))
            for match in reversed(matches):
                content = content[:match.start()] + content[match.end():]
                fixes.append(f"Removed hanging docstring: {match.group(0)[:50]}...")
        
        # Also remove standalone string literals that look like comments
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Skip lines that are just string literals (not assignments or function calls)
            if (stripped.startswith("'") and stripped.endswith("'") and 
                '=' not in line and 'def ' not in line and 'class ' not in line):
                fixes.append(f"Removed standalone string literal: {stripped[:50]}...")
                continue
            cleaned_lines.append(line)
        
        if fixes:
            self.fixes_applied.extend(fixes)
            content = '\n'.join(cleaned_lines)
            
        return content
    
    def fix_array_conversion_issues(self, content: str) -> str:
        """Fix invalid array conversion patterns"""
        fixes = []
        
        # Fix .astype('float') on non-numpy arrays
        astype_pattern = r'(\w+)\.astype\(["\']float["\']\)'
        matches = list(re.finditer(astype_pattern, content))
        
        for match in reversed(matches):
            var_name = match.group(1)
            # Replace with proper numpy array conversion
            replacement = f'np.array({var_name}, dtype=float)'
            content = content[:match.start()] + replacement + content[match.end():]
            fixes.append(f"Fixed array conversion for {var_name}")
        
        if fixes:
            self.fixes_applied.extend(fixes)
            
        return content
    
    def remove_duplicate_imports(self, content: str) -> str:
        """Remove duplicate import statements"""
        lines = content.split('\n')
        seen_imports = set()
        cleaned_lines = []
        fixes = []
        
        for line in lines:
            stripped = line.strip()
            
            # Check if it's an import line
            if (stripped.startswith('import ') or stripped.startswith('from ')) and not stripped.startswith('#'):
                if stripped in seen_imports:
                    fixes.append(f"Removed duplicate import: {stripped}")
                    continue
                seen_imports.add(stripped)
            
            cleaned_lines.append(line)
        
        if fixes:
            self.fixes_applied.extend(fixes)
            
        return '\n'.join(cleaned_lines)
    
    def fix_mathtext_usage(self, content: str) -> str:
        """Fix common MathText vs Text usage issues"""
        fixes = []
        
        # Fix Text() with LaTeX content -> MathTex()
        text_with_latex = r'Text\((["\'][^"\']*\\\\[^"\']*["\'])\)'
        matches = list(re.finditer(text_with_latex, content))
        
        for match in reversed(matches):
            latex_content = match.group(1)
            replacement = f'MathTex({latex_content})'
            content = content[:match.start()] + replacement + content[match.end():]
            fixes.append(f"Converted Text with LaTeX to MathTex: {latex_content[:30]}...")
        
        if fixes:
            self.fixes_applied.extend(fixes)
            
        return content
    
    def validate_syntax(self, content: str) -> bool:
        """Check if the content has valid Python syntax"""
        try:
            ast.parse(content)
            return True
        except SyntaxError as e:
            print(f"Syntax error: {e}")
            return False
    
    def fix_snippet(self, file_path: str) -> Tuple[str, List[str]]:
        """Fix a single validated snippet file"""
        self.fixes_applied = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return f"Error reading file: {e}", []
        
        # Apply fixes in order
        original_syntax_valid = self.validate_syntax(content)
        
        content = self.remove_duplicate_imports(content)
        content = self.fix_hanging_docstrings(content)
        content = self.fix_malformed_text_objects(content)
        content = self.fix_array_conversion_issues(content)
        content = self.fix_mathtext_usage(content)
        
        # Validate final syntax
        final_syntax_valid = self.validate_syntax(content)
        
        if self.fixes_applied:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                status = f"Fixed {len(self.fixes_applied)} issues"
                if not original_syntax_valid and final_syntax_valid:
                    status += " - SYNTAX RESTORED"
                elif original_syntax_valid and not final_syntax_valid:
                    status += " - WARNING: SYNTAX BROKEN"
                    
                return status, self.fixes_applied
            except Exception as e:
                return f"Error writing file: {e}", []
        else:
            return "No fixes needed", []
    
    def fix_all_validated_snippets(self, video_path: str) -> dict:
        """Fix all validated snippets for a video"""
        snippets_dir = os.path.join(video_path, 'validated_snippets')
        
        if not os.path.exists(snippets_dir):
            return {"error": f"Validated snippets directory not found: {snippets_dir}"}
        
        results = {}
        total_fixes = 0
        
        for filename in os.listdir(snippets_dir):
            if filename.endswith('.py'):
                file_path = os.path.join(snippets_dir, filename)
                status, fixes = self.fix_snippet(file_path)
                results[filename] = {
                    'status': status,
                    'fixes': fixes,
                    'fix_count': len(fixes)
                }
                total_fixes += len(fixes)
        
        results['summary'] = {
            'total_files': len([f for f in results.keys() if f != 'summary']),
            'total_fixes': total_fixes,
            'files_with_fixes': len([r for r in results.values() if isinstance(r, dict) and r.get('fix_count', 0) > 0])
        }
        
        return results

def main():
    fixer = ValidatedSnippetFixer()
    
    # Fix inventing-math validated snippets
    video_path = "/Users/timholdsworth/code/3b1b_dataset/outputs/2015/inventing-math"
    
    print("Fixing validated snippets for inventing-math...")
    results = fixer.fix_all_validated_snippets(video_path)
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        return
    
    print(f"\nResults:")
    print(f"Files processed: {results['summary']['total_files']}")
    print(f"Files with fixes: {results['summary']['files_with_fixes']}")
    print(f"Total fixes applied: {results['summary']['total_fixes']}")
    
    print("\nDetailed results:")
    for filename, result in results.items():
        if filename != 'summary' and result['fix_count'] > 0:
            print(f"\n{filename}: {result['status']}")
            for fix in result['fixes'][:3]:  # Show first 3 fixes
                print(f"  - {fix}")
            if len(result['fixes']) > 3:
                print(f"  ... and {len(result['fixes']) - 3} more fixes")

if __name__ == "__main__":
    main()