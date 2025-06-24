#!/usr/bin/env python3
"""
AST-based converter for ManimGL to ManimCE conversion.

This module provides context-aware code transformations using Python's AST
to handle complex conversions that regex cannot properly address.
"""

import ast
import astor
from typing import Dict, List, Set, Optional, Tuple, Any
import re


class ManimASTTransformer(ast.NodeTransformer):
    """Main AST transformer for converting ManimGL code to ManimCE."""
    
    def __init__(self):
        self.imports_to_add: Set[str] = set()
        self.imports_to_remove: Set[str] = set()
        self.pi_creature_vars: Set[str] = set()
        self.conversion_log: List[str] = []
        self.issues: List[Dict[str, Any]] = []
        
        # Animation parameter mappings
        self.animation_mappings = {
            'ShowCreation': {
                'new_name': 'Create',
                'unsupported_params': ['lag_ratio'],
                'param_renames': {}
            },
            'ShowCreationThenDestruction': {
                'new_name': 'ShowPassingFlash',
                'unsupported_params': [],
                'param_renames': {}
            },
            'ShowCreationThenFadeOut': {
                'new_name': 'ShowPassingFlash',  # Approximate
                'unsupported_params': [],
                'param_renames': {}
            },
            'WiggleOutThenIn': {
                'new_name': 'Wiggle',
                'unsupported_params': [],
                'param_renames': {}
            },
            'CircleIndicate': {
                'new_name': 'Indicate',
                'unsupported_params': [],
                'param_renames': {}
            },
            'FlipThroughNumbers': {
                'new_name': 'FlipThroughNumbers',
                'unsupported_params': [],
                'param_renames': {},
                'requires_import': 'from manimce_custom_animations import FlipThroughNumbers'
            },
            'DelayByOrder': {
                'new_name': 'DelayByOrder',
                'unsupported_params': [],
                'param_renames': {},
                'requires_import': 'from manimce_custom_animations import DelayByOrder'
            }
        }
        
        # Method to property conversions
        self.method_to_property = {
            'get_width': 'width',
            'get_height': 'height',
            'get_x': 'x',
            'get_y': 'y',
            'get_z': 'z',
            'get_tex_string': 'tex_string',
            'get_fill_color': 'fill_color',
            'get_stroke_color': 'stroke_color',
            'get_fill_opacity': 'fill_opacity',
            'get_stroke_opacity': 'stroke_opacity',
            'get_stroke_width': 'stroke_width',
        }
        
        # Class name mappings
        self.class_mappings = {
            'TextMobject': 'Text',
            'TexMobject': 'MathTex',
            'TexText': 'Tex',
            'OldTex': 'Tex',
            'OldTexText': 'Text',
            'ContinualAnimation': None,  # Needs special handling
            'Mobject': 'Mobject',  # Base class exists in both
            'Mobject1D': 'VMobject',  # No direct equivalent
            'Mobject2D': 'VMobject',  # No direct equivalent
        }
        
    def visit_Import(self, node: ast.Import) -> Optional[ast.Import]:
        """Handle import statements."""
        new_names = []
        for alias in node.names:
            if alias.name.startswith('manimlib'):
                # Convert manimlib imports to manim
                new_name = alias.name.replace('manimlib', 'manim')
                new_alias = ast.alias(name=new_name, asname=alias.asname)
                new_names.append(new_alias)
                self.conversion_log.append(f"Converted import: {alias.name} → {new_name}")
            else:
                new_names.append(alias)
        
        if new_names:
            node.names = new_names
            return node
        return None
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> Optional[ast.ImportFrom]:
        """Handle from imports."""
        if node.module:
            # Handle manimlib imports
            if node.module.startswith('manimlib'):
                new_module = node.module.replace('manimlib', 'manim')
                node.module = new_module
                self.conversion_log.append(f"Converted import: from {node.module} → from {new_module}")
                return node
            
            # Remove custom imports
            if any(node.module.startswith(prefix) for prefix in ['custom.', 'once_useful_constructs.', 'stage_scenes']):
                self.conversion_log.append(f"Removed custom import: from {node.module}")
                return None
            
            # Handle manim_imports_ext
            if node.module == 'manim_imports_ext':
                node.module = 'manim'
                self.conversion_log.append("Converted: from manim_imports_ext → from manim")
                return node
        
        return node
    
    def visit_Call(self, node: ast.Call) -> ast.AST:
        """Handle function and method calls."""
        # Handle method to property conversions
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            
            # Convert get_* methods to properties
            if method_name in self.method_to_property and not node.args:
                prop_name = self.method_to_property[method_name]
                self.conversion_log.append(f"Converted method to property: .{method_name}() → .{prop_name}")
                return ast.Attribute(
                    value=node.func.value,
                    attr=prop_name,
                    ctx=ast.Load()
                )
            
            # Handle set_* methods
            if method_name.startswith('set_') and len(node.args) == 1:
                # Special cases for methods that stay as methods
                if method_name in ['set_color', 'set_fill', 'set_stroke']:
                    return self.generic_visit(node)
                
                # Convert set_width, set_height to property assignment
                if method_name in ['set_width', 'set_height']:
                    prop_name = method_name[4:]  # Remove 'set_'
                    # This needs to be handled at the statement level
                    # Mark for later processing
                    node._convert_to_assignment = (node.func.value, prop_name, node.args[0])
                    
        # Handle class instantiations
        if isinstance(node.func, ast.Name):
            class_name = node.func.id
            
            # Handle animation conversions
            if class_name in self.animation_mappings:
                mapping = self.animation_mappings[class_name]
                new_name = mapping['new_name']
                
                # Filter out unsupported parameters
                new_keywords = []
                for keyword in node.keywords:
                    if keyword.arg not in mapping['unsupported_params']:
                        # Rename parameters if needed
                        if keyword.arg in mapping['param_renames']:
                            keyword.arg = mapping['param_renames'][keyword.arg]
                        new_keywords.append(keyword)
                    else:
                        self.issues.append({
                            'type': 'unsupported_param',
                            'animation': class_name,
                            'param': keyword.arg,
                            'description': f"Parameter '{keyword.arg}' not supported in {new_name}"
                        })
                
                node.func.id = new_name
                node.keywords = new_keywords
                self.conversion_log.append(f"Converted animation: {class_name} → {new_name}")
                
                # Track required imports
                if 'requires_import' in mapping:
                    self.imports_to_add.add(mapping['requires_import'])
            
            # Handle class name mappings
            elif class_name in self.class_mappings:
                new_class = self.class_mappings[class_name]
                if new_class:
                    node.func.id = new_class
                    self.conversion_log.append(f"Converted class: {class_name} → {new_class}")
                    
                    # Special handling for Tex/Text with LaTeX
                    if new_class in ['Tex', 'MathTex'] and node.args:
                        # Convert string arguments to raw strings if they contain backslashes
                        for i, arg in enumerate(node.args):
                            if isinstance(arg, ast.Str) and '\\' in arg.s:
                                # Convert to raw string
                                node.args[i] = ast.Str(s=arg.s)
                                # Mark that this needs raw string handling
                                node.args[i]._needs_raw = True
            
            # Detect Pi Creature usage
            if any(pattern in class_name for pattern in ['PiCreature', 'Randolph', 'Mortimer']):
                self.pi_creature_vars.add(class_name)
                self.issues.append({
                    'type': 'pi_creature',
                    'class': class_name,
                    'description': f"Pi Creature class '{class_name}' used"
                })
        
        return self.generic_visit(node)
    
    def visit_Assign(self, node: ast.Assign) -> Optional[ast.AST]:
        """Handle assignments to detect Pi Creature variables."""
        # Check if assigning a Pi Creature
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            if any(pattern in node.value.func.id for pattern in ['PiCreature', 'Randolph', 'Mortimer', 'get_students']):
                # Track variable names
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.pi_creature_vars.add(target.id)
                
                # Comment out the line
                return None  # This will be handled in post-processing
        
        return self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        """Handle class definitions, especially CONFIG dictionaries."""
        new_body = []
        config_dict = None
        
        # Look for CONFIG dictionary
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == 'CONFIG':
                        config_dict = item.value
                        continue
            new_body.append(item)
        
        # Convert CONFIG dict to class attributes
        if config_dict and isinstance(config_dict, ast.Dict):
            self.conversion_log.append(f"Converting CONFIG dict in class {node.name}")
            
            for key, value in zip(config_dict.keys, config_dict.values):
                if isinstance(key, ast.Str):
                    # Create class attribute
                    attr_assign = ast.Assign(
                        targets=[ast.Name(id=key.s, ctx=ast.Store())],
                        value=value
                    )
                    new_body.insert(0, attr_assign)
        
        node.body = new_body
        
        # Handle ContinualAnimation base class
        new_bases = []
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == 'ContinualAnimation':
                self.issues.append({
                    'type': 'continual_animation',
                    'class': node.name,
                    'description': f"Class '{node.name}' inherits from ContinualAnimation"
                })
                # Don't include ContinualAnimation as base
                continue
            new_bases.append(base)
        
        node.bases = new_bases
        
        return self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        """Handle attribute access for constants and properties."""
        # Convert frame constants
        if isinstance(node.value, ast.Name):
            if node.value.id == 'FRAME_WIDTH':
                return ast.Attribute(
                    value=ast.Name(id='config', ctx=ast.Load()),
                    attr='frame_width',
                    ctx=node.ctx
                )
            elif node.value.id == 'FRAME_HEIGHT':
                return ast.Attribute(
                    value=ast.Name(id='config', ctx=ast.Load()),
                    attr='frame_height',
                    ctx=node.ctx
                )
        
        return self.generic_visit(node)


