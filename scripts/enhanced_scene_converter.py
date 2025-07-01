#!/usr/bin/env python3
"""
Enhanced Scene Converter - Integrated Dependency Analysis and Validation

This module integrates scene conversion, dependency analysis, and render validation
into a single coherent pipeline, solving the "0 dependencies" issue and providing
better error isolation.

Key Features:
- Real-time dependency analysis during conversion
- Scene-level render validation  
- Self-contained snippet generation
- Comprehensive metadata tracking
"""

import ast
import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import existing components
from scripts.manimce_conversion_utils import apply_all_conversions
from scripts.ast_systematic_converter import ASTSystematicConverter
from scripts.manimce_precompile_validator import ManimCEPrecompileValidator
from scripts.pre_conversion_validator import PreConversionValidator, ValidationResult

# Configure logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Conditional import for Claude error fixer (may not always be available)
try:
    from scripts.claude_api_helper import ClaudeErrorFixer
    CLAUDE_AVAILABLE = True
except ImportError:
    logger.warning("Claude API helper not available - error fixing disabled")
    CLAUDE_AVAILABLE = False
    ClaudeErrorFixer = None

# Import validation failure auto-recovery system
try:
    from scripts.validation_failure_recovery import ValidationFailureRecovery
    AUTO_RECOVERY_AVAILABLE = True
except ImportError:
    logger.warning("Validation failure auto-recovery not available")
    AUTO_RECOVERY_AVAILABLE = False
    ValidationFailureRecovery = None

# Import unfixable pattern detector
try:
    from scripts.unfixable_pattern_detector import UnfixablePatternDetector, FixabilityLevel
    UNFIXABLE_DETECTOR_AVAILABLE = True
except ImportError:
    logger.warning("Unfixable pattern detector not available")
    UNFIXABLE_DETECTOR_AVAILABLE = False
    UnfixablePatternDetector = None


class FunctionDependencyVisitor(ast.NodeVisitor):
    """Helper visitor to analyze function bodies for dependencies."""
    
    def __init__(self):
        self.used_names = set()
        self.used_functions = set()
    
    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.used_functions.add(node.func.id)
        self.generic_visit(node)


class DependencyAnalyzer(ast.NodeVisitor):
    """Analyze AST to find dependencies for a given scene."""
    
    def __init__(self, module_ast: ast.Module, scene_name: str):
        self.module_ast = module_ast
        self.scene_name = scene_name
        self.scene_node = None
        
        # Dependencies to track
        self.used_functions: Set[str] = set()
        self.used_names: Set[str] = set()
        self.used_classes: Set[str] = set()
        self.used_imports: Set[str] = set()
        
        # Module-level definitions
        self.module_functions: Dict[str, ast.FunctionDef] = {}
        self.module_classes: Dict[str, ast.ClassDef] = {}
        self.module_constants: Dict[str, ast.AST] = {}
        self.module_imports: List[ast.AST] = []
        
        # Current context
        self.current_class = None
        self.in_scene = False
        
        # Analyze module first
        self._analyze_module()
        
    def _analyze_module(self):
        """Extract module-level definitions."""
        for node in self.module_ast.body:
            if isinstance(node, ast.FunctionDef):
                self.module_functions[node.name] = node
            elif isinstance(node, ast.ClassDef):
                self.module_classes[node.name] = node
                if node.name == self.scene_name:
                    self.scene_node = node
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self.module_imports.append(node)
            elif isinstance(node, ast.Assign):
                # Track module-level constants
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.module_constants[target.id] = node
    
    def analyze_scene(self) -> Dict[str, Any]:
        """Analyze the scene and return its dependencies."""
        if not self.scene_node:
            return {}
        
        # Find base classes
        base_classes = []
        for base in self.scene_node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
        
        # Visit the scene node
        self.in_scene = True
        self.visit(self.scene_node)
        self.in_scene = False
        
        # Collect all dependencies
        dependencies = {
            'functions': self._collect_function_dependencies(),
            'classes': self._collect_class_dependencies(base_classes),
            'constants': self._collect_constant_dependencies(),
            'imports': self._collect_import_dependencies(),
            'base_classes': base_classes
        }
        
        return dependencies
    
    def visit_Call(self, node: ast.Call):
        """Track function calls."""
        if self.in_scene:
            if isinstance(node.func, ast.Name):
                self.used_functions.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                # Track method calls that might be module functions
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                    # Skip self.method() calls
                    pass
                else:
                    # Could be a function from an imported module
                    self.used_functions.add(ast.unparse(node.func))
        
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name):
        """Track name references."""
        if self.in_scene and isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        
        self.generic_visit(node)
    
    def _collect_function_dependencies(self) -> Dict[str, ast.FunctionDef]:
        """Collect all functions used by the scene."""
        result = {}
        to_process = list(self.used_functions)
        processed = set()
        
        while to_process:
            func_name = to_process.pop(0)
            if func_name in processed or func_name not in self.module_functions:
                continue
                
            processed.add(func_name)
            result[func_name] = self.module_functions[func_name]
            
            # Analyze function body for more dependencies
            func_analyzer = FunctionDependencyVisitor()
            func_analyzer.visit(self.module_functions[func_name])
            
            # Add newly found dependencies
            for name in func_analyzer.used_names:
                if name in self.module_functions and name not in processed:
                    to_process.append(name)
                # Also track constants used by functions
                if name in self.module_constants:
                    self.used_names.add(name)
        
        return result
    
    def _collect_class_dependencies(self, base_classes: List[str]) -> Dict[str, ast.ClassDef]:
        """Collect all classes used by the scene."""
        result = {}
        to_process = list(base_classes) + [name for name in self.used_names if name in self.module_classes]
        processed = set()
        
        while to_process:
            class_name = to_process.pop(0)
            if class_name in processed or class_name not in self.module_classes or class_name == 'Scene':
                continue
                
            processed.add(class_name)
            result[class_name] = self.module_classes[class_name]
            
            # Analyze class body for dependencies
            class_analyzer = FunctionDependencyVisitor()
            class_analyzer.visit(self.module_classes[class_name])
            
            # Add dependencies found in class
            for name in class_analyzer.used_names:
                if name in self.module_classes and name not in processed:
                    to_process.append(name)
                # Track constants used by classes
                if name in self.module_constants:
                    self.used_names.add(name)
            
            # Check base classes of this class
            class_node = self.module_classes[class_name]
            for base in class_node.bases:
                if isinstance(base, ast.Name) and base.id in self.module_classes:
                    if base.id not in processed:
                        to_process.append(base.id)
        
        return result
    
    def _collect_constant_dependencies(self) -> Dict[str, ast.AST]:
        """Collect all constants used by the scene."""
        result = {}
        
        for name in self.used_names:
            if name in self.module_constants:
                result[name] = self.module_constants[name]
        
        return result
    
    def _collect_import_dependencies(self) -> List[ast.AST]:
        """Determine which imports are needed."""
        # For now, include all imports (conservative approach)
        # TODO: Smart import filtering based on usage
        return self.module_imports


