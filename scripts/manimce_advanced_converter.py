#!/usr/bin/env python3
"""
Advanced ManimGL to ManimCE converter that integrates AST transformations,
API mappings, and intelligent pattern detection for high-quality conversions.
"""

import ast
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any
import subprocess
import tempfile
import shutil

# Import our modules
from manimce_ast_converter import convert_with_ast, analyze_manimgl_usage
from manimce_api_mappings import *
from manimce_conversion_utils import fix_string_continuations

logger = logging.getLogger(__name__)


class AdvancedManimConverter:
    """Advanced converter with AST transformation and comprehensive API mapping."""
    
    def __init__(self, source_dir: str, output_dir: str, verbose: bool = False,
                 enable_render_validation: bool = True, render_max_attempts: int = 3):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        self.enable_render_validation = enable_render_validation
        self.render_max_attempts = render_max_attempts
        
        # Conversion tracking
        self.conversion_stats = {
            'total_files': 0,
            'successful': 0,
            'failed': 0,
            'syntax_errors': 0,
            'render_validated': 0,
            'patterns_fixed': {}
        }
        
    def convert_file(self, file_path: Path) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Convert a single file with advanced techniques.
        
        Returns:
            Tuple of (converted_content, success, metadata)
        """
        logger.info(f"Converting {file_path} with advanced converter")
        metadata = {
            'file': str(file_path),
            'analysis': {},
            'conversions': [],
            'issues': [],
            'render_results': []
        }
        
        try:
            # Read original content
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Step 1: Analyze the code
            logger.info("Step 1: Analyzing ManimGL usage patterns...")
            analysis = analyze_manimgl_usage(original_content)
            metadata['analysis'] = analysis
            
            # Step 2: Pre-process for known issues
            logger.info("Step 2: Pre-processing for known issues...")
            preprocessed = self.preprocess_content(original_content, analysis)
            
            # Step 3: AST-based conversion
            logger.info("Step 3: Applying AST-based conversions...")
            ast_converted, conversion_log, ast_issues = convert_with_ast(preprocessed)
            metadata['conversions'].extend(conversion_log)
            metadata['issues'].extend(ast_issues)
            
            # Step 4: Apply additional pattern-based conversions
            logger.info("Step 4: Applying pattern-based conversions...")
            pattern_converted = self.apply_pattern_conversions(ast_converted, analysis)
            
            # Step 5: Post-process and clean up
            logger.info("Step 5: Post-processing and cleanup...")
            postprocessed = self.postprocess_content(pattern_converted, analysis, metadata)
            
            # Step 6: Add scene-specific code if needed
            logger.info("Step 6: Adding scene-specific implementations...")
            final_content = self.add_scene_implementations(postprocessed, analysis)
            
            # Step 7: Validate syntax
            logger.info("Step 7: Validating syntax...")
            try:
                compile(final_content, str(file_path), 'exec')
                logger.info("✓ Syntax validation passed")
            except SyntaxError as e:
                logger.error(f"Syntax error after conversion: {e}")
                metadata['issues'].append({
                    'type': 'syntax_error',
                    'error': str(e),
                    'line': e.lineno
                })
                self.conversion_stats['syntax_errors'] += 1
                # Try to fix common syntax errors
                final_content = self.fix_common_syntax_errors(final_content, e)
            
            # Step 8: Render validation if enabled
            if self.enable_render_validation and not any(i['type'] == 'syntax_error' for i in metadata['issues']):
                logger.info("Step 8: Validating rendering...")
                validated_content, render_success, render_results = self.validate_rendering(
                    file_path, original_content, final_content
                )
                metadata['render_results'] = render_results
                final_content = validated_content
                
                if render_success:
                    self.conversion_stats['render_validated'] += 1
            
            self.conversion_stats['successful'] += 1
            return final_content, True, metadata
            
        except Exception as e:
            logger.error(f"Failed to convert {file_path}: {e}")
            metadata['issues'].append({
                'type': 'conversion_error',
                'error': str(e)
            })
            self.conversion_stats['failed'] += 1
            return original_content, False, metadata
    
    def preprocess_content(self, content: str, analysis: Dict[str, Any]) -> str:
        """Pre-process content to fix known issues before AST parsing."""
        # Fix string continuations
        content = fix_string_continuations(content)
        
        # Remove problematic imports that break AST parsing
        lines = content.split('\n')
        new_lines = []
        
        for line in lines:
            # Skip imports from old modules that don't exist
            if re.match(r'from\s+old_projects', line):
                new_lines.append(f"# REMOVED: {line}")
                continue
            
            # Fix relative imports that might cause issues
            if re.match(r'from\s+\.\s+import', line):
                new_lines.append(f"# REMOVED: {line} # Relative import")
                continue
                
            new_lines.append(line)
        
        return '\n'.join(new_lines)
    
    def apply_pattern_conversions(self, content: str, analysis: Dict[str, Any]) -> str:
        """Apply pattern-based conversions that AST might miss."""
        # Convert tex_to_color_map patterns
        content = self.convert_tex_to_color_map(content)
        
        # Convert direction combinations
        for old_dir, new_dir in DIRECTION_MAPPINGS.items():
            content = re.sub(rf'\b{re.escape(old_dir)}\b', new_dir, content)
        
        # Convert color names
        for old_color, new_color in COLOR_MAPPINGS.items():
            content = re.sub(rf'\b{old_color}\b', new_color, content)
        
        # Handle LaTeX strings in Text/Tex objects
        content = self.convert_latex_strings(content)
        
        # Convert ContinualAnimation patterns
        if analysis['features']['uses_continual_animation']:
            content = self.convert_continual_animations(content)
        
        return content
    
    def convert_tex_to_color_map(self, content: str) -> str:
        """Convert tex_to_color_map to set_color_by_text calls."""
        # Pattern to find TextMobject/Text with tex_to_color_map
        pattern = r'(\w+)\s*=\s*(TextMobject|Text)\((.*?)tex_to_color_map\s*=\s*{([^}]+)}(.*?)\)'
        
        def replace_tex_color_map(match):
            var_name = match.group(1)
            class_name = match.group(2)
            before_args = match.group(3)
            color_map = match.group(4)
            after_args = match.group(5)
            
            # Parse color mappings
            color_mappings = []
            for mapping in re.findall(r'"([^"]+)"\s*:\s*(\w+)', color_map):
                text, color = mapping
                color_mappings.append((text, color))
            
            # Create base object without tex_to_color_map
            result = f"{var_name} = {class_name}({before_args.rstrip(', ')}{after_args})"
            
            # Add set_color_by_text calls
            for text, color in color_mappings:
                result += f"\n{var_name}.set_color_by_text('{text}', {color})"
            
            return result
        
        return re.sub(pattern, replace_tex_color_map, content, flags=re.DOTALL)
    
    def convert_latex_strings(self, content: str) -> str:
        """Convert LaTeX strings to use raw strings appropriately."""
        # Convert strings in MathTex/Tex that contain backslashes
        patterns = [
            (r'(MathTex|Tex)\s*\(\s*"([^"]*\\[^"]*)"', r'\1(r"\2"'),
            (r"(MathTex|Tex)\s*\(\s*'([^']*\\[^']*)'", r"\1(r'\2')"),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        
        # Convert double backslashes to single in raw strings
        content = re.sub(r'(r["\'])([^"\']*?)\\\\([^"\']*?)\1', r'\1\2\\\3\1', content)
        
        return content
    
    def convert_continual_animations(self, content: str) -> str:
        """Convert ContinualAnimation classes to updater functions."""
        # Find ContinualAnimation classes
        pattern = r'class\s+(\w+)\(ContinualAnimation\):(.*?)(?=\nclass|\n\w|\Z)'
        
        def convert_to_updater(match):
            class_name = match.group(1)
            class_body = match.group(2)
            
            # Extract update_mobject method
            update_pattern = r'def\s+update_mobject\(self,\s*dt\):(.*?)(?=\n\s{0,4}\w|\Z)'
            update_match = re.search(update_pattern, class_body, re.DOTALL)
            
            if update_match:
                update_body = update_match.group(1)
                
                # Convert self references to mobject references
                update_body = re.sub(r'\bself\.mobject\b', 'mobject', update_body)
                update_body = re.sub(r'\bself\b', 'mobject', update_body)
                
                # Create updater function
                func_name = f"{class_name.lower()}_updater"
                updater_code = f"""