def convert_with_ast(content: str) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    """
    Convert ManimGL code to ManimCE using AST transformations.
    
    Returns:
        Tuple of (converted_code, conversion_log, issues)
    """
    try:
        # Parse the code into AST
        tree = ast.parse(content)
        
        # Apply transformations
        transformer = ManimASTTransformer()
        new_tree = transformer.visit(tree)
        
        # Fix missing locations in AST
        ast.fix_missing_locations(new_tree)
        
        # Convert back to code
        converted_code = astor.to_source(new_tree)
        
        # Post-process for special cases
        converted_code = post_process_converted_code(converted_code, transformer)
        
        return converted_code, transformer.conversion_log, transformer.issues
        
    except SyntaxError as e:
        return content, [f"Syntax error during AST parsing: {e}"], [{'type': 'syntax_error', 'error': str(e)}]
    except Exception as e:
        return content, [f"Error during AST conversion: {e}"], [{'type': 'conversion_error', 'error': str(e)}]


def post_process_converted_code(code: str, transformer: ManimASTTransformer) -> str:
    """Apply post-processing to handle special cases."""
    lines = code.split('\n')
    new_lines = []
    
    # Ensure from manim import * is present
    has_manim_import = False
    import_insert_line = 0
    
    for i, line in enumerate(lines):
        # Check for manim import
        if 'from manim import *' in line:
            has_manim_import = True
        
        # Find where to insert import if needed
        if line.strip() and not line.strip().startswith('#') and import_insert_line == 0:
            if not line.startswith(('import', 'from')):
                import_insert_line = i
        
        # Comment out lines with Pi Creatures
        if any(var in line for var in transformer.pi_creature_vars):
            indent = len(line) - len(line.lstrip())
            new_lines.append(' ' * indent + '# REMOVED: ' + line.strip() + ' # Pi Creature not available in ManimCE')
        else:
            new_lines.append(line)
    
    # Add manim import if missing
    if not has_manim_import:
        new_lines.insert(import_insert_line, 'from manim import *')
        import_insert_line += 1
    
    # Add any required custom imports
    if transformer.imports_to_add:
        # Find the line after main manim import
        insert_pos = import_insert_line
        for imp in sorted(transformer.imports_to_add):
            new_lines.insert(insert_pos, imp)
            insert_pos += 1
        new_lines.insert(insert_pos, '')
    
    return '\n'.join(new_lines)


