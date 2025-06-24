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

# Import error collection system
from conversion_error_collector import (
    get_error_collector, 
    collect_conversion_error, 
    collect_conversion_fix,
    get_fix_suggestions_for_error
)

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

# Import our advanced conversion system
try:
    from manimce_advanced_converter import AdvancedManimConverter
    from manimce_ast_converter import analyze_manimgl_usage
    ADVANCED_CONVERTER_AVAILABLE = True
except ImportError:
    ADVANCED_CONVERTER_AVAILABLE = False
    logger.warning("Advanced converter not available, using basic conversion")


class ManimConverter:
    """Main converter class for manimgl to manimce conversion."""
    
    def __init__(self, source_dir: str, output_dir: str, verbose: bool = False, 
                 enable_render_validation: bool = True, render_max_attempts: int = 3,
                 use_advanced_converter: bool = True, intelligent_parsing: bool = True):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.conversion_log = []
        self.issues = []
        self.pi_creature_files = []
        self.verbose = verbose
        self.enable_render_validation = enable_render_validation
        self.render_max_attempts = render_max_attempts
        self.use_advanced = use_advanced_converter and ADVANCED_CONVERTER_AVAILABLE
        self.intelligent_parsing = intelligent_parsing
        
        # Initialize advanced converter if available
        if self.use_advanced:
            self.advanced_converter = AdvancedManimConverter(
                source_dir, output_dir, verbose, 
                enable_render_validation, render_max_attempts
            )
            # Pass our regex expertise to the AST converter for enhanced quality
            self.advanced_converter.regex_helper = self
            logger.info("Using enhanced AST converter with regex techniques")
        else:
            logger.info("Using basic regex-based converter")
        
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
        
        # Copy custom animations module to utils
        custom_animations_src = Path(__file__).parent / 'manimce_custom_animations.py'
        custom_animations_dst = self.output_dir / 'utils' / 'manimce_custom_animations.py'
        
        if custom_animations_src.exists() and not custom_animations_dst.exists():
            shutil.copy2(custom_animations_src, custom_animations_dst)
            self.logger.info(f"Copied custom animations module to {custom_animations_dst}")
        
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
        i = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Skip if already commented
            if stripped.startswith('#'):
                modified_lines.append(line)
                i += 1
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
                
                # Check if this is part of a multi-line statement
                # Look for unclosed parentheses, brackets, or line continuations
                open_parens = line.count('(') - line.count(')')
                open_brackets = line.count('[') - line.count(']')
                open_braces = line.count('{') - line.count('}')
                ends_with_backslash = stripped.endswith('\\')
                
                # Continue commenting subsequent lines if needed
                j = i + 1
                while j < len(lines) and (open_parens > 0 or open_brackets > 0 or 
                                         open_braces > 0 or ends_with_backslash):
                    next_line = lines[j]
                    next_stripped = next_line.strip()
                    
                    # Update counts
                    open_parens += next_line.count('(') - next_line.count(')')
                    open_brackets += next_line.count('[') - next_line.count(']')
                    open_braces += next_line.count('{') - next_line.count('}')
                    ends_with_backslash = next_stripped.endswith('\\')
                    
                    # Comment out this continuation line
                    next_indent = len(next_line) - len(next_line.lstrip())
                    next_comment_prefix = ' ' * next_indent + '# '
                    commented_next = next_comment_prefix + 'REMOVED (cont): ' + next_stripped
                    modified_lines.append(commented_next)
                    
                    j += 1
                
                # Skip the lines we just processed
                i = j
                
                # Log what we commented out
                self.conversion_log.append(f"Commented out pi_creature line: {stripped}")
            else:
                modified_lines.append(line)
                i += 1
        
        # Post-process to add 'pass' to empty function bodies
        result_lines = []
        i = 0
        while i < len(modified_lines):
            line = modified_lines[i]
            result_lines.append(line)
            
            # Check if this is a function definition
            if re.match(r'\s*def\s+\w+\s*\(.*\)\s*:', line):
                # Look ahead to see if function body is empty or all commented
                j = i + 1
                found_non_comment = False
                indent_level = len(line) - len(line.lstrip()) + 4  # Expected indent for function body
                
                while j < len(modified_lines):
                    next_line = modified_lines[j]
                    if not next_line.strip():  # Empty line
                        j += 1
                        continue
                    
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent < indent_level:  # End of function body
                        break
                    
                    if not next_line.strip().startswith('#'):  # Found non-comment line
                        found_non_comment = True
                        break
                    
                    j += 1
                
                # If no non-comment lines found in function body, add 'pass'
                if not found_non_comment:
                    result_lines.append(' ' * indent_level + 'pass')
                    self.conversion_log.append(f"Added 'pass' to empty function body")
            
            i += 1
        
        return '\n'.join(result_lines)
    
    # Removed complexity analysis - we now prioritize quality over speed
    
    def validate_for_conversion(self, file_path: Path) -> Tuple[bool, str]:
        """Check if file is ready for conversion"""
        
        if not file_path.exists():
            return False, "File does not exist"
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
        except Exception as e:
            return False, f"Cannot read file: {e}"
        
        if len(content) < 100:
            return False, "File is too small (less than 100 characters)"
        
        try:
            compile(content, str(file_path), 'exec')
        except SyntaxError as e:
            return False, f"Input has syntax errors: {e}"
        
        # Check for ManimGL imports (indicates it needs conversion)
        has_manimgl = any(pattern in content for pattern in [
            'from manimlib', 'import manimlib', 'from manim_imports_ext'
        ])
        
        # Check for ManimCE imports (indicates it's already converted)
        has_manimce = 'from manim import' in content and 'manimlib' not in content
        
        if has_manimce:
            return False, "File appears to already be converted to ManimCE"
        
        if not has_manimgl:
            # No clear imports, but might still be ManimGL code
            return True, "File may be ManimGL code (no clear imports found)"
        
        return True, "Ready for conversion"
    
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
    
    def fix_tex_parentheses(self, content: str) -> str:
        """Fix common syntax errors in Tex calls caused by conversion."""
        import re
        
        # Pattern 1: Fix Tex calls with string formatting that have extra )
        # e.g., Tex(r'\frac{%d}{%d}') % (n, d)) -> Tex(r'\frac{%d}{%d}' % (n, d))
        content = re.sub(
            r"((?:Old)?Tex\(r?['\"].*?['\"])\)\s*%\s*([^)]+)\)\)",
            r"\1 % \2)",
            content
        )
        
        # Pattern 2: Fix Tex calls ending with '))
        # e.g., Tex(r'\int')) -> Tex(r'\int')
        content = re.sub(
            r"((?:Old)?Tex\(r?['\"][^'\"]+?['\"]\))\)",
            r"\1",
            content
        )
        
        # Pattern 3: Fix indentation issues after class definitions
        lines = content.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            if i > 0 and lines[i-1].strip().startswith('class ') and lines[i-1].strip().endswith(':'):
                # Previous line was a class definition
                if line.startswith('def ') and not line.startswith('    '):
                    # This def should be indented
                    line = '    ' + line
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def test_render_scene(self, file_path: Path, scene_name: str, timeout: int = 30) -> Dict:
        """Try to render a scene and return the result."""
        try:
            # Create a temporary directory for render output
            temp_render_dir = self.output_dir / 'temp_renders'
            temp_render_dir.mkdir(exist_ok=True)
            
            cmd = [
                "manim", 
                str(file_path), 
                scene_name,
                "-ql",  # low quality for speed
                "--disable_caching",
                "-s",  # just save last frame
                "--media_dir", str(temp_render_dir)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return {"success": True, "scene": scene_name}
            else:
                # Extract meaningful error from stderr
                error_lines = result.stderr.strip().split('\n')
                # Look for actual error messages (skip warnings)
                actual_errors = [line for line in error_lines 
                               if 'Error' in line or 'error' in line or 'Traceback' in line
                               or 'File' in line or 'line' in line]
                
                error_msg = '\n'.join(actual_errors[-20:]) if actual_errors else result.stderr[-1000:]
                
                return {
                    "success": False,
                    "scene": scene_name,
                    "error": error_msg,
                    "full_stderr": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {"success": False, "scene": scene_name, "error": f"Render timeout after {timeout}s"}
        except Exception as e:
            return {"success": False, "scene": scene_name, "error": str(e)}
    
    def run_render_validation(self, file_path: Path, original_content: str, converted_content: str, max_attempts: int = 3) -> Tuple[str, bool, List[Dict]]:
        """
        Validate conversion by attempting to render scenes.
        Returns: (final_content, success, render_results)
        """
        # Extract scenes from converted content
        scenes = extract_scenes(converted_content)
        if not scenes:
            logger.info(f"No scenes found in {file_path}")
            return converted_content, True, []
        
        # Write converted content to a temporary file for testing
        temp_file = self.output_dir / 'temp_test.py'
        current_content = converted_content
        render_results = []
        error_ids = []  # Track error IDs for this validation
        
        # Test first scene (or first few if the first has no construct method)
        scenes_to_test = []
        for scene_name, scene_body in scenes[:3]:
            if 'def construct' in scene_body:
                scenes_to_test.append(scene_name)
                if len(scenes_to_test) >= 1:  # Just test one scene for speed
                    break
        
        if not scenes_to_test:
            logger.warning(f"No scenes with construct method found in {file_path}")
            return converted_content, True, []
        
        scene_name = scenes_to_test[0]
        logger.info(f"Testing render of scene: {scene_name}")
        
        for attempt in range(max_attempts):
            # Write current content to temp file
            with open(temp_file, 'w') as f:
                f.write(current_content)
            
            # Try to render
            render_result = self.test_render_scene(temp_file, scene_name)
            render_results.append(render_result)
            
            if render_result["success"]:
                logger.info(f"✓ Scene {scene_name} renders successfully!")
                
                # Record successful fixes
                for error_id in error_ids:
                    collect_conversion_fix(
                        error_id=error_id,
                        fix_description="Render validation succeeded after fixes",
                        fixed_code=current_content,
                        success=True,
                        fix_type='claude',
                        additional_info={'scene': scene_name, 'attempts': attempt + 1}
                    )
                
                # Clean up temp file
                if temp_file.exists():
                    temp_file.unlink()
                return current_content, True, render_results
            
            # Render failed - collect the error
            error_id = collect_conversion_error(
                file_path=str(file_path),
                error_message=render_result.get('error', 'Unknown error'),
                error_type='render_error',
                code_context=f"Scene: {scene_name}",
                original_code=original_content[:1000],
                converted_code=current_content[:1000]
            )
            error_ids.append(error_id)
            
            # Try to fix with Claude
            if attempt < max_attempts - 1:
                logger.info(f"Render failed (attempt {attempt + 1}/{max_attempts}), asking Claude to fix...")
                
                # Generate enhanced fix prompt with error patterns
                fix_prompt = self.generate_render_fix_prompt(
                    file_path, 
                    original_content, 
                    current_content, 
                    render_result
                )
                
                # Run Claude to fix the error
                fix_result = self.run_claude_render_fix(fix_prompt, temp_file)
                
                if fix_result.get('status') == 'fixed':
                    # Read the fixed content
                    with open(temp_file, 'r') as f:
                        new_content = f.read()
                    
                    # Record the fix attempt
                    collect_conversion_fix(
                        error_id=error_id,
                        fix_description=f"Claude fix attempt {attempt + 1}",
                        fixed_code=new_content[:1000],
                        success=False,  # Will update to True if render succeeds
                        fix_type='claude',
                        additional_info={'attempt': attempt + 1}
                    )
                    
                    current_content = new_content
                    logger.info("Claude applied a fix, retrying render...")
                else:
                    logger.error(f"Claude fix failed: {fix_result.get('error', 'Unknown error')}")
                    break
        
        # Record final failure
        for error_id in error_ids:
            collect_conversion_fix(
                error_id=error_id,
                fix_description=f"Failed after {max_attempts} attempts",
                fixed_code=current_content[:1000],
                success=False,
                fix_type='claude',
                additional_info={'final_attempt': True}
            )
        
        # Clean up temp file
        if temp_file.exists():
            temp_file.unlink()
            
        logger.warning(f"Failed to get {scene_name} to render after {max_attempts} attempts")
        return current_content, False, render_results
    
    def generate_render_fix_prompt(self, file_path: Path, original_content: str, 
                                  converted_content: str, render_result: Dict) -> str:
        """Generate an enhanced prompt for Claude to fix render errors."""
        # Get fix suggestions from error collector
        error_message = render_result.get('error', '')
        suggestions = get_fix_suggestions_for_error(error_message, converted_content[:500])
        
        # Build suggestions section
        suggestions_text = ""
        if suggestions:
            suggestions_text = "\n## Suggested Fixes (based on similar errors):\n"
            for i, suggestion in enumerate(suggestions[:3], 1):
                suggestions_text += f"\n{i}. **{suggestion['description']}** (confidence: {suggestion['confidence']:.1%})\n"
                if suggestion.get('code_snippet'):
                    suggestions_text += f"   ```python\n   {suggestion['code_snippet']}\n   ```\n"
        
        # Get specific patterns for this error type
        error_patterns = self._get_error_specific_patterns(error_message)
        
        return f"""You are helping convert ManimGL code to ManimCE. A scene failed to render with an error.

## Original ManimGL Code (first 100 lines):
```python
{original_content[:3000]}
```

## Converted ManimCE Code:
```python
{converted_content}
```

## Render Error:
Scene: {render_result['scene']}
Error: {render_result['error']}
{suggestions_text}

## Known Error Patterns:
{error_patterns}

## Your Task:
1. Analyze the error message carefully
2. Check the suggested fixes first - they have worked for similar errors
3. Identify what ManimCE API changes are causing the issue
4. Fix ONLY the specific error - don't make other changes

## Common Issues and Solutions:
- **ShowCreation not found** → Replace with `Create`
- **TextMobject not found** → Replace with `Text`
- **TexMobject not found** → Replace with `MathTex`
- **OldTex/OldTexText** → Replace with `Tex`/`Text` using raw strings
- **COLOR_MAP** → Replace with `MANIM_COLORS`
- **get_width()/get_height()** → Use `.width`/`.height` properties
- **ContinualAnimation** → Convert to `mobject.add_updater(lambda m, dt: ...)`
- **CONFIG dictionary** → Convert to class attributes or __init__ parameters
- **Missing imports** → Add `from manim import *` or specific imports

Edit the file at: {file_path}

IMPORTANT: Make minimal changes to fix only the render error. Do not refactor or improve code style."""
    
    def _get_error_specific_patterns(self, error_message: str) -> str:
        """Get specific patterns for common error types."""
        patterns = []
        
        # Check for specific error patterns
        if "ShowCreation" in error_message:
            patterns.append("- ShowCreation is now Create in ManimCE")
            patterns.append("- May need: from manim import Create")
        
        if "TextMobject" in error_message:
            patterns.append("- TextMobject is now Text in ManimCE")
            patterns.append("- May need: from manim import Text")
        
        if "TexMobject" in error_message:
            patterns.append("- TexMobject is now MathTex in ManimCE")
            patterns.append("- May need: from manim import MathTex")
        
        if "COLOR_MAP" in error_message:
            patterns.append("- COLOR_MAP is now MANIM_COLORS")
            patterns.append("- Color constants may have changed (LIGHT_GRAY → LIGHT_GREY)")
        
        if "has no attribute 'get_" in error_message:
            patterns.append("- Many get_* methods are now properties")
            patterns.append("- get_width() → .width, get_height() → .height")
        
        if "ContinualAnimation" in error_message:
            patterns.append("- ContinualAnimation doesn't exist in ManimCE")
            patterns.append("- Use mobject.add_updater() instead")
        
        if "CONFIG" in error_message:
            patterns.append("- CONFIG dictionaries need conversion")
            patterns.append("- Move CONFIG items to class attributes or __init__")
        
        if not patterns:
            patterns.append("- Check imports are correct")
            patterns.append("- Verify all class names match ManimCE API")
        
        return "\n".join(patterns)
    
    def run_claude_render_fix(self, prompt: str, file_path: Path) -> Dict:
        """Run Claude to fix render errors."""
        try:
            # Save prompt for debugging
            prompt_file = self.output_dir / 'logs' / 'render_fix_prompt.txt'
            prompt_file.parent.mkdir(exist_ok=True)
            with open(prompt_file, 'w') as f:
                f.write(prompt)
            
            # Run Claude with the fix prompt
            cmd = ["claude"]
            
            if self.verbose:
                # Run with output streaming to console
                logger.info("Running Claude to fix render errors...")
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1  # Line buffered
                )
                
                # Send the prompt to stdin
                process.stdin.write(prompt)
                process.stdin.close()
                
                # Collect output while also printing it
                stdout_lines = []
                
                # Read stdout in real-time
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        print(f"    Claude: {line.rstrip()}")
                        stdout_lines.append(line)
                
                # Get any remaining stderr
                stderr = process.stderr.read()
                
                result = subprocess.CompletedProcess(
                    args=process.args,
                    returncode=process.returncode,
                    stdout=''.join(stdout_lines),
                    stderr=stderr
                )
            else:
                # Run silently
                result = subprocess.run(
                    cmd,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minute timeout for fixes
                )
            
            if result.returncode == 0:
                # Check if file was actually modified
                if file_path.exists():
                    return {"status": "fixed"}
                else:
                    return {"status": "error", "error": "File not found after Claude edit"}
            else:
                return {
                    "status": "error",
                    "error": f"Claude returned non-zero exit code: {result.returncode}",
                    "stderr": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Claude fix timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def convert_file(self, file_path: Path) -> Tuple[str, bool]:
        """Convert a single Python file with render validation."""
        logger.info(f"Converting {file_path}")
        self.conversion_log = []
        
        # Validate file before conversion
        is_valid, validation_msg = self.validate_for_conversion(file_path)
        if not is_valid:
            logger.error(f"File validation failed: {validation_msg}")
            self.issues.append({
                'file': str(file_path),
                'issue': 'validation_failed',
                'description': validation_msg
            })
            return "", False
        
        logger.info(f"Validation passed: {validation_msg}")
        
        # Quality-first approach: Always use AST but enhance it with regex techniques
        if self.intelligent_parsing and self.use_advanced:
            logger.info("Using enhanced AST converter with quality-focused techniques")
        
        # Use advanced converter if available
        if self.use_advanced:
            try:
                converted_content, success, metadata = self.advanced_converter.convert_file(file_path)
                
                # Update our tracking
                self.conversion_log.extend(metadata.get('conversions', []))
                self.issues.extend(metadata.get('issues', []))
                
                # Track pi creature files
                if any(issue.get('type') == 'pi_creature' for issue in metadata.get('issues', [])):
                    self.pi_creature_files.append(str(file_path))
                
                return converted_content, success
                
            except Exception as e:
                logger.error(f"Advanced converter failed, falling back to basic: {e}")
                self.use_advanced = False
        
        # Fall back to basic conversion
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content  # Keep original for error fixing
            
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
            
            # Fix common syntax errors from conversion
            converted = self.fix_tex_parentheses(converted)
            
            # Add custom animation imports if needed
            if any(anim in converted for anim in ['FlipThroughNumbers', 'DelayByOrder']):
                # Check if the import is already there
                if 'from manimce_custom_animations import' not in converted:
                    lines = converted.split('\n')
                    insert_pos = 0
                    
                    # Find position after manim import
                    for i, line in enumerate(lines):
                        if 'from manim import *' in line:
                            insert_pos = i + 1
                            break
                    
                    # Add the import
                    imports_needed = []
                    if 'FlipThroughNumbers' in converted:
                        imports_needed.append('FlipThroughNumbers')
                    if 'DelayByOrder' in converted:
                        imports_needed.append('DelayByOrder')
                    
                    import_line = f"from manimce_custom_animations import {', '.join(imports_needed)}"
                    lines.insert(insert_pos, import_line)
                    converted = '\n'.join(lines)
            
            # Validate syntax
            has_syntax_error = False
            try:
                compile(converted, str(file_path), 'exec')
            except SyntaxError as e:
                has_syntax_error = True
                self.issues.append({
                    'file': str(file_path),
                    'issue': 'syntax_error',
                    'description': f'Syntax error after conversion: {e}'
                })
                logger.error(f"Syntax error in converted file {file_path}: {e}")
                logger.info("Attempting to fix common syntax errors...")
            
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
            
            # If we still have syntax errors after all conversions, try one more validation
            if has_syntax_error:
                try:
                    compile(converted, str(file_path), 'exec')
                    has_syntax_error = False  # Fixed!
                    logger.info("Syntax errors were fixed by subsequent conversions")
                except SyntaxError as e:
                    logger.error(f"Still has syntax error after all conversions: {e}")
                    # Return original content to avoid creating broken files
                    logger.warning(f"Returning original content for {file_path} due to syntax errors")
                    return content, False
            
            # NEW: Run render validation before finalizing
            if self.enable_render_validation and not has_syntax_error and extract_scenes(converted):
                logger.info("Running render validation...")
                validated_content, render_success, render_results = self.run_render_validation(
                    file_path, original_content, converted, max_attempts=self.render_max_attempts
                )
                
                if render_success:
                    converted = validated_content
                    self.conversion_log.append("✓ Render validation passed")
                else:
                    self.issues.append({
                        'file': str(file_path),
                        'issue': 'render_failed',
                        'description': 'Could not get scenes to render after multiple attempts',
                        'render_results': render_results
                    })
                    self.conversion_log.append("✗ Render validation failed")
                    # Still return the converted content, just log the issue
                    converted = validated_content
            
            # Generate test scenes for the file
            scenes = extract_scenes(converted)
            if scenes and not has_syntax_error:
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
    
    def generate_enhanced_conversion_prompt(self, file_content: str, file_path: Path) -> str:
        """Generate an enhanced prompt for initial conversion with error prevention."""
        # Get common error patterns from the collector
        collector = get_error_collector()
        error_patterns = collector.get_error_patterns()
        
        # Build prevention rules based on patterns
        prevention_rules = []
        for category, data in error_patterns.items():
            if data['count'] > 5 and data['most_common_items']:
                for item in data['most_common_items'][:3]:
                    prevention_rules.append(f"- {category}: Check for '{item}' and apply appropriate conversion")
        
        return f"""Convert this ManimGL code to ManimCE. Based on analysis of {collector.error_db['statistics']['total_errors']} previous conversion errors, pay special attention to these common issues:

## Most Common Conversion Errors to Prevent:
{chr(10).join(prevention_rules[:10]) if prevention_rules else '- No previous error patterns available'}

## Essential Conversions:
1. **Imports**: 
   - `from manimlib import *` → `from manim import *`
   - Remove custom imports (custom., once_useful_constructs., etc.)

2. **Class Name Changes**:
   - TextMobject → Text
   - TexMobject → MathTex
   - TexText → Tex
   - OldTex → Tex (with raw strings)
   - ShowCreation → Create
   - ShowCreationThenDestruction → ShowPassingFlash

3. **Method Changes**:
   - get_width() → .width
   - get_height() → .height
   - Many other get_* methods are now properties

4. **Special Handling**:
   - Pi Creatures: Comment out with explanation
   - ContinualAnimation: Convert to add_updater()
   - CONFIG dict: Convert to class attributes

## File to Convert:
{file_path}

## Code:
```python
{file_content}
```

Convert this code ensuring it will compile and run in ManimCE without errors."""

    def generate_sanity_check_prompt(self) -> str:
        """Generate a comprehensive prompt for Claude to sanity check the conversion."""
        # Gather statistics
        total_files = len([f for f in (self.output_dir / 'converted').rglob('*.py')])
        syntax_errors = [i for i in self.issues if i.get('issue') == 'syntax_error']
        pi_creature_issues = [i for i in self.issues if i.get('issue') == 'pi_creature_usage']
        continual_animation_issues = [i for i in self.issues if i.get('issue') == 'continual_animation']
        
        # Get error patterns from collector
        collector = get_error_collector()
        error_summary = collector.generate_error_summary()
        
        prompt = f"""You are reviewing an automated ManimGL to ManimCE code conversion. Your task is to:
1. Check for any remaining ManimGL-specific code that wasn't converted
2. Fix any obvious conversion errors
3. Ensure the code follows ManimCE conventions

Conversion Summary:
- Converted directory: {self.output_dir / 'converted'}
- Total files converted: {total_files}
- Files with syntax errors: {len(syntax_errors)}
- Files with Pi Creatures (commented out): {len(self.pi_creature_files)}
- Files with ContinualAnimation: {len(continual_animation_issues)}

## Error Pattern Analysis:
{error_summary}

Known Issues Requiring Attention:
"""
        
        # Add specific files with issues
        if syntax_errors:
            prompt += "\n## Files with Syntax Errors:\n"
            for error in syntax_errors[:5]:  # Show first 5
                prompt += f"- {error['file']}: {error.get('description', 'Unknown error')}\n"
            if len(syntax_errors) > 5:
                prompt += f"- ... and {len(syntax_errors) - 5} more\n"
        
        if continual_animation_issues:
            prompt += "\n## Files using ContinualAnimation (needs conversion to updaters):\n"
            for issue in continual_animation_issues[:5]:
                prompt += f"- {issue['file']}\n"
        
        prompt += """\n## Specific Patterns to Check and Fix:

1. **Import statements**: 
   - Ensure all files have `from manim import *` at the top
   - Remove any remaining `from manimlib` imports
   - Remove custom imports like `from custom.`, `from once_useful_constructs.`

2. **Class name conversions**:
   - TextMobject → Text
   - TexMobject → MathTex  
   - TexText → Tex
   - OldTex → Tex (with raw strings r"...")
   - OldTexText → Text
   - ShowCreation → Create
   - ShowCreationThenDestruction → ShowPassingFlash

3. **Method updates**:
   - `.scale_to_fit_width()` → `.scale_to_fit_width()`
   - `.scale_to_fit_height()` → `.scale_to_fit_height()` 
   - `get_center()` → `get_center()`
   - Check that color constants use ManimCE names (RED, BLUE, etc.)

4. **ContinualAnimation conversions**:
   - Convert ContinualAnimation to use `.add_updater()` method
   - Example: `self.continual_animations.append(ContinualAnimation(...))` 
     should become: `mobject.add_updater(lambda m, dt: ...)`

5. **LaTeX string handling**:
   - Convert regular strings in Tex/MathTex to raw strings: Tex("\\frac{1}{2}") → Tex(r"\frac{1}{2}")
   - Ensure double backslashes are converted to single in raw strings

6. **3D Scene handling**:
   - ThreeDScene methods may need updates
   - Camera configuration might need adjustment

7. **CONFIG dictionary**:
   - Old CONFIG dictionaries should be converted to __init__ parameters
   - Scene.CONFIG → class attributes or config decorators

8. **Pi Creatures**:
   - These have been commented out as they're not available in ManimCE
   - Don't try to fix these - they need custom assets

## Instructions:

1. Read through the converted files in: {self.output_dir / 'converted'}
2. For each file with issues:
   - Fix any syntax errors
   - Apply the pattern conversions listed above
   - Ensure the file can be imported without errors
3. Use the Edit tool to make corrections
4. Focus on files with known issues first
5. Create a summary of what you fixed

DO NOT:
- Try to run or render the scenes (just ensure syntactic correctness)
- Uncomment Pi Creature code (these need special assets)
- Make stylistic changes beyond what's needed for ManimCE compatibility
- Add new functionality

Start by checking files with syntax errors, then move to other pattern fixes.
"""
        
        return prompt
    
    def run_claude_sanity_check(self) -> Dict:
        """Run Claude sanity check with proper error handling and optional verbose output."""
        prompt = self.generate_sanity_check_prompt()
        
        # Save prompt for debugging
        prompt_file = self.output_dir / 'logs' / 'sanity_check_prompt.txt'
        prompt_file.parent.mkdir(exist_ok=True)
        with open(prompt_file, 'w') as f:
            f.write(prompt)
        
        try:
            claude_command = ["claude", "--dangerously-skip-permissions", "--model", "opus"]
            if self.verbose:
                # Run with output streaming
                logger.info("Running Claude with verbose output...")
                process = subprocess.Popen(
                    claude_command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                
                # Send prompt to stdin and close it
                process.stdin.write(prompt)
                process.stdin.close()
                
                stdout_lines = []
                
                # Read output in real-time
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        print(f"    Claude: {line.rstrip()}")
                        stdout_lines.append(line)
                
                # Get any remaining stderr
                stderr = process.stderr.read()
                
                # Save Claude's response
                response_file = self.output_dir / 'logs' / 'sanity_check_response.txt'
                with open(response_file, 'w') as f:
                    f.write(''.join(stdout_lines))
                
                if process.returncode == 0:
                    return {
                        "status": "completed",
                        "prompt_file": str(prompt_file),
                        "response_file": str(response_file)
                    }
                else:
                    return {
                        "status": "error",
                        "error": f"Claude returned non-zero exit code: {process.returncode}",
                        "stderr": stderr
                    }
                    
            else:
                # Run silently
                result = subprocess.run(
                    claude_command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout
                )
                
                # Save response
                response_file = self.output_dir / 'logs' / 'sanity_check_response.txt'
                with open(response_file, 'w') as f:
                    f.write(result.stdout)
                
                if result.returncode == 0:
                    return {
                        "status": "completed",
                        "prompt_file": str(prompt_file),
                        "response_file": str(response_file)
                    }
                else:
                    return {
                        "status": "error",
                        "error": f"Claude returned non-zero exit code: {result.returncode}",
                        "stderr": result.stderr
                    }
                    
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": "Claude sanity check timed out after 10 minutes"
            }
        except FileNotFoundError:
            return {
                "status": "error",
                "error": "Claude CLI not found. Please install it first."
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Unexpected error: {str(e)}"
            }
    
    def run(self):
        """Run the complete conversion process."""
        logger.info("Starting ManimGL to ManimCE conversion")
        
        self.setup_output_directory()
        self.convert_directory()
        
        # Add Claude sanity check here
        logger.info("Running Claude sanity check on converted files...")
        sanity_check_result = self.run_claude_sanity_check()
        if sanity_check_result['status'] == 'completed':
            logger.info("Claude sanity check completed successfully")
        else:
            logger.error(f"Claude sanity check failed: {sanity_check_result.get('error', 'Unknown error')}")
        
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
    
    converter = ManimConverter(args.source, args.output, verbose=args.verbose)
    converter.run()


if __name__ == '__main__':
    main()