def {func_name}(mobject, dt):
    \"\"\"Updater function converted from {class_name}.\"\"\"
{update_body}

# Usage: mobject.add_updater({func_name})
# To remove: mobject.remove_updater({func_name})
"""
                return updater_code
            
            return match.group(0)
        
        return re.sub(pattern, convert_to_updater, content, flags=re.DOTALL)
    
    def postprocess_content(self, content: str, analysis: Dict[str, Any], 
                          metadata: Dict[str, Any]) -> str:
        """Post-process content for final cleanup using enhanced regex techniques."""
        # Apply regex helper's superior techniques if available
        if hasattr(self, 'regex_helper') and self.regex_helper:
            logger.info("Applying enhanced regex techniques for superior quality")
            
            # Use regex helper's sophisticated Pi Creature handling
            from pathlib import Path
            temp_path = Path("temp_conversion")  # Dummy path for the method
            has_pi_creature = self.regex_helper.detect_pi_creature_usage(content, temp_path)
            if has_pi_creature:
                content = self.regex_helper.comment_out_pi_creature_usage(content)
                metadata['conversions'].append("Applied sophisticated Pi Creature commenting")
            
            # Use regex helper's import filtering
            content = self.regex_helper.convert_imports(content)
            
            # Use regex helper's string continuation fixes
            content = self.regex_helper.fix_string_continuations(content)
            
            # Use regex helper's TeX parentheses fixes
            content = self.regex_helper.fix_tex_parentheses(content)
            
            metadata['conversions'].append("Applied enhanced regex post-processing")
        
        # Original post-processing logic
        lines = content.split('\n')
        new_lines = []
        
        # Track imports
        has_manim_import = False
        import_section_end = 0
        
        for i, line in enumerate(lines):
            # Check for manim import
            if 'from manim import *' in line:
                has_manim_import = True
            
            # Find end of import section
            if line.strip() and not line.strip().startswith('#'):
                if not line.startswith(('import', 'from')):
                    if import_section_end == 0:
                        import_section_end = i
            
            # Remove empty class definitions from failed conversions
            if re.match(r'class\s+\w+\(\s*\):', line):
                new_lines.append(f"# REMOVED: {line} # Empty class from failed conversion")
                continue
            
            new_lines.append(line)
        
        # Ensure manim import
        if not has_manim_import:
            new_lines.insert(import_section_end, 'from manim import *')
            new_lines.insert(import_section_end + 1, '')
            metadata['conversions'].append("Added: from manim import *")
        
        return '\n'.join(new_lines)
    
    def add_scene_implementations(self, content: str, analysis: Dict[str, Any]) -> str:
        """Add scene-specific implementations for GraphScene, NumberLineScene, etc."""
        lines = content.split('\n')
        new_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check for GraphScene inheritance
            graph_scene_match = re.match(r'class\s+(\w+)\(.*GraphScene.*?\):', line)
            if graph_scene_match:
                class_name = graph_scene_match.group(1)
                new_lines.append(line)
                i += 1
                
                # Add GraphScene implementation after class definition
                indent = '    '
                new_lines.extend([
                    f"{indent}# GraphScene compatibility methods",
                    f"{indent}def __init__(self, **kwargs):",
                    f"{indent}    super().__init__(**kwargs)",
                    f"{indent}    self.x_min = getattr(self, 'x_min', -10)",
                    f"{indent}    self.x_max = getattr(self, 'x_max', 10)",
                    f"{indent}    self.y_min = getattr(self, 'y_min', -5)",
                    f"{indent}    self.y_max = getattr(self, 'y_max', 5)",
                    f"{indent}    self.x_axis_step = getattr(self, 'x_axis_step', 1)",
                    f"{indent}    self.y_axis_step = getattr(self, 'y_axis_step', 1)",
                    f"{indent}    self.axes = None",
                    ""
                ])
                
                # Add the template methods
                template_lines = SCENE_TEMPLATES['GraphScene'].strip().split('\n')
                new_lines.extend(template_lines)
                new_lines.append("")
                
                # Skip to the original class body
                continue
            
            # Check for NumberLineScene inheritance
            number_scene_match = re.match(r'class\s+(\w+)\(.*NumberLineScene.*?\):', line)
            if number_scene_match:
                new_lines.append(line.replace('NumberLineScene', 'Scene'))
                i += 1
                
                # Add NumberLineScene implementation
                template_lines = SCENE_TEMPLATES['NumberLineScene'].strip().split('\n')
                new_lines.extend(template_lines)
                new_lines.append("")
                
                continue
            
            new_lines.append(line)
            i += 1
        
        return '\n'.join(new_lines)
    
    def fix_common_syntax_errors(self, content: str, error: SyntaxError) -> str:
        """Try to fix common syntax errors."""
        lines = content.split('\n')
        
        if error.msg == 'invalid syntax' and error.lineno:
            # Try to fix the specific line
            line_idx = error.lineno - 1
            if line_idx < len(lines):
                problem_line = lines[line_idx]
                
                # Fix property assignment in wrong context
                if '=' in problem_line and '.width' in problem_line:
                    # This might be a width assignment that needs different handling
                    lines[line_idx] = f"# FIXME: {problem_line} # Property assignment syntax error"
                
                # Fix empty parentheses in class definition
                elif re.match(r'class\s+\w+\(\s*\):', problem_line):
                    lines[line_idx] = re.sub(r'\(\s*\)', '(Scene)', problem_line)
        
        return '\n'.join(lines)
    
    def validate_rendering(self, file_path: Path, original_content: str, 
                         converted_content: str) -> Tuple[str, bool, List[Dict]]:
        """Validate that the converted code can render."""
        # Extract scenes
        scenes = self.extract_scene_names(converted_content)
        if not scenes:
            logger.info("No scenes found to validate")
            return converted_content, True, []
        
        # Test first scene
        scene_name = scenes[0]
        logger.info(f"Testing render of scene: {scene_name}")
        
        render_results = []
        current_content = converted_content
        
        for attempt in range(self.render_max_attempts):
            # Write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(current_content)
                temp_file = f.name
            
            try:
                # Try to render
                result = self.test_render_scene(temp_file, scene_name)
                render_results.append(result)
                
                if result['success']:
                    logger.info(f"✓ Scene {scene_name} renders successfully!")
                    return current_content, True, render_results
                
                # Try to fix the error
                if attempt < self.render_max_attempts - 1:
                    logger.info(f"Render failed (attempt {attempt + 1}), trying to fix...")
                    fixed_content = self.fix_render_error(current_content, result['error'])
                    if fixed_content != current_content:
                        current_content = fixed_content
                    else:
                        logger.warning("Could not generate fix for render error")
                        break
                        
            finally:
                # Clean up temp file
                Path(temp_file).unlink(missing_ok=True)
        
        logger.warning(f"Failed to validate rendering after {self.render_max_attempts} attempts")
        return current_content, False, render_results
    
    def extract_scene_names(self, content: str) -> List[str]:
        """Extract all Scene class names from the content."""
        scene_pattern = r'class\s+(\w+)\(.*Scene.*?\):'
        return re.findall(scene_pattern, content)
    
    def test_render_scene(self, file_path: str, scene_name: str) -> Dict[str, Any]:
        """Test rendering a specific scene."""
        try:
            cmd = [
                "manim", file_path, scene_name,
                "-ql",  # Low quality for speed
                "--disable_caching",
                "-s",  # Just save last frame
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {"success": True, "scene": scene_name}
            else:
                # Extract meaningful error
                error_lines = result.stderr.strip().split('\n')
                error_msg = '\n'.join([
                    line for line in error_lines 
                    if any(keyword in line.lower() for keyword in ['error', 'traceback', 'file'])
                ])[-500:]  # Last 500 chars
                
                return {
                    "success": False,
                    "scene": scene_name,
                    "error": error_msg or result.stderr[-500:]
                }
                
        except subprocess.TimeoutExpired:
            return {"success": False, "scene": scene_name, "error": "Render timeout"}
        except Exception as e:
            return {"success": False, "scene": scene_name, "error": str(e)}
    
    def fix_render_error(self, content: str, error: str) -> str:
        """Try to fix common render errors."""
        # Common error patterns and fixes
        if "has no attribute 'c2p'" in error:
            # Missing axes initialization
            content = re.sub(
                r'(self\.axes\.c2p)',
                r'self.coords_to_point',
                content
            )
        
        elif "name 'Create' is not defined" in error:
            # Missing import
            if 'from manim import *' not in content:
                lines = content.split('\n')
                lines.insert(0, 'from manim import *')
                content = '\n'.join(lines)
        
        elif "unexpected keyword argument" in error:
            # Extract the problematic argument
            arg_match = re.search(r"unexpected keyword argument '(\w+)'", error)
            if arg_match:
                bad_arg = arg_match.group(1)
                # Remove this argument from calls
                content = re.sub(f'{bad_arg}\\s*=\\s*[^,)]+,?', '', content)
        
        elif "WIDTH" in error or "HEIGHT" in error:
            # Frame constant issues
            replacements = {
                'FRAME_WIDTH': 'config.frame_width',
                'FRAME_HEIGHT': 'config.frame_height',
            }
            for old, new in replacements.items():
                content = re.sub(rf'\b{old}\b', new, content)
        
        return content
    
    def generate_conversion_report(self) -> Dict[str, Any]:
        """Generate a detailed conversion report."""
        return {
            'stats': self.conversion_stats,
            'common_issues': self.analyze_common_issues(),
            'recommendations': self.generate_recommendations()
        }
    
    def analyze_common_issues(self) -> List[Dict[str, Any]]:
        """Analyze patterns in conversion issues."""
        # This would analyze the accumulated metadata to find patterns
        return []
    
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on conversion results."""
        recommendations = []
        
        if self.conversion_stats['syntax_errors'] > 0:
            recommendations.append(
                "Several files had syntax errors after conversion. "
                "Consider manual review of complex class inheritance patterns."
            )
        
        if self.conversion_stats.get('render_validated', 0) < self.conversion_stats['successful']:
            recommendations.append(
                "Not all files were render-validated. "
                "Consider running full render tests on converted files."
            )
        
        return recommendations