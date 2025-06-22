#!/usr/bin/env python3
"""
Convert ManimGL code to ManimCE (Manim Community Edition)

This script handles the conversion of 3Blue1Brown's manim code from
the OpenGL version (manimgl) to the Community Edition (manimce).
"""

import os
import re
import shutil
import json
from pathlib import Path
from typing import Dict, List, Tuple, Set
import logging
from datetime import datetime
import sys
import subprocess

# Add the script directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from manimce_conversion_utils import (
    apply_all_conversions,
    convert_latex_strings,
    add_scene_config_decorator,
    generate_test_scene,
    extract_scenes
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ManimConverter:
    """Main converter class for manimgl to manimce conversion."""
    
    def __init__(self, source_dir: str, output_dir: str):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.conversion_log = []
        self.issues = []
        self.pi_creature_files = []
        
        # Define conversion mappings
        self.import_mappings = {
            r'from manimlib import \*': 'from manim import *',
            r'from manimlib\.': 'from manim.',
            r'import manimlib': 'import manim',
            r'from manim_imports_ext import \*': 'from manim import *',
        }
        
        self.class_mappings = {
            # Text objects
            r'\bTextMobject\b': 'Text',
            r'\bTexMobject\b': 'MathTex',
            r'\bTexText\b': 'Tex',
            r'\bOldTex\b': 'Tex',
            r'\bOldTexText\b': 'Text',
            
            # Old tex mobject references
            r'from manimlib\.mobject\.svg\.old_tex_mobject import \*': '',
            
            # Animation updates
            r'\bShowCreation\b': 'Create',
            r'\bUncreate\b': 'Uncreate',
            r'\bDrawBorderThenFill\b': 'DrawBorderThenFill',
            r'\bShowPassingFlash\b': 'ShowPassingFlash',
            r'\bCircleIndicate\b': 'Indicate',
            r'\bShowCreationThenDestruction\b': 'ShowPassingFlash',
            r'\bShowCreationThenFadeOut\b': 'ShowCreationThenFadeOut',
            r'\bContinualAnimation\b': 'Animation',  # Will need manual review
            
            # Scene updates
            r'\bThreeDScene\b': 'ThreeDScene',
            r'\bSpecialThreeDScene\b': 'ThreeDScene',
        }
        
        # Patterns to detect custom imports that need removal
        self.custom_import_patterns = [
            r'from custom\.',
            r'from once_useful_constructs\.',
            r'from script_wrapper import',
            r'from stage_scenes import',
        ]
        
        # Patterns to detect pi_creature usage
        self.pi_creature_patterns = [
            r'PiCreature',
            r'pi_creature',
            r'Randolph',
            r'Mortimer',
            r'get_students',
        ]
        
    def setup_output_directory(self):
        """Create output directory structure."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.output_dir / 'converted').mkdir(exist_ok=True)
        (self.output_dir / 'logs').mkdir(exist_ok=True)
        (self.output_dir / 'utils').mkdir(exist_ok=True)
        
    def convert_imports(self, content: str) -> str:
        """Convert import statements from manimgl to manimce."""
        modified_content = content
        
        # Apply import mappings
        for pattern, replacement in self.import_mappings.items():
            if re.search(pattern, modified_content):
                modified_content = re.sub(pattern, replacement, modified_content)
                self.conversion_log.append(f"Converted import: {pattern} -> {replacement}")
        
        # Remove custom imports
        lines = modified_content.split('\n')
        filtered_lines = []
        
        for line in lines:
            should_remove = False
            for pattern in self.custom_import_patterns:
                if re.search(pattern, line):
                    should_remove = True
                    self.conversion_log.append(f"Removed custom import: {line.strip()}")
                    break
            
            if not should_remove:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def convert_class_names(self, content: str) -> str:
        """Convert class names from manimgl to manimce."""
        modified_content = content
        
        for pattern, replacement in self.class_mappings.items():
            if re.search(pattern, modified_content):
                count = len(re.findall(pattern, modified_content))
                modified_content = re.sub(pattern, replacement, modified_content)
                self.conversion_log.append(f"Replaced {count} instances of {pattern} with {replacement}")
        
        return modified_content
    
    def detect_pi_creature_usage(self, content: str, file_path: Path) -> bool:
        """Detect if file uses pi_creature and log it."""
        has_pi_creature = False
        
        for pattern in self.pi_creature_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                has_pi_creature = True
                matches = re.findall(pattern, content, re.IGNORECASE)
                self.issues.append({
                    'file': str(file_path),
                    'issue': 'pi_creature_usage',
                    'pattern': pattern,
                    'count': len(matches)
                })
        
        if has_pi_creature:
            self.pi_creature_files.append(str(file_path))
            
        return has_pi_creature
    
    def comment_out_pi_creature_usage(self, content: str) -> str:
        """Comment out lines that use Pi Creatures since we can't replicate the assets."""
        lines = content.split('\n')
        modified_lines = []
        pi_creature_vars = set()  # Track variable names that are pi creatures
        
        for line in lines:
            original_line = line
            stripped = line.strip()
            
            # Skip if already commented
            if stripped.startswith('#'):
                modified_lines.append(line)
                continue
                
            # Check if line contains pi creature patterns
            has_pi_creature = any(
                re.search(pattern, line, re.IGNORECASE) 
                for pattern in self.pi_creature_patterns
            )
            
            # Check for pi creature variable assignment
            pi_assignment = re.search(r'(\w+)\s*=\s*(?:PiCreature|Randolph|Mortimer|get_students)', line, re.IGNORECASE)
            if pi_assignment:
                pi_creature_vars.add(pi_assignment.group(1))
            
            # Check if line uses a known pi creature variable
            uses_pi_var = any(re.search(r'\b' + var + r'\b', line) for var in pi_creature_vars)
            
            if has_pi_creature or uses_pi_var:
                # Comment out the line and add explanation
                indent = len(line) - len(line.lstrip())
                comment_prefix = ' ' * indent + '# '
                commented_line = comment_prefix + 'REMOVED: ' + stripped + ' # Pi Creature not available in ManimCE'
                modified_lines.append(commented_line)
                
                # Log what we commented out
                self.conversion_log.append(f"Commented out pi_creature line: {stripped}")
            else:
                modified_lines.append(line)
        
        return '\n'.join(modified_lines)
    
    def add_manimce_imports(self, content: str) -> str:
        """Add necessary manimce imports if not present."""
        if 'from manim import *' not in content:
            # Check if there are any imports at all
            import_match = re.search(r'^(import|from)', content, re.MULTILINE)
            if import_match:
                # Add after first import block
                lines = content.split('\n')
                import_end = 0
                for i, line in enumerate(lines):
                    if line.strip() and not line.startswith(('import', 'from', '#')):
                        import_end = i
                        break
                
                lines.insert(import_end, 'from manim import *')
                content = '\n'.join(lines)
            else:
                # Add at the beginning
                content = 'from manim import *\n\n' + content
                
        return content
    
    def convert_file(self, file_path: Path) -> Tuple[str, bool]:
        """Convert a single Python file."""
        logger.info(f"Converting {file_path}")
        self.conversion_log = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Skip if already converted
            if 'from manim import *' in content and 'from manimlib' not in content:
                logger.info(f"File {file_path} appears to already be converted")
                return content, False
            
            # Apply basic conversions
            converted = content
            converted = self.convert_imports(converted)
            converted = self.convert_class_names(converted)
            converted = self.add_manimce_imports(converted)
            
            # Apply advanced conversions from utilities
            converted = apply_all_conversions(converted)
            converted = convert_latex_strings(converted)
            converted = add_scene_config_decorator(converted)
            
            # Validate syntax
            try:
                compile(converted, str(file_path), 'exec')
            except SyntaxError as e:
                self.issues.append({
                    'file': str(file_path),
                    'issue': 'syntax_error',
                    'description': f'Syntax error after conversion: {e}'
                })
                logger.warning(f"Syntax error in converted file {file_path}: {e}")
            
            # Detect issues
            has_pi_creature = self.detect_pi_creature_usage(converted, file_path)
            
            # Check for other potential issues
            if 'ContinualAnimation' in converted:
                self.issues.append({
                    'file': str(file_path),
                    'issue': 'continual_animation',
                    'description': 'Uses ContinualAnimation which needs manual conversion to updaters'
                })
            
            if re.search(r'\.glsl', converted):
                self.issues.append({
                    'file': str(file_path),
                    'issue': 'glsl_shaders',
                    'description': 'Contains GLSL shader references that may need rewriting'
                })
            
            # Comment out pi_creature usage instead of trying to replace
            if has_pi_creature:
                converted = self.comment_out_pi_creature_usage(converted)
            
            # Generate test scenes for the file
            scenes = extract_scenes(converted)
            if scenes:
                test_code = "\n\n# Auto-generated test scenes\n"
                for scene_name, _ in scenes[:3]:  # First 3 scenes only
                    is_3d = 'ThreeDScene' in converted
                    test_code += generate_test_scene(scene_name, is_3d)
                
                # Save test file separately
                test_file = self.output_dir / 'tests' / f"test_{file_path.stem}.py"
                test_file.parent.mkdir(exist_ok=True)
                with open(test_file, 'w') as f:
                    f.write("from manim import *\n")
                    if has_pi_creature:
                        f.write("# Note: Pi Creature scenes have been commented out\n")
                    f.write(test_code)
                
                self.conversion_log.append(f"Generated test file: {test_file}")
            
            return converted, True
            
        except Exception as e:
            logger.error(f"Error converting {file_path}: {e}")
            self.issues.append({
                'file': str(file_path),
                'issue': 'conversion_error',
                'error': str(e)
            })
            return content, False
    
    def convert_directory(self, relative_path: str = ""):
        """Recursively convert all Python files in a directory."""
        source_path = self.source_dir / relative_path
        output_path = self.output_dir / 'converted' / relative_path
        
        if not source_path.exists():
            logger.warning(f"Source path does not exist: {source_path}")
            return
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        for item in source_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                self.convert_directory(str(item.relative_to(self.source_dir)))
            elif item.suffix == '.py':
                output_file = output_path / item.name
                converted_content, was_converted = self.convert_file(item)
                
                if was_converted:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(converted_content)
                    
                    # Save conversion log for this file
                    if self.conversion_log:
                        log_file = self.output_dir / 'logs' / f"{item.stem}_conversion.log"
                        log_file.parent.mkdir(exist_ok=True)
                        with open(log_file, 'w') as f:
                            f.write('\n'.join(self.conversion_log))
    
    def generate_summary_report(self):
        """Generate a summary report of the conversion."""
        report = {
            'conversion_date': datetime.now().isoformat(),
            'source_directory': str(self.source_dir),
            'output_directory': str(self.output_dir),
            'total_files_processed': len(self.issues),
            'files_with_pi_creature': len(self.pi_creature_files),
            'issues': self.issues,
            'pi_creature_files': self.pi_creature_files
        }
        
        report_path = self.output_dir / 'conversion_report.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Also create a human-readable summary
        summary_path = self.output_dir / 'conversion_summary.md'
        with open(summary_path, 'w') as f:
            f.write("# ManimGL to ManimCE Conversion Summary\n\n")
            f.write(f"**Date**: {report['conversion_date']}\n\n")
            f.write(f"**Source**: `{report['source_directory']}`\n")
            f.write(f"**Output**: `{report['output_directory']}`\n\n")
            
            f.write("## Statistics\n\n")
            f.write(f"- Total files processed: {report['total_files_processed']}\n")
            f.write(f"- Files with pi_creature: {len(self.pi_creature_files)}\n")
            f.write(f"- Total issues found: {len(self.issues)}\n\n")
            
            if self.pi_creature_files:
                f.write("## Files Requiring Pi Creature Replacement\n\n")
                for file in self.pi_creature_files:
                    f.write(f"- `{file}`\n")
                f.write("\n")
            
            # Group issues by type
            issues_by_type = {}
            for issue in self.issues:
                issue_type = issue.get('issue', 'unknown')
                if issue_type not in issues_by_type:
                    issues_by_type[issue_type] = []
                issues_by_type[issue_type].append(issue)
            
            if issues_by_type:
                f.write("## Issues by Type\n\n")
                for issue_type, issues in issues_by_type.items():
                    f.write(f"### {issue_type} ({len(issues)} files)\n\n")
                    for issue in issues[:10]:  # Show first 10
                        f.write(f"- `{issue['file']}`\n")
                    if len(issues) > 10:
                        f.write(f"- ... and {len(issues) - 10} more\n")
                    f.write("\n")
        
        logger.info(f"Conversion report saved to {report_path}")
        logger.info(f"Human-readable summary saved to {summary_path}")
    
    def run(self):
        """Run the complete conversion process."""
        logger.info("Starting ManimGL to ManimCE conversion")
        
        self.setup_output_directory()
        self.convert_directory()
        
        # Note: Claude sanity check could be added here if needed
        # For now, we rely on the automated conversion rules and manual review
        logger.info("Conversion validation completed - review conversion_summary.md for issues")
        
        self.generate_summary_report()
        
        logger.info("Conversion complete!")
        logger.info(f"Files with pi_creature: {len(self.pi_creature_files)}")
        logger.info(f"Total issues: {len(self.issues)}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert ManimGL code to ManimCE')
    parser.add_argument('source', help='Source directory containing manimgl code')
    parser.add_argument('output', help='Output directory for converted code')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    converter = ManimConverter(args.source, args.output)
    converter.run()


if __name__ == '__main__':
    main()