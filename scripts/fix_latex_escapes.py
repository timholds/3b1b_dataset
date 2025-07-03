#!/usr/bin/env python3

"""
Fix LaTeX escape sequence issues in validated snippets
Addresses Unicode escape errors in string literals
"""

import os
import re
from typing import List, Tuple

class LaTeXEscapeFixer:
    def __init__(self):
        self.fixes_applied = []
    
    def fix_latex_escapes(self, content: str) -> str:
        """Fix LaTeX escape sequences that cause Unicode errors"""
        fixes = []
        
        # Common LaTeX escape patterns that need raw strings or proper escaping
        patterns_to_fix = [
            # \c followed by letters -> \\c
            (r'\\c([a-z])', r'\\\\c\1'),
            # \p followed by letters -> \\p  
            (r'\\p([a-z])', r'\\\\p\1'),
            # Single backslashes before letters that aren't already escaped
            (r'(?<!\\)\\([a-zA-Z])', r'\\\\\\1'),
            # \U in strings (Unicode escapes) -> \\U
            (r'\\U([0-9A-Fa-f])', r'\\\\U\1'),
            # Other problematic single backslashes
            (r"'([^']*?)\\_([^']*?)'", r"'\1\\\\_\2'"),
            (r'"([^"]*?)\\_(.*?)"', r'"\1\\\\_\2"'),
        ]
        
        for pattern, replacement in patterns_to_fix:
            old_content = content
            content = re.sub(pattern, replacement, content)
            if content != old_content:
                fixes.append(f"Fixed LaTeX escape: {pattern} -> {replacement}")
        
        # Specifically fix the dist_text strings that have issues
        # Look for patterns like 'random\_dist' and fix them
        dist_patterns = [
            (r"'random\\_dist'", r"'random\\\\_dist'"),
            (r"'2\\_adic\\_dist'", r"'2\\\\_adic\\\\_dist'"),
            (r'"random\\_dist"', r'"random\\\\_dist"'),
            (r'"2\\_adic\\_dist"', r'"2\\\\_adic\\\\_dist"'),
        ]
        
        for pattern, replacement in dist_patterns:
            old_content = content
            content = re.sub(pattern, replacement, content)
            if content != old_content:
                fixes.append(f"Fixed dist text pattern: {pattern}")
        
        # Fix LaTeX in list/tuple contexts
        latex_in_lists = re.finditer(r"'([^']*\\[^']*)'", content)
        for match in reversed(list(latex_in_lists)):
            original = match.group(0)
            inner = match.group(1)
            # Double escape all backslashes
            fixed_inner = inner.replace('\\', '\\\\')
            fixed = f"'{fixed_inner}'"
            content = content[:match.start()] + fixed + content[match.end():]
            if fixed != original:
                fixes.append(f"Fixed LaTeX in string: {original[:30]}...")
        
        if fixes:
            self.fixes_applied.extend(fixes)
        
        return content
    
    def fix_file(self, file_path: str) -> Tuple[str, List[str]]:
        """Fix LaTeX escapes in a single file"""
        self.fixes_applied = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return f"Error reading file: {e}", []
        
        original_content = content
        content = self.fix_latex_escapes(content)
        
        if content != original_content:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return f"Fixed {len(self.fixes_applied)} LaTeX issues", self.fixes_applied
            except Exception as e:
                return f"Error writing file: {e}", []
        else:
            return "No LaTeX fixes needed", []
    
    def fix_all_snippets(self, snippets_dir: str) -> dict:
        """Fix LaTeX escapes in all validated snippets"""
        if not os.path.exists(snippets_dir):
            return {"error": f"Directory not found: {snippets_dir}"}
        
        results = {}
        total_fixes = 0
        
        for filename in os.listdir(snippets_dir):
            if filename.endswith('.py'):
                file_path = os.path.join(snippets_dir, filename)
                status, fixes = self.fix_file(file_path)
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
    fixer = LaTeXEscapeFixer()
    
    snippets_dir = "/Users/timholdsworth/code/3b1b_dataset/outputs/2015/inventing-math/validated_snippets"
    
    print("Fixing LaTeX escape sequences in validated snippets...")
    results = fixer.fix_all_snippets(snippets_dir)
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        return
    
    print(f"\nResults:")
    print(f"Files processed: {results['summary']['total_files']}")
    print(f"Files with fixes: {results['summary']['files_with_fixes']}")
    print(f"Total fixes applied: {results['summary']['total_fixes']}")
    
    if results['summary']['files_with_fixes'] > 0:
        print("\nFiles with LaTeX fixes:")
        for filename, result in results.items():
            if filename != 'summary' and result['fix_count'] > 0:
                print(f"  {filename}: {result['fix_count']} fixes")

if __name__ == "__main__":
    main()