#!/usr/bin/env python3

"""
Fix remaining specific issues in validated snippets
"""

import os
import re
from typing import List, Tuple

class RemainingIssuesFixer:
    def __init__(self):
        self.fixes_applied = []
    
    def fix_text_objects(self, content: str) -> str:
        """Fix specific text object malformation issues"""
        fixes = []
        
        # Fix YouJustInventedSomeMath.py Text with malformed newline
        old_text = "Text('You  just  invented\\\\\\\\\\1 some  math')"
        new_text = "Text('You just invented\\nsome math')"
        if old_text in content:
            content = content.replace(old_text, new_text)
            fixes.append("Fixed YouJustInventedSomeMath text object")
        
        # Fix DistanceIsAFunction.py malformed Text tuple
        old_pattern = r'\(dist, r_paren, arg0, comma, arg1, l_paren, equals, result\) = \[Text\(".*?"\)\]'
        if re.search(old_pattern, content):
            # Replace with proper individual Text objects
            replacement = '''dist = Text(dist_text)
        r_paren = Text("(")
        arg0 = Text("000")
        comma = Text(",")
        arg1 = Text("000")
        l_paren = Text(")")
        equals = Text("=")
        result = Text("000")'''
            content = re.sub(old_pattern, replacement, content)
            fixes.append("Fixed DistanceIsAFunction Text tuple unpacking")
        
        if fixes:
            self.fixes_applied.extend(fixes)
        
        return content
    
    def fix_over_escaped_variables(self, content: str) -> str:
        """Fix over-escaped string variables"""
        fixes = []
        
        # Fix over-escaped dist_text variables
        replacements = [
            ("'random\\\\\\\\_dist'", "'random_dist'"),
            ("'2\\\\\\\\_adic\\\\_dist'", "'2_adic_dist'"),
        ]
        
        for old, new in replacements:
            if old in content:
                content = content.replace(old, new)
                fixes.append(f"Fixed over-escaped variable: {old} -> {new}")
        
        if fixes:
            self.fixes_applied.extend(fixes)
        
        return content
    
    def fix_malformed_latex_strings(self, content: str) -> str:
        """Fix remaining malformed LaTeX strings"""
        fixes = []
        
        # Fix specific patterns that are still problematic
        patterns = [
            # Fix newline escapes that got mangled
            (r'\\\\\\\\\\1', r'\\n'),
            (r'\\\\\\\\\\n', r'\\n'),
            # Fix excessive backslashes in LaTeX
            (r'\\\\\\\\frac', r'\\\\frac'),
            (r'\\\\\\\\quad', r'\\\\quad'),
            (r'\\\\\\\\cdots', r'\\\\cdots'),
        ]
        
        for pattern, replacement in patterns:
            old_content = content
            content = re.sub(pattern, replacement, content)
            if content != old_content:
                fixes.append(f"Fixed LaTeX pattern: {pattern}")
        
        if fixes:
            self.fixes_applied.extend(fixes)
        
        return content
    
    def fix_file(self, file_path: str) -> Tuple[str, List[str]]:
        """Fix remaining issues in a single file"""
        self.fixes_applied = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return f"Error reading file: {e}", []
        
        original_content = content
        content = self.fix_text_objects(content)
        content = self.fix_over_escaped_variables(content)
        content = self.fix_malformed_latex_strings(content)
        
        if content != original_content:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return f"Fixed {len(self.fixes_applied)} remaining issues", self.fixes_applied
            except Exception as e:
                return f"Error writing file: {e}", []
        else:
            return "No remaining issues found", []
    
    def fix_all_snippets(self, snippets_dir: str) -> dict:
        """Fix remaining issues in all validated snippets"""
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
    fixer = RemainingIssuesFixer()
    
    snippets_dir = "/Users/timholdsworth/code/3b1b_dataset/outputs/2015/inventing-math/validated_snippets"
    
    print("Fixing remaining issues in validated snippets...")
    results = fixer.fix_all_snippets(snippets_dir)
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        return
    
    print(f"\nResults:")
    print(f"Files processed: {results['summary']['total_files']}")
    print(f"Files with fixes: {results['summary']['files_with_fixes']}")
    print(f"Total fixes applied: {results['summary']['total_fixes']}")
    
    if results['summary']['files_with_fixes'] > 0:
        print("\nFiles with remaining fixes:")
        for filename, result in results.items():
            if filename != 'summary' and result['fix_count'] > 0:
                print(f"  {filename}: {result['status']}")
                for fix in result['fixes']:
                    print(f"    - {fix}")

if __name__ == "__main__":
    main()