class SceneRenderValidator:
    """Validates individual scenes by attempting to render them."""
    
    def __init__(self, verbose: bool = False, timeout: int = 30):
        self.verbose = verbose
        self.timeout = timeout
        
    def validate_scene_by_rendering(self, snippet_content: str, scene_name: str, 
                                  output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Test render a scene snippet to validate it works.
        
        Args:
            snippet_content: Self-contained scene code
            scene_name: Name of the scene to render
            output_dir: Directory to save render output (optional)
            
        Returns:
            Dict with validation results including success, errors, render_time, etc.
        """
        result = {
            'success': False,
            'scene_name': scene_name,
            'render_time': 0,
            'output_file': None,
            'error': None,
            'stdout': '',
            'stderr': ''
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Create temporary scene file
                scene_file = Path(temp_dir) / f"{scene_name}_test.py"
                with open(scene_file, 'w', encoding='utf-8') as f:
                    f.write(snippet_content)
                
                # Prepare render command
                if output_dir:
                    output_dir = Path(output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    media_dir = output_dir
                else:
                    media_dir = Path(temp_dir) / 'media'
                
                cmd = [
                    'manim', str(scene_file), scene_name,
                    '--media_dir', str(media_dir),
                    '-ql',  # Low quality for speed
                    '-s',   # Save last frame only
                    '--disable_caching'
                ]
                
                # Run render with timeout
                start_time = time.time()
                process = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=self.timeout,
                    cwd=temp_dir
                )
                result['render_time'] = time.time() - start_time
                
                result['stdout'] = process.stdout
                result['stderr'] = process.stderr
                
                if process.returncode == 0:
                    # Check if output file was created
                    expected_output = media_dir / 'images' / f'{scene_name}_test' / f'{scene_name}_ManimCE_*.png'
                    output_files = list(media_dir.glob('images/**/*.png'))
                    
                    if output_files:
                        result['success'] = True
                        result['output_file'] = str(output_files[0])
                        
                        # Copy to output directory if specified
                        if output_dir and output_dir != media_dir:
                            import shutil
                            dest_file = output_dir / f"{scene_name}_validation.png"
                            shutil.copy2(output_files[0], dest_file)
                            result['output_file'] = str(dest_file)
                    else:
                        result['error'] = 'Render completed but no output file created'
                else:
                    result['error'] = f'Manim exit code: {process.returncode}'
                    
            except subprocess.TimeoutExpired:
                result['error'] = f'Render timeout after {self.timeout} seconds'
            except Exception as e:
                result['error'] = f'Render validation failed: {str(e)}'
                
        return result


class EnhancedSceneConverter:
    """
    Unified scene processor that combines conversion, dependency analysis, 
    and validation into a single pipeline.
    """
    
    def __init__(self, enable_render_validation: bool = True, 
                 enable_precompile_validation: bool = True,
                 enable_pre_conversion_validation: bool = True,
                 enable_claude_fixes: bool = True,
                 enable_auto_recovery: bool = True,
                 verbose: bool = False, render_timeout: int = 15,
                 max_fix_attempts: int = 2, min_conversion_confidence: float = 0.8):
        self.enable_render_validation = enable_render_validation
        self.enable_precompile_validation = enable_precompile_validation
        self.enable_pre_conversion_validation = enable_pre_conversion_validation
        self.enable_claude_fixes = enable_claude_fixes
        self.enable_auto_recovery = enable_auto_recovery
        self.verbose = verbose
        self.render_timeout = render_timeout
        self.max_fix_attempts = max_fix_attempts
        self.min_conversion_confidence = min_conversion_confidence
        
        # Initialize validators
        if self.enable_pre_conversion_validation:
            self.pre_conversion_validator = PreConversionValidator(verbose=verbose)
            
        if self.enable_precompile_validation:
            self.precompile_validator = ManimCEPrecompileValidator(verbose=verbose)
        
        if self.enable_render_validation:
            self.render_validator = SceneRenderValidator(verbose=verbose, timeout=render_timeout)
        
        # Initialize validation failure auto-recovery
        if self.enable_auto_recovery and AUTO_RECOVERY_AVAILABLE:
            self.auto_recovery = ValidationFailureRecovery(verbose=verbose)
        elif self.enable_auto_recovery and not AUTO_RECOVERY_AVAILABLE:
            logger.warning("Auto-recovery requested but not available - disabling")
            self.enable_auto_recovery = False
            self.auto_recovery = None
        else:
            self.auto_recovery = None
        
        # Initialize Claude error fixer
        if self.enable_claude_fixes and CLAUDE_AVAILABLE:
            self.claude_fixer = ClaudeErrorFixer(
                verbose=verbose, 
                timeout=45,  # Fixed 45 second timeout for Claude
                max_attempts=max_fix_attempts,
                use_model_strategy=True  # Enable smart model selection
            )
        elif self.enable_claude_fixes and not CLAUDE_AVAILABLE:
            logger.warning("Claude fixes requested but not available - disabling")
            self.enable_claude_fixes = False
            self.claude_fixer = None
        else:
            self.claude_fixer = None
        
        # Initialize unfixable pattern detector
        self.unfixable_detector = UnfixablePatternDetector() if UNFIXABLE_DETECTOR_AVAILABLE else None
        self.unfixable_stats = {'skipped': 0, 'attempted': 0, 'patterns': {}}
        # Start in monitoring mode - log but don't skip
        self.unfixable_monitor_only = True
        
        if self.unfixable_detector:
            logger.info("Unfixable pattern detector enabled in MONITORING mode - will log but not skip")
        
        logger.info(f"Enhanced Scene Converter initialized (render={enable_render_validation}, precompile={enable_precompile_validation}, auto_recovery={enable_auto_recovery}, claude={enable_claude_fixes})")
    
    def process_scene(self, scene_name: str, scene_content: str, 
                     full_module_ast: ast.Module, video_name: str = "",
                     output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Complete scene processing pipeline:
        1. Convert ManimGL → ManimCE
        2. Analyze dependencies 
        3. Create self-contained snippet
        4. Validate by precompilation and rendering
        5. Return comprehensive results
        
        Args:
            scene_name: Name of the scene class
            scene_content: Original scene code
            full_module_ast: AST of the complete module for dependency analysis
            video_name: Name of the video (for metadata)
            output_dir: Directory to save validation outputs
            
        Returns:
            Dict with comprehensive processing results
        """
        result = {
            'scene_name': scene_name,
            'success': False,
            'content': scene_content,
            'converted_content': '',
            'snippet': '',
            'dependencies': {},
            'validation': {
                'precompile': {'success': False},
                'render': {'success': False}
            },
            'metadata': {
                'video_name': video_name,
                'original_lines': len(scene_content.splitlines()),
                'converted_lines': 0,
                'processing_time': 0
            },
            'errors': [],
            'pre_conversion_validation': None
        }
        
        start_time = time.time()
        
        # Quick complexity check - skip extremely large scenes that will likely timeout
        lines_count = len(scene_content.splitlines())
        if lines_count > 1000:  # Skip scenes larger than 1000 lines
            logger.warning(f"Skipping {scene_name} - too large ({lines_count} lines, likely to timeout)")
            result['success'] = False
            result['errors'] = [f"Scene too large ({lines_count} lines) - skipped to prevent timeout"]
            result['metadata']['processing_time'] = time.time() - start_time
            result['metadata']['skipped_reason'] = 'too_large'
            return result
        
        try:
            # Step 0: Pre-conversion validation
            if self.enable_pre_conversion_validation:
                logger.info(f"Pre-conversion validation: {scene_name}")
                pre_validation = self.pre_conversion_validator.validate_code(
                    scene_content, f"{video_name}/{scene_name}.py"
                )
                result['pre_conversion_validation'] = {
                    'confidence': pre_validation.conversion_confidence,
                    'is_valid': pre_validation.is_valid,
                    'error_count': sum(1 for i in pre_validation.issues if i.severity.value == 'error'),
                    'warning_count': sum(1 for i in pre_validation.issues if i.severity.value == 'warning'),
                    'issues': [
                        {
                            'severity': i.severity.value,
                            'line': i.line,
                            'type': i.issue_type,
                            'message': i.message,
                            'suggestion': i.suggestion
                        }
                        for i in pre_validation.issues[:10]  # First 10 issues
                    ]
                }
                
                # Log confidence level
                if pre_validation.conversion_confidence < 0.3:
                    logger.warning(f"Low conversion confidence ({pre_validation.conversion_confidence:.1%}) for {scene_name}")
                elif pre_validation.conversion_confidence < 0.7:
                    logger.info(f"Medium conversion confidence ({pre_validation.conversion_confidence:.1%}) for {scene_name}")
                    
                # Check if confidence is below threshold - skip if too low
                if pre_validation.conversion_confidence < self.min_conversion_confidence:
                    logger.info(f"Skipping {scene_name} - conversion confidence ({pre_validation.conversion_confidence:.1%}) below threshold ({self.min_conversion_confidence:.1%})")
                    return {
                        'status': 'skipped_low_confidence',
                        'scene_name': scene_name,
                        'conversion_confidence': pre_validation.conversion_confidence,
                        'min_threshold': self.min_conversion_confidence,
                        'reason': f'Conversion confidence ({pre_validation.conversion_confidence:.1%}) below minimum threshold ({self.min_conversion_confidence:.1%})',
                        'pre_conversion_validation': result['pre_conversion_validation']
                    }
                    
                # Save for Claude context
                self._last_pre_validation = result['pre_conversion_validation']
            
            # Step 1: Convert ManimGL → ManimCE
            if self.verbose:
                logger.info(f"Converting scene: {scene_name}")
            converted_content = self._convert_scene_content(scene_content)
            result['converted_content'] = converted_content
            result['metadata']['converted_lines'] = len(converted_content.splitlines())
            
            # Step 2: Analyze dependencies  
            logger.debug(f"Analyzing dependencies: {scene_name}")
            dependencies = self._analyze_dependencies(scene_name, full_module_ast)
            result['dependencies'] = self._format_dependencies(dependencies)
            
            # Step 3: Create self-contained snippet
            logger.debug(f"Creating snippet: {scene_name}")  
            snippet = self._create_self_contained_snippet(
                scene_name, converted_content, dependencies, video_name
            )
            result['snippet'] = snippet
            
            # Step 4: Validate by precompilation
            if self.enable_precompile_validation:
                logger.debug(f"Precompile validation: {scene_name}")
                precompile_result = self._validate_precompile(snippet, scene_name)
                result['validation']['precompile'] = precompile_result
                
                # If precompile validation was fixed by auto-recovery, update the snippet
                if 'fixed_content' in precompile_result:
                    snippet = precompile_result['fixed_content']
                    result['snippet'] = snippet
                    result['metadata']['auto_recovery_precompile'] = precompile_result.get('auto_recovery_changes', [])
            
            # Step 5: Validate by rendering
            if self.enable_render_validation:
                logger.debug(f"Render validation: {scene_name}")
                render_result = self._validate_render(snippet, scene_name, output_dir)
                result['validation']['render'] = render_result
                
                # If rendering succeeded after fixes, update the snippet
                if render_result['success'] and 'fixed_content' in render_result:
                    claude_fixes = render_result.get('fix_attempts', 0)
                    auto_recovery_applied = render_result.get('auto_recovery_applied', False)
                    
                    if claude_fixes > 0:
                        logger.info(f"Using fixed snippet after {claude_fixes} Claude fixes")
                        result['metadata']['claude_fixes_applied'] = claude_fixes
                    
                    if auto_recovery_applied:
                        logger.info(f"Auto-recovery applied during render validation")
                        result['metadata']['auto_recovery_render'] = render_result.get('auto_recovery_changes', [])
                    
                    result['snippet'] = render_result['fixed_content']
            
            # Determine overall success
            # Consider validation successful if auto-recovery fixed the issues
            precompile_had_issues = (self.enable_precompile_validation and 
                                   result['metadata'].get('initial_precompile_valid') == False)
            precompile_ok = (not self.enable_precompile_validation or 
                           result['validation']['precompile']['success'])
            render_ok = (not self.enable_render_validation or 
                        result['validation']['render']['success'])
            
            result['success'] = precompile_ok and render_ok
            
            if result['success']:
                # Success logging moved to debug level
                if self.verbose:
                    success_details = []
                    if result['metadata'].get('auto_recovery_precompile') or result['metadata'].get('auto_recovery_render'):
                        auto_fixes = len(result['metadata'].get('auto_recovery_precompile', [])) + len(result['metadata'].get('auto_recovery_render', []))
                        success_details.append(f"{auto_fixes} auto-fixes")
                    if result['metadata'].get('claude_fixes_applied', 0) > 0:
                        success_details.append(f"{result['metadata']['claude_fixes_applied']} Claude fixes")
                    
                    detail_str = f" ({', '.join(success_details)})" if success_details else ""
                    logger.info(f"✅ {scene_name} succeeded{detail_str}")
                
                # Create success message with fix details
                success_details = []
                if result['metadata'].get('auto_recovery_precompile') or result['metadata'].get('auto_recovery_render'):
                    auto_fixes = len(result['metadata'].get('auto_recovery_precompile', [])) + len(result['metadata'].get('auto_recovery_render', []))
                    success_details.append(f"{auto_fixes} auto-recovery fixes")
                if result['metadata'].get('claude_fixes_applied', 0) > 0:
                    success_details.append(f"{result['metadata']['claude_fixes_applied']} Claude fixes")
                
                success_msg = f"✅ Scene {scene_name} processed successfully"
                if success_details:
                    success_msg += f" (with {', '.join(success_details)})"
                
                logger.info(success_msg)
            else:
                errors = []
                # More informative error messages
                if not precompile_ok:
                    if precompile_had_issues and result['metadata'].get('auto_recovery_precompile'):
                        errors.append(f"precompile validation failed after {len(result['metadata']['auto_recovery_precompile'])} auto-recovery attempts")
                    else:
                        errors.append("precompile validation failed")
                if not render_ok:
                    if result['metadata'].get('auto_recovery_render'):
                        errors.append(f"render validation failed after {len(result['metadata']['auto_recovery_render'])} auto-recovery attempts")
                    else:
                        errors.append("render validation failed")
                        
                # Only show warning if there were actual persistent issues
                if errors:
                    logger.warning(f"⚠️ {scene_name} has issues: {', '.join(errors)}")
                
        except Exception as e:
            logger.error(f"❌ Failed to process scene {scene_name}: {str(e)}")
            result['errors'].append(str(e))
            result['success'] = False
            
        finally:
            result['metadata']['processing_time'] = time.time() - start_time
            
        return result
    
    def _convert_scene_content(self, scene_content: str) -> str:
        """Convert ManimGL scene content to ManimCE using AST-based converter."""
        try:
            # PRIORITY 1: Use AST-based systematic converter (90%+ success rate)
            ast_converter = ASTSystematicConverter()
            converted = ast_converter.convert_code(scene_content)
            
            # Log conversion statistics
            report = ast_converter.get_conversion_report()
            logger.debug(f"AST Conversion: {report['transformations_applied']} transformations, "
                        f"{report['conversion_rate']:.1f}% rate, patterns: {report['patterns_matched']}")
            
            return converted
            
        except Exception as e:
            logger.warning(f"AST conversion failed: {e}, falling back to regex")
            # FALLBACK: Use regex-based conversion (legacy compatibility)
            try:
                converted = apply_all_conversions(scene_content)
                logger.debug("Fallback regex conversion succeeded")
                return converted
            except Exception as e2:
                logger.error(f"Both AST and regex conversion failed: {e2}")
                raise
    
    def _analyze_dependencies(self, scene_name: str, full_module_ast: ast.Module) -> Dict[str, Any]:
        """Analyze scene dependencies using existing DependencyAnalyzer."""
        try:
            analyzer = DependencyAnalyzer(full_module_ast, scene_name)
            dependencies = analyzer.analyze_scene()
            return dependencies
        except Exception as e:
            logger.error(f"Dependency analysis failed for {scene_name}: {e}")
            return {'functions': {}, 'classes': {}, 'constants': {}, 'imports': [], 'base_classes': []}
    
    def _format_dependencies(self, dependencies: Dict[str, Any]) -> Dict[str, Any]:
        """Format dependency information for reporting."""
        return {
            'functions': list(dependencies.get('functions', {}).keys()),
            'classes': list(dependencies.get('classes', {}).keys()),
            'constants': list(dependencies.get('constants', {}).keys()),
            'base_classes': dependencies.get('base_classes', []),
            'function_count': len(dependencies.get('functions', {})),
            'class_count': len(dependencies.get('classes', {})),
            'constant_count': len(dependencies.get('constants', {})),
            'import_count': len(dependencies.get('imports', []))
        }
    
    def _create_self_contained_snippet(self, scene_name: str, converted_content: str, 
                                     dependencies: Dict[str, Any], video_name: str) -> str:
        """Create a self-contained snippet with all dependencies."""
        try:
            # Create self-contained snippet with all dependencies
            parts = []
            
            # Header with metadata
            parts.append(f"# Video: {video_name}")
            parts.append(f"# Scene: {scene_name}")
            parts.append(f"# Auto-generated self-contained snippet")
            parts.append("")
            
            # Imports
            parts.append("from manim import *")
            
            # Check if custom animations are needed and add them
            custom_animation_classes = {'FlipThroughNumbers', 'DelayByOrder', 'ContinualAnimation'}
            added_custom_animations = set()  # Track which ones we've added
            uses_custom_animations = False
            
            # Check if any custom animations are used in the converted content
            for class_name in custom_animation_classes:
                if class_name in converted_content:
                    uses_custom_animations = True
                    break
            
            # Also check in original dependencies
            if dependencies.get('classes'):
                for class_name in dependencies['classes'].keys():
                    if class_name in custom_animation_classes:
                        uses_custom_animations = True
                        break
            
            if uses_custom_animations:
                # Import custom animations inline to make snippet self-contained
                parts.append("# Custom animation imports (inlined for self-containment)")
                custom_animations_path = os.path.join(os.path.dirname(__file__), 'manimce_custom_animations.py')
                try:
                    with open(custom_animations_path, 'r') as f:
                        custom_anim_content = f.read()
                        # Extract only the class definitions we need
                        custom_tree = ast.parse(custom_anim_content)
                        for node in custom_tree.body:
                            if isinstance(node, ast.ClassDef) and node.name in custom_animation_classes:
                                if node.name in converted_content or (dependencies.get('classes') and node.name in dependencies['classes']):
                                    parts.append(ast.unparse(node))
                                    parts.append("")
                                    added_custom_animations.add(node.name)
                except Exception as e:
                    logger.warning(f"Could not inline custom animations: {e}")
                    parts.append("# NOTE: Custom animations may need to be imported manually")
            
            # Add unique imports from dependencies (excluding manimlib-related imports)
            seen_imports = {'from manim import *', 'import manim'}
            for import_node in dependencies.get('imports', []):
                import_str = ast.unparse(import_node)
                if (import_str not in seen_imports and 
                    'from manim import' not in import_str and 
                    'import manim' not in import_str and
                    'manimlib' not in import_str and
                    'manim_imports_ext' not in import_str):
                    seen_imports.add(import_str)
                    parts.append(import_str)
            
            parts.append("")
            
            # Constants (deduplicated)
            seen_constants = set()
            if dependencies.get('constants'):
                parts.append("# Constants")
                for const_name, const_node in dependencies['constants'].items():
                    if const_name not in seen_constants:
                        seen_constants.add(const_name)
                        parts.append(ast.unparse(const_node))
                parts.append("")
            
            # Helper functions (deduplicated)
            seen_functions = set()
            if dependencies.get('functions'):
                parts.append("# Helper functions")
                for func_name, func_node in dependencies['functions'].items():
                    if func_name not in seen_functions:
                        seen_functions.add(func_name)
                        parts.append(ast.unparse(func_node))
                        parts.append("")
            
            # Base classes (excluding standard Scene classes and custom animations)
            seen_classes = set()
            if dependencies.get('classes'):
                # Filter out custom animations that we've already added
                filtered_classes = {
                    name: node for name, node in dependencies['classes'].items()
                    if name not in added_custom_animations  # Use the set we created above
                }
                
                if filtered_classes:
                    parts.append("# Required classes")
                    for class_name, class_node in filtered_classes.items():
                        if class_name not in seen_classes:
                            seen_classes.add(class_name)
                            parts.append(ast.unparse(class_node))
                            parts.append("")
            
            # The converted scene itself
            parts.append("# Main scene")
            parts.append(converted_content)
            
            return '\n'.join(parts)
            
        except Exception as e:
            logger.error(f"Failed to create snippet for {scene_name}: {e}")
            # Fallback to just the converted content
            return f"from manim import *\n\n{converted_content}"
    
    def _validate_precompile(self, snippet: str, scene_name: str) -> Dict[str, Any]:
        """Validate snippet using precompile validator with auto-recovery."""
        current_snippet = snippet
        auto_recovery_applied = False
        auto_recovery_changes = []
        
        try:
            validation_report = self.precompile_validator.validate_file(
                file_path=f"<snippet_{scene_name}>", 
                content=current_snippet
            )
            
            # If validation failed and auto-recovery is enabled, try to fix it
            if not validation_report.is_valid and self.enable_auto_recovery:
                error_messages = [error.message for error in validation_report.errors]
                combined_error = "; ".join(error_messages[:3])  # Combine first 3 errors
                
                logger.info(f"Precompile validation failed for {scene_name}, attempting auto-recovery...")
                
                fixed_snippet, recovery_success, changes_made = self.auto_recovery.auto_fix_validation_failure(
                    current_snippet, combined_error, scene_name
                )
                
                if recovery_success:
                    logger.info(f"Auto-recovery applied {len(changes_made)} precompile fixes: {', '.join(changes_made)}")
                    current_snippet = fixed_snippet
                    auto_recovery_applied = True
                    auto_recovery_changes = changes_made
                    
                    # Re-validate the fixed snippet
                    validation_report = self.precompile_validator.validate_file(
                        file_path=f"<snippet_{scene_name}>", 
                        content=current_snippet
                    )
            
            # Save errors for Claude context
            if validation_report.errors:
                self._last_precompile_errors = [error.message for error in validation_report.errors[:5]]
            else:
                self._last_precompile_errors = None
            
            result = {
                'success': validation_report.is_valid,
                'errors': len(validation_report.errors),
                'warnings': len(validation_report.warnings),
                'error_messages': [error.message for error in validation_report.errors[:5]]  # Limit for brevity
            }
            
            # Add auto-recovery metadata
            if auto_recovery_applied:
                result['auto_recovery_applied'] = True
                result['auto_recovery_changes'] = auto_recovery_changes
                result['fixed_content'] = current_snippet
            
            return result
            
        except Exception as e:
            self._last_precompile_errors = [f"Precompile validation failed: {str(e)}"]
            return {
                'success': False,
                'errors': 1,
                'warnings': 0,
                'error_messages': self._last_precompile_errors
            }
    
    def _validate_render(self, snippet: str, scene_name: str, 
                        output_dir: Optional[Path]) -> Dict[str, Any]:
        """Validate snippet by attempting to render it, with auto-recovery and Claude error recovery."""
        current_snippet = snippet
        attempt = 1
        all_results = []
        auto_recovery_applied = False
        auto_recovery_changes = []
        
        while attempt <= self.max_fix_attempts:
            try:
                # Try to render
                validation_result = self.render_validator.validate_scene_by_rendering(
                    current_snippet, scene_name, output_dir
                )
                all_results.append(validation_result)
                
                if validation_result['success']:
                    # Success! Return the result with fixed content if we made fixes
                    if attempt > 1 or auto_recovery_applied:
                        validation_result['fixed_content'] = current_snippet
                        validation_result['fix_attempts'] = attempt - 1
                        if auto_recovery_applied:
                            validation_result['auto_recovery_applied'] = True
                            validation_result['auto_recovery_changes'] = auto_recovery_changes
                    return validation_result
                
                # Render failed - try auto-recovery first (BEFORE Claude)
                error_message = validation_result.get('stderr', '') or validation_result.get('error', '')
                
                # If this is a timeout on a second+ attempt, skip Claude and fail fast
                if 'timeout' in error_message.lower() and attempt > 1:
                    logger.warning(f"Multiple render timeouts for {scene_name} - skipping further attempts")
                    break
                
                if self.enable_auto_recovery and not auto_recovery_applied and attempt == 1:
                    logger.info(f"Render failed for {scene_name}, attempting auto-recovery before Claude...")
                    
                    fixed_snippet, recovery_success, changes_made = self.auto_recovery.auto_fix_validation_failure(
                        current_snippet, error_message, scene_name
                    )
                    
                    if recovery_success:
                        logger.info(f"Auto-recovery applied {len(changes_made)} fixes: {', '.join(changes_made)}")
                        current_snippet = fixed_snippet
                        auto_recovery_applied = True
                        auto_recovery_changes = changes_made
                        # Continue to next iteration to test the auto-fixed code
                        continue
                    else:
                        logger.info(f"Auto-recovery could not fix this error pattern - proceeding to Claude")
                
                # Check if this error is unfixable before calling Claude
                should_skip_claude = False
                skip_reason = ""
                
                if self.unfixable_detector:
                    should_skip, skip_reason = self.unfixable_detector.should_skip_claude(
                        current_snippet, 
                        error_message, 
                        attempt - 1  # Previous attempts count
                    )
                    
                    if should_skip:
                        # In monitoring mode, just log what would happen
                        if self.unfixable_monitor_only:
                            logger.warning(f"[MONITOR] Would skip Claude API call for {scene_name}: {skip_reason}")
                            self.unfixable_stats['attempted'] += 1  # Count as attempted in monitor mode
                        else:
                            logger.warning(f"Skipping Claude API call for {scene_name}: {skip_reason}")
                            self.unfixable_stats['skipped'] += 1
                            should_skip_claude = True
                        
                        # Track the pattern
                        level, issues = self.unfixable_detector.analyze_code(current_snippet, error_message)
                        for issue in issues:
                            category = issue.split(':')[0]
                            self.unfixable_stats['patterns'][category] = self.unfixable_stats['patterns'].get(category, 0) + 1
                        
                        # If not in monitoring mode and should skip, return failure
                        if not self.unfixable_monitor_only and should_skip:
                            return {
                                'success': False,
                                'scene_name': scene_name,
                                'render_time': 0,
                                'error': error_message,
                                'unfixable_reason': skip_reason,
                                'unfixable_level': level.value
                            }
                
                # Auto-recovery failed or not attempted - try Claude if enabled and not unfixable
                if self.enable_claude_fixes and attempt < self.max_fix_attempts:
                    if not should_skip_claude:
                        logger.info(f"Render failed for {scene_name}, attempting Claude fix (attempt {attempt}/{self.max_fix_attempts})")
                    else:
                        logger.info(f"[MONITOR] Proceeding with Claude fix despite unfixable pattern detection")
                    
                    self.unfixable_stats['attempted'] += 1
                    
                    # Get additional context from precompile errors and pre-conversion validation
                    additional_context = {
                        'video_name': self._current_video_name if hasattr(self, '_current_video_name') else None,
                        'video_year': self._current_video_year if hasattr(self, '_current_video_year') else None
                    }
                    
                    # Add auto-recovery context if it was attempted
                    if auto_recovery_applied:
                        additional_context['auto_recovery_applied'] = True
                        additional_context['auto_recovery_changes'] = auto_recovery_changes
                    
                    if hasattr(self, '_last_precompile_errors'):
                        additional_context['precompile_errors'] = self._last_precompile_errors
                        
                    # Add pre-conversion validation insights
                    if hasattr(self, '_last_pre_validation') and self._last_pre_validation:
                        additional_context['pre_conversion_validation'] = {
                            'confidence': self._last_pre_validation.get('confidence', 0),
                            'error_count': self._last_pre_validation.get('error_count', 0),
                            'top_issues': self._last_pre_validation.get('issues', [])[:5]
                        }
                    
                    # Ask Claude to fix it
                    fix_result = self.claude_fixer.fix_render_error(
                        scene_name=scene_name,
                        snippet_content=current_snippet,
                        error_message=error_message,
                        attempt_number=attempt,
                        additional_context=additional_context
                    )
                    
                    if fix_result['success']:
                        logger.info(f"Claude fix applied: {', '.join(fix_result['changes_made'])}")
                        current_snippet = fix_result['fixed_content']
                    else:
                        logger.warning(f"Claude fix failed: {fix_result['error']}")
                        break
                else:
                    # No more attempts or Claude fixes disabled
                    break
                    
            except Exception as e:
                logger.error(f"Error during render validation: {str(e)}")
                all_results.append({
                    'success': False,
                    'scene_name': scene_name,
                    'render_time': 0,
                    'error': f"Render validation failed: {str(e)}"
                })
                break
            
            attempt += 1
        
        # All attempts failed - return the last result with all attempts
        final_result = all_results[-1] if all_results else {
            'success': False,
            'scene_name': scene_name,
            'render_time': 0,
            'error': "No render attempts made"
        }
        final_result['all_attempts'] = all_results
        final_result['total_attempts'] = len(all_results)
        
        # Add auto-recovery metadata to final result
        if auto_recovery_applied:
            final_result['auto_recovery_applied'] = True
            final_result['auto_recovery_changes'] = auto_recovery_changes
        
        return final_result

    def get_auto_recovery_statistics(self) -> Optional[Dict[str, Any]]:
        """Get auto-recovery usage statistics."""
        if self.auto_recovery:
            return self.auto_recovery.get_statistics()
        return None
    
    def get_unfixable_detector_statistics(self) -> Optional[Dict[str, Any]]:
        """Get unfixable pattern detector statistics."""
        if self.unfixable_detector:
            stats = dict(self.unfixable_stats)
            stats['detector_report'] = self.unfixable_detector.get_fixability_report()
            stats['monitor_mode'] = self.unfixable_monitor_only
            return stats
        return None
    
    def set_unfixable_monitor_mode(self, monitor_only: bool):
        """Set whether to only monitor unfixable patterns or actively skip Claude calls."""
        self.unfixable_monitor_only = monitor_only
        if self.unfixable_detector:
            mode = "MONITORING" if monitor_only else "ACTIVE"
            logger.info(f"Unfixable pattern detector set to {mode} mode")


def test_enhanced_converter():
    """Test function to validate the enhanced converter works."""
    # Test with a scene that has an error to test Claude fixing
    test_scene_content = '''
class TestScene(Scene):
    def construct(self):
        # This will fail - ShowCreation doesn't exist in ManimCE
        circle = Circle()
        self.play(ShowCreation(circle))
        self.wait()
'''
    
    # Create minimal AST for testing
    test_ast = ast.parse(test_scene_content)
    
    converter = EnhancedSceneConverter(
        enable_render_validation=True,
        enable_precompile_validation=True,
        enable_claude_fixes=True,
        verbose=True,
        max_fix_attempts=3
    )
    
    result = converter.process_scene(
        scene_name="TestScene",
        scene_content=test_scene_content,
        full_module_ast=test_ast,
        video_name="test_video"
    )
    
    print("\nTest Results:")
    print(f"Success: {result['success']}")
    print(f"Dependencies: {result['dependencies']}")
    print(f"Precompile: {result['validation']['precompile']['success']}")
    print(f"Render: {result['validation']['render']['success']}")
    if 'claude_fixes_applied' in result['metadata']:
        print(f"Claude fixes applied: {result['metadata']['claude_fixes_applied']}")
    
    if result['success'] and 'fixed_content' in result['validation']['render']:
        print("\nFixed snippet preview:")
        print(result['snippet'][:300] + "...")
    
    return result


if __name__ == "__main__":
    # Run test if called directly
    test_enhanced_converter()