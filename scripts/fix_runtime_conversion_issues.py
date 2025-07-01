#!/usr/bin/env python3
"""
Fix runtime conversion issues that AST conversion can't catch.
Addresses issues like:
1. .center vs .get_center() property/method confusion
2. Runtime-generated Tex vs MathTex content
3. Other common runtime pattern issues
"""

import re
import ast
from pathlib import Path
from typing import List, Dict, Tuple
import logging


class RuntimeConversionFixer:
    """Fix runtime issues that the AST converter can't catch."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        
        # Pattern fixes to apply
        self.pattern_fixes = [
            # Fix .center property to .get_center() method
            (
                r'(\w+)\.center(\s*[+\-*/])',
                r'\1.get_center()\2',
                'Fix .center property to .get_center() method'
            ),
            
            # Fix runtime Tex with math content that should be MathTex
            (
                r"Tex\s*\(\s*['\"]([^'\"]*\\\\frac[^'\"]*)['\"]",
                r'MathTex(r"\1"',
                'Fix Tex with \\frac to MathTex'
            ),
            (
                r"Tex\s*\(\s*['\"]([^'\"]*\\\\cdot[^'\"]*)['\"]",
                r'MathTex(r"\1"',
                'Fix Tex with \\cdot to MathTex'
            ),
            (
                r"Tex\s*\(\s*['\"]([^'\"]*\\\\sum[^'\"]*)['\"]",
                r'MathTex(r"\1"',
                'Fix Tex with \\sum to MathTex'
            ),
            (
                r"Tex\s*\(\s*['\"]([^'\"]*\\\\int[^'\"]*)['\"]",
                r'MathTex(r"\1"',
                'Fix Tex with \\int to MathTex'
            ),
            (
                r"Tex\s*\(\s*['\"]([^'\"]*\\\\\w+[^'\"]*)['\"]",
                r'MathTex(r"\1"',
                'Fix Tex with LaTeX commands to MathTex'
            ),
            
            # Fix string formatting that generates math content
            (
                r"Tex\s*\(\s*['\"]\\\\frac\{%[sd]\}\{%[sd]\}['\"]",
                r'MathTex(r"\\frac{%s}{%s}"',
                'Fix string formatted fractions to MathTex'
            ),
            
            # Fix common ManimGL to ManimCE property changes
            (
                r'(\w+)\.points\[0\]',
                r'\1.get_start()',
                'Fix .points[0] to .get_start()'
            ),
            (
                r'(\w+)\.points\[-1\]',
                r'\1.get_end()',
                'Fix .points[-1] to .get_end()'
            ),
            
            # Fix shift operations with wrong syntax
            (
                r'\.shift\(([^)]+) - ([^)]+)\.points\[0\]\)',
                r'.shift(\1 - \2.get_start())',
                'Fix shift with points[0] to get_start()'
            ),
            
            # Fix common method vs property issues
            (
                r'(\w+)\.width(\s*[+\-*/])',
                r'\1.get_width()\2',
                'Fix .width property to .get_width() method'
            ),
            (
                r'(\w+)\.height(\s*[+\-*/])',
                r'\1.get_height()\2',
                'Fix .height property to .get_height() method'
            ),
        ]
        
        # Math LaTeX patterns that should definitely be MathTex
        self.math_patterns = [
            r'\\frac', r'\\sum', r'\\int', r'\\prod', r'\\lim',
            r'\\alpha', r'\\beta', r'\\gamma', r'\\delta', r'\\epsilon',
            r'\\theta', r'\\lambda', r'\\mu', r'\\pi', r'\\sigma',
            r'\\infty', r'\\partial', r'\\nabla', r'\\cdot', r'\\times',
            r'\\leq', r'\\geq', r'\\neq', r'\\approx', r'\\pm'
        ]
        
    def fix_file(self, file_path: Path) -> Dict:
        """Fix runtime conversion issues in a single file."""
        if not file_path.exists() or not file_path.suffix == '.py':
            return {'status': 'skipped', 'reason': 'Not a Python file'}
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
                
            fixed_content = original_content
            fixes_applied = []
            
            # Apply pattern fixes
            for pattern, replacement, description in self.pattern_fixes:
                matches = list(re.finditer(pattern, fixed_content))
                if matches:
                    fixed_content = re.sub(pattern, replacement, fixed_content)
                    fixes_applied.append({
                        'description': description,
                        'pattern': pattern,
                        'matches': len(matches),
                        'lines': [self._get_line_number(original_content, m.start()) for m in matches]
                    })
                    
            # Check for potential math content in Tex calls that we might have missed
            tex_calls = re.finditer(r'Tex\s*\(\s*[\'\"r]([^\'\"]*)[\'\"]\s*\)', fixed_content)
            for match in tex_calls:
                tex_content = match.group(1)
                if any(pattern in tex_content for pattern in self.math_patterns):
                    # This looks like math content that should be MathTex
                    line_num = self._get_line_number(fixed_content, match.start())
                    fixes_applied.append({
                        'description': 'Potential math content in Tex call',
                        'line': line_num,
                        'content': tex_content,
                        'suggestion': 'Consider changing to MathTex'
                    })
            
            # Write back if changes were made
            if fixed_content != original_content:
                # Create backup
                backup_path = file_path.with_suffix(file_path.suffix + '.runtime_backup')
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                    
                # Write fixed version
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                    
                return {
                    'status': 'fixed',
                    'fixes_applied': fixes_applied,
                    'backup_created': str(backup_path)
                }
            else:
                return {
                    'status': 'no_changes_needed',
                    'potential_issues': fixes_applied if fixes_applied else []
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
            
    def _get_line_number(self, content: str, position: int) -> int:
        """Get line number for a character position in the content."""
        return content[:position].count('\n') + 1
        
    def fix_directory(self, directory: Path, file_pattern: str = "*.py") -> Dict:
        """Fix all Python files in a directory."""
        if not directory.exists():
            return {'error': 'Directory does not exist'}
            
        results = {
            'total_files': 0,
            'files_fixed': 0,
            'files_with_issues': 0,
            'files_failed': 0,
            'detailed_results': {}
        }
        
        for file_path in directory.rglob(file_pattern):
            if file_path.is_file():
                results['total_files'] += 1
                
                result = self.fix_file(file_path)
                results['detailed_results'][str(file_path)] = result
                
                if result['status'] == 'fixed':
                    results['files_fixed'] += 1
                elif result['status'] == 'error':
                    results['files_failed'] += 1
                elif result.get('potential_issues'):
                    results['files_with_issues'] += 1
                    
                if self.verbose:
                    self.logger.info(f"Processed {file_path}: {result['status']}")
                    
        return results
        
    def fix_video_snippets(self, year: int, base_dir: Path, video_filter: List[str] = None) -> Dict:
        """Fix runtime issues in validated snippets for a specific year."""
        year_dir = base_dir / 'outputs' / str(year)
        
        if not year_dir.exists():
            return {'error': f'Year directory {year_dir} does not exist'}
            
        results = {
            'year': year,
            'total_videos': 0,
            'videos_processed': 0,
            'total_files_fixed': 0,
            'video_results': {}
        }
        
        for video_dir in year_dir.iterdir():
            if not video_dir.is_dir():
                continue
                
            # Apply video filter if specified
            if video_filter and video_dir.name not in video_filter:
                continue
                
            results['total_videos'] += 1
            
            # Check for validated snippets
            snippets_dir = video_dir / 'validated_snippets'
            if not snippets_dir.exists():
                results['video_results'][video_dir.name] = {
                    'status': 'no_snippets',
                    'message': 'No validated_snippets directory found'
                }
                continue
                
            # Fix snippets in this video
            video_result = self.fix_directory(snippets_dir)
            results['video_results'][video_dir.name] = video_result
            results['videos_processed'] += 1
            results['total_files_fixed'] += video_result.get('files_fixed', 0)
            
            if self.verbose:
                fixed = video_result.get('files_fixed', 0)
                total = video_result.get('total_files', 0)
                self.logger.info(f"Video {video_dir.name}: {fixed}/{total} files fixed")
                
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Fix runtime conversion issues in ManimCE snippets'
    )
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    parser.add_argument('--video', action='append',
                        help='Process only specific video(s) by name (can be specified multiple times)')
    parser.add_argument('--file', type=str,
                        help='Process a single file instead of entire year')
    parser.add_argument('--directory', type=str,
                        help='Process all Python files in a directory')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    fixer = RuntimeConversionFixer(verbose=args.verbose)
    
    if args.file:
        # Process single file
        file_path = Path(args.file)
        result = fixer.fix_file(file_path)
        print(f"Result for {file_path}: {result}")
        
    elif args.directory:
        # Process directory
        dir_path = Path(args.directory)
        result = fixer.fix_directory(dir_path)
        print(f"Fixed {result['files_fixed']}/{result['total_files']} files")
        print(f"Files with potential issues: {result['files_with_issues']}")
        print(f"Failed files: {result['files_failed']}")
        
    else:
        # Process year
        base_dir = Path(__file__).parent.parent
        result = fixer.fix_video_snippets(args.year, base_dir, args.video)
        
        print(f"Runtime Fix Results for {args.year}:")
        print(f"Videos processed: {result['videos_processed']}/{result['total_videos']}")
        print(f"Total files fixed: {result['total_files_fixed']}")
        
        # Show summary by video
        for video_name, video_result in result['video_results'].items():
            if video_result.get('files_fixed', 0) > 0:
                print(f"  {video_name}: {video_result['files_fixed']} files fixed")


if __name__ == '__main__':
    main()