def analyze_manimgl_usage(content: str) -> Dict[str, Any]:
    """
    Analyze ManimGL code to identify features used and potential issues.
    
    Returns:
        Dictionary with analysis results
    """
    analysis = {
        'imports': {
            'manimlib_imports': [],
            'custom_imports': [],
            'standard_imports': []
        },
        'classes_used': {
            'scenes': [],
            'animations': [],
            'mobjects': [],
            'custom_classes': []
        },
        'features': {
            'uses_config_dict': False,
            'uses_pi_creatures': False,
            'uses_continual_animation': False,
            'uses_3d_scenes': False,
            'uses_tex': False,
            'uses_graphs': False,
            'uses_number_line': False
        },
        'potential_issues': []
    }
    
    try:
        tree = ast.parse(content)
        
        # Analyze imports
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    if 'manimlib' in node.module:
                        analysis['imports']['manimlib_imports'].append(node.module)
                    elif any(node.module.startswith(prefix) for prefix in ['custom.', 'once_useful_constructs.']):
                        analysis['imports']['custom_imports'].append(node.module)
                    else:
                        analysis['imports']['standard_imports'].append(node.module)
        
        # Analyze classes and features
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check base classes
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        if 'Scene' in base.id:
                            analysis['classes_used']['scenes'].append(node.name)
                            if 'ThreeDScene' in base.id:
                                analysis['features']['uses_3d_scenes'] = True
                            if 'GraphScene' in base.id:
                                analysis['features']['uses_graphs'] = True
                        elif 'ContinualAnimation' in base.id:
                            analysis['features']['uses_continual_animation'] = True
                
                # Check for CONFIG dict
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == 'CONFIG':
                                analysis['features']['uses_config_dict'] = True
            
            # Check for specific class usage
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                class_name = node.func.id
                
                # Animations
                if any(anim in class_name for anim in ['Animation', 'Transform', 'Create', 'Write', 'FadeIn', 'FadeOut']):
                    analysis['classes_used']['animations'].append(class_name)
                
                # Mobjects
                elif any(obj in class_name for obj in ['Mobject', 'Text', 'Tex', 'Circle', 'Square', 'Line']):
                    analysis['classes_used']['mobjects'].append(class_name)
                    if 'Tex' in class_name:
                        analysis['features']['uses_tex'] = True
                
                # Pi Creatures
                elif any(pi in class_name for pi in ['PiCreature', 'Randolph', 'Mortimer']):
                    analysis['features']['uses_pi_creatures'] = True
                
                # Number line
                elif 'NumberLine' in class_name:
                    analysis['features']['uses_number_line'] = True
        
        # Identify potential issues
        if analysis['features']['uses_continual_animation']:
            analysis['potential_issues'].append("Uses ContinualAnimation - needs conversion to updaters")
        
        if analysis['features']['uses_pi_creatures']:
            analysis['potential_issues'].append("Uses Pi Creatures - will be commented out")
        
        if analysis['imports']['custom_imports']:
            analysis['potential_issues'].append("Has custom imports that may need manual resolution")
        
        if analysis['features']['uses_3d_scenes']:
            analysis['potential_issues'].append("Uses 3D scenes - may need renderer configuration")
        
    except Exception as e:
        analysis['potential_issues'].append(f"Analysis error: {str(e)}")
    
    return analysis