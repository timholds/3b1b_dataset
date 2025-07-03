#!/usr/bin/env python3

"""
Comprehensive fix for all critical runtime errors
Applies fixes robustly to address rendering failures
"""

import os
import re
from typing import List, Tuple

class ComprehensiveRuntimeFixer:
    def __init__(self):
        self.fixes_applied = []
    
    def fix_all_critical_errors(self, content: str, filename: str) -> str:
        """Apply all critical runtime fixes"""
        fixes = []
        
        # 1. Fix .center property access -> .get_center() method calls
        center_patterns = [
            (r'(\w+)\.center(\s*\+)', r'\1.get_center()\2'),
            (r'(\w+)\.center(\s*-)', r'\1.get_center()\2'),
            (r'(\w+)\.center(\s*\))', r'\1.get_center()\2'),
            (r'Point\(([^)]+)\.center\)', r'Point(\1.get_center())'),
        ]
        
        for pattern, replacement in center_patterns:
            old_content = content
            content = re.sub(pattern, replacement, content)
            if content != old_content:
                fixes.append(f"Fixed .center access in {filename}")
        
        # 2. Fix .astype('float') -> np.array(var, dtype=float)
        astype_pattern = r'(\w+)\.astype\(["\']float["\']\)'
        matches = list(re.finditer(astype_pattern, content))
        for match in reversed(matches):
            var_name = match.group(1)
            replacement = f'np.array({var_name}, dtype=float)'
            content = content[:match.start()] + replacement + content[match.end():]
            fixes.append(f"Fixed astype array conversion for {var_name}")
        
        # 3. Fix malformed f-strings with backslashes
        content = re.sub(r'f"([^"]*\\[^"]*)"', r'r"\1"', content)
        
        # 4. Fix specific file issues
        if filename == 'DistanceIsAFunction.py':
            content = self.fix_distance_function_specific(content)
        elif filename == 'ChopIntervalInProportions.py':
            content = self.fix_chop_interval_specific(content)
        elif filename == 'OneAndInfiniteSumAreTheSameThing.py':
            content = self.fix_infinite_sum_specific(content)
        
        if fixes:
            self.fixes_applied.extend(fixes)
        
        return content
    
    def fix_distance_function_specific(self, content: str) -> str:
        """Fix specific issues in DistanceIsAFunction.py"""
        # Ensure proper tuple unpacking for Text objects
        text_tuple_pattern = r'(dist, r_paren, arg0, comma, arg1, l_paren, equals, result) = Text\([^)]+\)'
        if re.search(text_tuple_pattern, content):
            replacement = '''dist = Text(dist_text)
        r_paren = Text('(')
        arg0 = Text('000')
        comma = Text(',')
        arg1 = Text('000')
        l_paren = Text(')')
        equals = Text('=')
        result = Text('000')'''
            content = re.sub(text_tuple_pattern, replacement, content)
        
        return content
    
    def fix_chop_interval_specific(self, content: str) -> str:
        """Fix specific issues in ChopIntervalInProportions.py"""
        # Fix the curr = left.astype('float') line specifically
        content = re.sub(r'curr = left\.astype\(["\']float["\']\)', 'curr = np.array(left, dtype=float)', content)
        return content
    
    def fix_infinite_sum_specific(self, content: str) -> str:
        """Fix specific issues in OneAndInfiniteSumAreTheSameThing.py"""
        # Remove duplicate class definitions and fix the scene
        if 'class OneAndInfiniteSumAreTheSameThing(Scene):' in content:
            # Replace the entire problematic section
            pattern = r'class OneAndInfiniteSumAreTheSameThing\(Scene\):.*?def construct\(self\):.*?(?=class OneAndInfiniteSumAreTheSameThing\(Scene\):|$)'
            replacement = '''class OneAndInfiniteSumAreTheSameThing(Scene):
    def construct(self):
        # Create the equation elements
        one = MathTex("1")
        equals = MathTex("=")
        inf_sum = MathTex(r"\\sum_{{n=1}}^{{\\infty}} \\frac{{1}}{{2^n}}")
        
        # Position elements
        one.shift(LEFT)
        inf_sum.shift(RIGHT)
        
        # Add elements and animate
        self.add(one)
        self.wait()
        self.add(inf_sum)
        self.wait()
        self.play(FadeIn(equals))
        self.wait()'''
            
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
            
            # Remove any remaining duplicate classes
            lines = content.split('\n')
            cleaned_lines = []
            in_duplicate_class = False
            class_count = 0
            
            for line in lines:
                if 'class OneAndInfiniteSumAreTheSameThing(Scene):' in line:
                    class_count += 1
                    if class_count > 1:
                        in_duplicate_class = True
                        continue
                    else:
                        in_duplicate_class = False
                
                if in_duplicate_class:
                    # Skip lines that are part of duplicate class
                    if line.strip() and not line.startswith('    ') and not line.startswith('\t'):
                        in_duplicate_class = False
                        cleaned_lines.append(line)
                    continue
                
                cleaned_lines.append(line)
            
            content = '\n'.join(cleaned_lines)
        
        return content
    
    def fix_file(self, file_path: str) -> Tuple[str, List[str]]:
        """Fix all critical errors in a single file"""
        self.fixes_applied = []
        filename = os.path.basename(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return f"Error reading file: {e}", []
        
        original_content = content
        content = self.fix_all_critical_errors(content, filename)
        
        if content != original_content:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return f"Applied {len(self.fixes_applied)} comprehensive fixes", self.fixes_applied
            except Exception as e:
                return f"Error writing file: {e}", []
        else:
            return "No fixes needed", []
    
    def fix_all_snippets(self, snippets_dir: str) -> dict:
        """Fix all validated snippets comprehensively"""
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
    fixer = ComprehensiveRuntimeFixer()
    
    snippets_dir = "/Users/timholdsworth/code/3b1b_dataset/outputs/2015/inventing-math/validated_snippets"
    
    print("Applying comprehensive runtime fixes...")
    results = fixer.fix_all_snippets(snippets_dir)
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        return
    
    print(f"\nResults:")
    print(f"Files processed: {results['summary']['total_files']}")
    print(f"Files with fixes: {results['summary']['files_with_fixes']}")
    print(f"Total fixes applied: {results['summary']['total_fixes']}")
    
    # Show critical files that were fixed
    critical_files = ['DistanceIsAFunction.py', 'ChopIntervalInProportions.py', 'OneAndInfiniteSumAreTheSameThing.py']
    for filename in critical_files:
        if filename in results and results[filename]['fix_count'] > 0:
            print(f"\n{filename}: {results[filename]['status']}")
            for fix in results[filename]['fixes']:
                print(f"  - {fix}")

if __name__ == "__main__":
    main()