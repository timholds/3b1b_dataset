#!/usr/bin/env python3

"""
Fix specific runtime errors identified from rendering logs
These are the blocking issues preventing video generation
"""

import os
import re
from typing import List, Tuple

class RuntimeErrorFixer:
    def __init__(self):
        self.fixes_applied = []
    
    def fix_center_method_calls(self, content: str) -> str:
        """Fix .center + ... where center should be .get_center()"""
        fixes = []
        
        # Pattern: .center + something (where center should be a method call)
        center_pattern = r'(\w+)\.center(\s*\+)'
        matches = list(re.finditer(center_pattern, content))
        
        for match in reversed(matches):  # Process in reverse to maintain positions
            var_name = match.group(1)
            operator = match.group(2)
            replacement = f'{var_name}.get_center(){operator}'
            content = content[:match.start()] + replacement + content[match.end():]
            fixes.append(f"Fixed center method call for {var_name}")
        
        if fixes:
            self.fixes_applied.extend(fixes)
        
        return content
    
    def fix_fstring_backslashes(self, content: str) -> str:
        """Fix f-strings containing backslashes (not allowed in Python)"""
        fixes = []
        
        # Find f-strings with backslashes
        fstring_pattern = r'f"([^"]*\\[^"]*)"'
        matches = list(re.finditer(fstring_pattern, content))
        
        for match in reversed(matches):
            original = match.group(0)
            inner_content = match.group(1)
            
            # Convert to regular string formatting
            # Replace the f-string with a regular string
            if '\\\\\\1nderbrace' in inner_content:
                # This is a malformed pattern - fix it
                fixed = 'r"\\\\Underbrace{%s}" % (14*\'\\\\quad\')'
                content = content[:match.start()] + fixed + content[match.end():]
                fixes.append(f"Fixed malformed f-string with backslashes: {original[:30]}...")
            else:
                # Generic f-string with backslashes - convert to format string
                fixed_inner = inner_content.replace('\\\\', '\\\\\\\\')
                fixed = f'"{fixed_inner}"'
                content = content[:match.start()] + fixed + content[match.end():]
                fixes.append(f"Fixed f-string with backslashes: {original[:30]}...")
        
        if fixes:
            self.fixes_applied.extend(fixes)
        
        return content
    
    def fix_latex_compilation_errors(self, content: str) -> str:
        """Fix LaTeX compilation errors"""
        fixes = []
        
        # Fix missing braces in LaTeX
        latex_fixes = [
            # Fix sum expressions missing braces
            (r"'\\\\sum_\\{([^}]+)\\}\\^\\\\infty", r"'\\\\sum_{\\1}^{\\\\infty}"),
            # Fix other missing braces
            (r'\\\\frac\\{([^}]+)\\}\\{([^}]+)\\}', r'\\\\frac{\\1}{\\2}'),
        ]
        
        for pattern, replacement in latex_fixes:
            old_content = content
            content = re.sub(pattern, replacement, content)
            if content != old_content:
                fixes.append(f"Fixed LaTeX braces: {pattern}")
        
        if fixes:
            self.fixes_applied.extend(fixes)
        
        return content
    
    def fix_points_attribute_access(self, content: str) -> str:
        """Fix .points[0] access which should be .get_start()"""
        fixes = []
        
        # Fix .points[0] -> .get_start()
        points_pattern = r'(\w+)\.points\[0\]'
        matches = list(re.finditer(points_pattern, content))
        
        for match in reversed(matches):
            var_name = match.group(1)
            replacement = f'{var_name}.get_start()'
            content = content[:match.start()] + replacement + content[match.end():]
            fixes.append(f"Fixed points[0] access for {var_name}")
        
        if fixes:
            self.fixes_applied.extend(fixes)
        
        return content
    
    def fix_astype_array_errors(self, content: str) -> str:
        """Fix .astype('float') on non-numpy arrays"""
        fixes = []
        
        # Fix curr = left.astype('float') pattern
        astype_pattern = r'(\w+) = (\w+)\.astype\(["\']float["\']\)'
        matches = list(re.finditer(astype_pattern, content))
        
        for match in reversed(matches):
            var_name = match.group(1)
            source_var = match.group(2)
            replacement = f'{var_name} = np.array({source_var}, dtype=float)'
            content = content[:match.start()] + replacement + content[match.end():]
            fixes.append(f"Fixed astype array conversion for {var_name}")
        
        if fixes:
            self.fixes_applied.extend(fixes)
        
        return content
    
    def fix_file(self, file_path: str) -> Tuple[str, List[str]]:
        """Fix runtime errors in a single file"""
        self.fixes_applied = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return f"Error reading file: {e}", []
        
        original_content = content
        
        # Apply fixes in order
        content = self.fix_center_method_calls(content)
        content = self.fix_fstring_backslashes(content)
        content = self.fix_latex_compilation_errors(content)
        content = self.fix_points_attribute_access(content)
        content = self.fix_astype_array_errors(content)
        
        if content != original_content:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return f"Fixed {len(self.fixes_applied)} runtime errors", self.fixes_applied
            except Exception as e:
                return f"Error writing file: {e}", []
        else:
            return "No runtime errors found", []
    
    def fix_all_snippets(self, snippets_dir: str) -> dict:
        """Fix runtime errors in all validated snippets"""
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
    fixer = RuntimeErrorFixer()
    
    snippets_dir = "/Users/timholdsworth/code/3b1b_dataset/outputs/2015/inventing-math/validated_snippets"
    
    print("Fixing runtime errors in validated snippets...")
    results = fixer.fix_all_snippets(snippets_dir)
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        return
    
    print(f"\nResults:")
    print(f"Files processed: {results['summary']['total_files']}")
    print(f"Files with fixes: {results['summary']['files_with_fixes']}")
    print(f"Total fixes applied: {results['summary']['total_fixes']}")
    
    if results['summary']['files_with_fixes'] > 0:
        print("\nFiles with runtime fixes:")
        for filename, result in results.items():
            if filename != 'summary' and result['fix_count'] > 0:
                print(f"  {filename}: {result['status']}")
                for fix in result['fixes']:
                    print(f"    - {fix}")

if __name__ == "__main__":
    main()