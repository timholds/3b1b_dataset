#!/usr/bin/env python3
"""
Utility functions for ManimGL to ManimCE conversion.

This module contains helper functions for common conversion tasks
and patterns that appear frequently in the conversion process.
"""

import re
from typing import Dict, List, Tuple, Optional
from scripts.manimce_api_mappings import (
    CLASS_MAPPINGS, METHOD_TO_PROPERTY_MAPPINGS, 
    is_pi_creature_related, get_class_conversion
)


def convert_continual_animation_to_updater(content: str) -> str:
    """
    Convert ContinualAnimation usage to ManimCE updater pattern.
    
    Note: This is a basic conversion that may require manual review.
    """
    # Pattern to find ContinualAnimation classes
    pattern = r'class\s+(\w+)\(ContinualAnimation\):(.*?)(?=\nclass|\Z)'
    
    def replace_continual_animation(match):
        class_name = match.group(1)
        class_body = match.group(2)
        
        # Extract the update_mobject method
        update_pattern = r'def\s+update_mobject\(self,\s*dt\):(.*?)(?=\n    def|\n\S|\Z)'
        update_match = re.search(update_pattern, class_body, re.DOTALL)
        
        if update_match:
            update_body = update_match.group(1)
            
            # Create a function-based updater
            updater_func = f"""
def {class_name.lower()}_updater(mobject, dt):
{update_body}

# Usage: mobject.add_updater({class_name.lower()}_updater)
"""
            return updater_func
        
        return match.group(0)  # Return original if can't convert
    
    converted = re.sub(pattern, replace_continual_animation, content, flags=re.DOTALL)
    
    # Add comment about manual review needed
    if 'ContinualAnimation' in content and converted != content:
        header = """# NOTE: ContinualAnimation has been converted to updater pattern.
# Please review and adjust the implementation as needed.
# In ManimCE, use mobject.add_updater(function) instead.

"""
        converted = header + converted
    
    return converted


def convert_old_color_names(content: str) -> str:
    """Convert old color names to ManimCE color names."""
    color_mappings = {
        r'\bCOLOR_MAP\b': 'MANIM_COLORS',
        r'\bLIGHT_GRAY\b': 'LIGHT_GREY',
        r'\bDARK_GRAY\b': 'DARK_GREY',
        r'\bGRAY\b': 'GREY',
        r'\bCOLOR_MAP\["([^"]+)"\]': r'MANIM_COLORS["\1"]',
    }
    
    converted = content
    for pattern, replacement in color_mappings.items():
        converted = re.sub(pattern, replacement, converted)
    
    return converted


def convert_old_methods(content: str) -> str:
    """Convert deprecated get_/set_ methods to property access."""
    # Common method conversions
    method_mappings = {
        # Get methods
        r'\.get_center\(\)': '.get_center()',  # This one stays the same
        r'\.get_x\(\)': '.get_x()',
        r'\.get_y\(\)': '.get_y()',
        r'\.get_z\(\)': '.get_z()',
        r'\.get_width\(\)': '.width',
        r'\.get_height\(\)': '.height',
        r'\.get_color\(\)': '.color',
        r'\.get_fill_color\(\)': '.fill_color',
        r'\.get_stroke_color\(\)': '.stroke_color',
        r'\.get_fill_opacity\(\)': '.fill_opacity',
        r'\.get_stroke_opacity\(\)': '.stroke_opacity',
        r'\.get_stroke_width\(\)': '.stroke_width',
        
        # Set methods (these need special handling)
        r'\.set_width\(([^)]+)\)': r'.width = \1',
        r'\.set_height\(([^)]+)\)': r'.height = \1',
        r'\.set_color\(([^)]+)\)': r'.set_color(\1)',  # This one stays
        r'\.set_fill_color\(([^)]+)\)': r'.set_fill(\1)',
        r'\.set_stroke_color\(([^)]+)\)': r'.set_stroke(\1)',
        r'\.set_fill_opacity\(([^)]+)\)': r'.set_fill(opacity=\1)',
        r'\.set_stroke_opacity\(([^)]+)\)': r'.set_stroke(opacity=\1)',
        r'\.set_stroke_width\(([^)]+)\)': r'.set_stroke(width=\1)',
        
        # Corner and edge conversions
        r'\.to_corner\(DOWN\s*\+\s*LEFT\)': '.to_corner(DL)',
        r'\.to_corner\(DOWN\s*\+\s*RIGHT\)': '.to_corner(DR)',
        r'\.to_corner\(UP\s*\+\s*LEFT\)': '.to_corner(UL)',
        r'\.to_corner\(UP\s*\+\s*RIGHT\)': '.to_corner(UR)',
        r'\.to_corner\(LEFT\s*\+\s*DOWN\)': '.to_corner(DL)',
        r'\.to_corner\(RIGHT\s*\+\s*DOWN\)': '.to_corner(DR)',
        r'\.to_corner\(LEFT\s*\+\s*UP\)': '.to_corner(UL)',
        r'\.to_corner\(RIGHT\s*\+\s*UP\)': '.to_corner(UR)',
        
        # Additional method conversions
        r'\.get_corner\(': '.get_critical_point(',
        r'\.scale_to_fit_width\(': '.scale_to_fit(',
        r'\.scale_to_fit_height\(': '.scale_to_fit(',
    }
    
    converted = content
    for pattern, replacement in method_mappings.items():
        converted = re.sub(pattern, replacement, converted)
    
    return converted


def convert_transform_animations(content: str) -> str:
    """Convert old transform animations to new syntax."""
    # Transform animation updates
    transform_mappings = {
        r'\bApplyMethod\b': 'ApplyMethod',  # Stays the same but note it
        r'\bApplyPointwiseFunction\b': 'ApplyPointwiseFunction',
        r'\bApplyMatrix\b': 'ApplyMatrix',
        r'\bWiggleOutThenIn\b': 'Wiggle',  # Changed in ManimCE
        r'\bFlash\b': 'Flash',
    }
    
    converted = content
    for pattern, replacement in transform_mappings.items():
        if pattern != replacement:
            converted = re.sub(pattern, replacement, converted)
    
    return converted


def convert_3d_scene_methods(content: str) -> str:
    """Convert 3D scene specific methods."""
    # 3D scene method updates
    scene_mappings = {
        r'\.set_camera_orientation\(': '.set_camera_orientation(',  # Stays same
        r'\.move_camera\(': '.move_camera(',
        r'\.get_camera\(\)': '.camera',
        r'\.get_frame\(\)': '.camera.frame',
    }
    
    converted = content
    for pattern, replacement in scene_mappings.items():
        converted = re.sub(pattern, replacement, converted)
    
    return converted


def add_config_dict_conversion(content: str) -> str:
    """
    Convert CONFIG dictionary to class attributes.
    
    ManimGL uses CONFIG dict, ManimCE uses class attributes.
    """
    # Pattern to find CONFIG dictionaries
    config_pattern = r'class\s+(\w+)\([^)]+\):\s*\n\s*CONFIG\s*=\s*{([^}]+)}'
    
    def convert_config(match):
        class_name = match.group(1)
        config_content = match.group(2)
        
        # Parse config items
        items = re.findall(r'"(\w+)"\s*:\s*([^,\n]+)', config_content)
        
        # Build class with attributes
        result = f"class {class_name}("
        if 'Scene' in match.group(0):
            result += "Scene"
        else:
            # Extract parent class from original
            parent_match = re.search(rf'class\s+{class_name}\(([^)]+)\)', match.group(0))
            if parent_match:
                result += parent_match.group(1)
        
        result += "):\n"
        
        # Add attributes
        for key, value in items:
            result += f"    {key} = {value.strip()}\n"
        
        return result
    
    converted = re.sub(config_pattern, convert_config, content, flags=re.MULTILINE)
    
    return converted


def suggest_pi_creature_replacement(content: str) -> str:
    """
    Add comments suggesting replacements for pi_creature usage.
    """
    if 'PiCreature' not in content and 'pi_creature' not in content:
        return content
    
    # Add helper code at the top
    helper_code = '''
# Pi Creature Replacement Options
# ================================
# Option 1: Simple Stick Figure
def create_stick_figure(color=WHITE, height=2):
    """Create a simple stick figure character."""
    from manim import VGroup, Circle, Line, WHITE, DOWN, LEFT, RIGHT, UP
    
    head = Circle(radius=height/4, color=color)
    body = Line(head.get_bottom(), head.get_bottom() + height/2 * DOWN, color=color)
    
    left_arm = Line(
        body.point_from_proportion(0.3),
        body.point_from_proportion(0.3) + height/4 * (LEFT + 0.5*DOWN),
        color=color
    )
    right_arm = Line(
        body.point_from_proportion(0.3),
        body.point_from_proportion(0.3) + height/4 * (RIGHT + 0.5*DOWN),
        color=color
    )
    
    left_leg = Line(
        body.get_bottom(),
        body.get_bottom() + height/4 * (LEFT + DOWN),
        color=color
    )
    right_leg = Line(
        body.get_bottom(),
        body.get_bottom() + height/4 * (RIGHT + DOWN),
        color=color
    )
    
    return VGroup(head, body, left_arm, right_arm, left_leg, right_leg)

# Option 2: Simple Face Character
def create_simple_face(color=YELLOW, radius=1):
    """Create a simple smiley face character."""
    from manim import VGroup, Circle, Dot, Arc, PI, BLACK, YELLOW
    
    face = Circle(radius=radius, color=color, fill_opacity=0.5)
    
    left_eye = Dot(
        point=face.get_center() + radius * 0.3 * (LEFT + 0.3*UP),
        radius=radius * 0.05,
        color=BLACK
    )
    right_eye = Dot(
        point=face.get_center() + radius * 0.3 * (RIGHT + 0.3*UP),
        radius=radius * 0.05,
        color=BLACK
    )
    
    smile = Arc(
        start_angle=-2*PI/3,
        angle=PI/3,
        radius=radius * 0.5,
        color=BLACK,
        stroke_width=3
    ).move_to(face.get_center() + radius * 0.2 * DOWN)
    
    return VGroup(face, left_eye, right_eye, smile)

# Replace PiCreature usage with:
# character = create_stick_figure()  # or create_simple_face()

'''
    
    # Add the helper code after imports
    import_end = 0
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith(('import', 'from', '#')):
            import_end = i
            break
    
    lines.insert(import_end, helper_code)
    
    # Add comments near PiCreature usage
    content_with_helpers = '\n'.join(lines)
    
    # Add inline comments
    content_with_helpers = re.sub(
        r'(\s*)(.*PiCreature.*)',
        r'\1# TODO: Replace PiCreature with create_stick_figure() or create_simple_face()\n\1\2',
        content_with_helpers
    )
    
    return content_with_helpers


def remove_pi_creature_dependencies(content: str) -> str:
    """
    Remove all Pi Creature dependencies using comprehensive centralized lists.
    Comments out Pi Creature classes, animations, methods, and helper functions.
    """
    # Centralized lists for maintainability
    PI_CREATURE_CLASSES = [
        'PiCreature', 'Randolph', 'Mortimer', 'ThoughtBubble', 'SpeechBubble',
        'WaveArm', 'BlinkPiCreature', 'PiCreatureBubbleIntroduction'
    ]
    
    PI_CREATURE_ANIMATIONS = [
        'WaveArm', 'BlinkPiCreature', 'RemovePiCreatureBubble', 'PiCreatureBubbleIntroduction',
        'Blink'  # When used with Pi Creatures
    ]
    
    PI_CREATURE_HELPER_FUNCTIONS = [
        'draw_you', 'create_pi_creature', 'make_pi_creature', 'get_pi_creature', 
        'setup_pi_creature', 'get_bubble_introduction'
    ]
    
    TEACHER_STUDENTS_METHODS = [
        'student_says', 'teacher_says', 'student_thinks', 'teacher_thinks',
        'play_student_changes', 'change_students', 'get_student_changes',
        'random_blink_wait'
    ]
    
    PI_CREATURE_INSTANCE_METHODS = [
        'change', 'look_at', 'blink', 'wave', 'says', 'thinks', 'get_bubble',
        'shift_onto_screen', 'change_mode', 'bubble_thought', 'bubble_speak'
    ]
    
    lines = content.split('\n')
    result_lines = []
    
    for line in lines:
        # Check if line contains Pi Creature patterns
        line_modified = False
        
        # 1. Check for Pi Creature class instantiations and animations
        for class_name in PI_CREATURE_CLASSES:
            if class_name in line and ('=' in line or 'self.play(' in line or 'self.add(' in line):
                # Comment out Pi Creature instantiation or usage
                indentation = len(line) - len(line.lstrip())
                result_lines.append(' ' * indentation + f'# {line.strip()}  # Pi Creature - no ManimCE equivalent')
                line_modified = True
                break
        
        if line_modified:
            continue
            
        # 2. Check for Pi Creature animations in play/add calls
        for animation in PI_CREATURE_ANIMATIONS:
            if animation in line and ('self.play(' in line or 'self.add(' in line):
                # Comment out Pi Creature animation
                indentation = len(line) - len(line.lstrip())
                result_lines.append(' ' * indentation + f'# {line.strip()}  # Pi Creature animation - no ManimCE equivalent')
                line_modified = True
                break
        
        if line_modified:
            continue
            
        # 3. Check for Pi Creature helper functions
        helper_pattern = r'\s*def\s+(' + '|'.join(PI_CREATURE_HELPER_FUNCTIONS) + r')\s*\('
        if re.match(helper_pattern, line):
            # Comment out Pi Creature helper function definition
            indentation = len(line) - len(line.lstrip())
            result_lines.append(' ' * indentation + f'# {line.strip()}  # Pi Creature helper function - no ManimCE equivalent')
            line_modified = True
        
        if line_modified:
            continue
            
        # 4. Check for TeacherStudentsScene method calls
        for method in TEACHER_STUDENTS_METHODS:
            if f'self.{method}(' in line:
                # Comment out TeacherStudentsScene method call
                indentation = len(line) - len(line.lstrip())
                result_lines.append(' ' * indentation + f'# {line.strip()}  # TeacherStudentsScene method - no ManimCE equivalent')
                line_modified = True
                break
        
        if line_modified:
            continue
            
        # 5. Check for Pi Creature instance method calls
        instance_method_pattern = r'\.\s*(' + '|'.join(PI_CREATURE_INSTANCE_METHODS) + r')\s*\('
        if re.search(instance_method_pattern, line):
            # Comment out Pi Creature instance method call
            indentation = len(line) - len(line.lstrip())
            result_lines.append(' ' * indentation + f'# {line.strip()}  # Pi Creature method - no ManimCE equivalent')
            line_modified = True
        
        if not line_modified:
            result_lines.append(line)
    
    return '\n'.join(result_lines)


def convert_frame_constants(content: str) -> str:
    """Convert frame-related constants to config attributes."""
    constant_replacements = {
        r'\bFRAME_X_RADIUS\b': 'config.frame_width / 2',
        r'\bFRAME_Y_RADIUS\b': 'config.frame_height / 2',
        r'\bFRAME_WIDTH\b': 'config.frame_width',
        r'\bFRAME_HEIGHT\b': 'config.frame_height',
        r'\bVIDEO_DIR\b': '"./"',
        r'\bPIXEL_WIDTH\b': 'config.pixel_width',
        r'\bPIXEL_HEIGHT\b': 'config.pixel_height',
    }
    
    converted = content
    for pattern, replacement in constant_replacements.items():
        converted = re.sub(pattern, replacement, converted)
    
    return converted


def add_undefined_class_stubs(content: str) -> str:
    """Add stub definitions for commonly undefined classes."""
    undefined_classes = {
        'Mobject1D': 'class Mobject1D(VMobject):\n    pass\n',
        'Mobject2D': 'class Mobject2D(VMobject):\n    pass\n',
        'RearrangeEquation': '''from manim import TexTemplate  # Required for size formatting

class RearrangeEquation(Scene):
    """Enhanced RearrangeEquation compatibility implementation."""
    @staticmethod
    def construct(scene, start_terms, end_terms, index_map, 
                  size="\\\\large", path=None, start_transform=None,
                  end_transform=None, leave_start_terms=False,
                  transform_kwargs=None):
        """Enhanced implementation for equation rearrangement with term mapping."""
        if transform_kwargs is None:
            transform_kwargs = {}
        
        # Create the starting equation with size
        if size:
            start_eq = MathTex(*start_terms, tex_template=TexTemplate().add_to_preamble(f"\\\\{size}"))
        else:
            start_eq = MathTex(*start_terms)
            
        if start_transform:
            start_eq = start_transform(start_eq)
        
        # Create the ending equation with size
        if size:
            end_eq = MathTex(*end_terms, tex_template=TexTemplate().add_to_preamble(f"\\\\{size}"))
        else:
            end_eq = MathTex(*end_terms)
            
        if end_transform:
            end_eq = end_transform(end_eq)
        
        # Show the starting equation
        scene.play(Write(start_eq))
        scene.wait()
        
        # Handle the rearrangement with index mapping
        if index_map:
            # Create a list to hold the transforms
            transforms = []
            
            # For each mapping, create a transform from start to end position
            for start_idx, end_idx in index_map.items():
                if start_idx < len(start_eq) and end_idx < len(end_eq):
                    # Use TransformMatchingTex for better alignment
                    transforms.append(
                        TransformMatchingTex(
                            start_eq[start_idx].copy(),
                            end_eq[end_idx],
                            path_arc=path if path else 0,
                            **transform_kwargs
                        )
                    )
            
            # Also fade out terms that aren't mapped
            fade_out_terms = []
            for i, term in enumerate(start_eq):
                if i not in index_map:
                    fade_out_terms.append(FadeOut(term))
            
            # Fade in new terms that weren't in the original
            fade_in_terms = []
            mapped_end_indices = set(index_map.values())
            for i, term in enumerate(end_eq):
                if i not in mapped_end_indices:
                    fade_in_terms.append(FadeIn(term))
            
            # Play all animations together
            all_anims = transforms + fade_out_terms + fade_in_terms
            if all_anims:
                scene.play(*all_anims, **transform_kwargs)
            else:
                # Fallback to simple transform
                scene.play(Transform(start_eq, end_eq, **transform_kwargs))
        else:
            # No index map provided, use simple transform
            scene.play(Transform(start_eq, end_eq, path_arc=path if path else 0, **transform_kwargs))
        
        scene.wait()
        
        if not leave_start_terms:
            scene.clear()
        else:
            # Keep the end equation visible
            scene.add(end_eq)
''',
        'GraphScene': '''import numpy as np  # Required for GraphScene

class GraphScene(Scene):
    """Enhanced GraphScene compatibility implementation."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Default graph parameters
        self.x_min = kwargs.get('x_min', -1)
        self.x_max = kwargs.get('x_max', 10)
        self.y_min = kwargs.get('y_min', -1)
        self.y_max = kwargs.get('y_max', 10)
        self.x_axis_step = kwargs.get('x_axis_step', 1)
        self.y_axis_step = kwargs.get('y_axis_step', 1)
        self.x_axis_label = kwargs.get('x_axis_label', None)
        self.y_axis_label = kwargs.get('y_axis_label', None)
        self.include_tip = kwargs.get('include_tip', True)
        self.axis_config = kwargs.get('axis_config', {})
        self.graph_origin = kwargs.get('graph_origin', ORIGIN)
        self.axes_color = kwargs.get('axes_color', WHITE)
        self.axes = None
        
    def setup_axes(self, animate=False):
        """Create and add axes to the scene."""
        self.axes = Axes(
            x_range=[self.x_min, self.x_max, self.x_axis_step],
            y_range=[self.y_min, self.y_max, self.y_axis_step],
            axis_config={
                "color": self.axes_color,
                **self.axis_config
            },
        ).shift(self.graph_origin)
        
        # Add labels if specified
        if self.x_axis_label:
            x_label = Text(self.x_axis_label).next_to(self.axes.x_axis, DOWN)
            self.axes.add(x_label)
        if self.y_axis_label:
            y_label = Text(self.y_axis_label).next_to(self.axes.y_axis, LEFT)
            self.axes.add(y_label)
            
        if self.include_tip:
            self.axes.add_tips()
            
        if animate:
            self.play(Create(self.axes))
        else:
            self.add(self.axes)
        return self.axes
    
    def coords_to_point(self, x, y):
        """Convert graph coordinates to point."""
        if self.axes:
            return self.axes.c2p(x, y)
        return np.array([x, y, 0]) + self.graph_origin
        
    def point_to_coords(self, point):
        """Convert point to graph coordinates."""
        if self.axes:
            return self.axes.p2c(point)
        return (point - self.graph_origin)[:2]
    
    def get_graph(self, func, x_range=None, **kwargs):
        """Create a graph of the given function."""
        if not self.axes:
            self.setup_axes()
        if x_range is None:
            x_range = [self.x_min, self.x_max]
        return self.axes.plot(func, x_range=x_range, **kwargs)
    
    def get_derivative_graph(self, graph, **kwargs):
        """Create a derivative graph from an existing graph."""
        # Simple numerical derivative
        def derivative_func(x):
            dx = 0.001
            return (graph.underlying_function(x + dx) - graph.underlying_function(x - dx)) / (2 * dx)
        return self.get_graph(derivative_func, **kwargs)
    
    def get_graph_label(self, graph, label, x_val=None, direction=UP, **kwargs):
        """Add a label to a graph."""
        if x_val is None:
            x_val = (self.x_min + self.x_max) / 2
        label_mob = MathTex(label, **kwargs) if isinstance(label, str) else label
        point = self.axes.input_to_graph_point(x_val, graph)
        label_mob.next_to(point, direction)
        return label_mob
    
    def get_axis_labels(self, x_label=None, y_label=None):
        """Get axis labels."""
        labels = VGroup()
        if x_label:
            x_label_mob = MathTex(x_label) if isinstance(x_label, str) else x_label
            x_label_mob.next_to(self.axes.x_axis, DOWN)
            labels.add(x_label_mob)
        if y_label:
            y_label_mob = MathTex(y_label) if isinstance(y_label, str) else y_label
            y_label_mob.next_to(self.axes.y_axis, LEFT)
            labels.add(y_label_mob)
        return labels
''',
        'NumberLineScene': '''class NumberLineScene(Scene):
    """Basic NumberLineScene compatibility stub."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.number_line = None
        
    def setup(self):
        """Create and add number line."""
        self.number_line = NumberLine()
        self.add(self.number_line)
''',
    }
    
    # Check which classes are used but not defined
    needed_classes = []
    for class_name in undefined_classes:
        if re.search(r'\b' + class_name + r'\b', content) and f'class {class_name}' not in content:
            needed_classes.append(class_name)
    
    if needed_classes:
        # Add definitions after imports
        lines = content.split('\n')
        insert_pos = 0
        
        for i, line in enumerate(lines):
            if 'from manim import *' in line:
                insert_pos = i + 1
                # Skip any existing compatibility code
                while insert_pos < len(lines) and (lines[insert_pos].strip() == '' or 
                                                   lines[insert_pos].strip().startswith('#')):
                    insert_pos += 1
                break
        
        # Add undefined class definitions
        compatibility_code = '\n# Compatibility stubs for undefined classes\n'
        for class_name in needed_classes:
            compatibility_code += undefined_classes[class_name] + '\n'
        
        lines.insert(insert_pos, compatibility_code)
        content = '\n'.join(lines)
    
    return content


def fix_string_continuations(content: str) -> str:
    """Fix backslash continuations in string literals."""
    # Pattern to find strings with backslash continuation
    # This matches strings that have a backslash followed by a newline
    pattern = r'(["\'])([^"\']*?)\\(\s*\n\s*)([^"\']*?)\1'
    
    def replace_continuation(match):
        quote = match.group(1)
        part1 = match.group(2)
        part2 = match.group(4)
        # Convert to implicit string concatenation
        return f'{quote}{part1}{quote} {quote}{part2}{quote}'
    
    # Apply the fix
    fixed = re.sub(pattern, replace_continuation, content, flags=re.MULTILINE | re.DOTALL)
    
    # Also handle triple-quoted strings with continuations
    triple_pattern = r'("""|\'\'\')([^"\']*?)\\(\s*\n\s*)([^"\']*?)\1'
    fixed = re.sub(triple_pattern, replace_continuation, fixed, flags=re.MULTILINE | re.DOTALL)
    
    return fixed


def convert_manimgl_imports(content: str) -> str:
    """Convert ManimGL imports to ManimCE imports."""
    # Special case: manimlib.imports doesn't exist in ManimCE
    # Convert specific imports from manimlib.imports to wildcard import
    content = re.sub(r'from manimlib\.imports import .*', 'from manim import *', content)
    
    # Replace manimlib imports with manim
    content = re.sub(r'from manimlib import \*', 'from manim import *', content)
    
    # Only convert top-level module imports that have direct equivalents
    # Don't convert deep imports like manimlib.scene.scene as they don't exist in ManimCE
    valid_module_conversions = [
        (r'from manimlib\.animation import', 'from manim.animation import'),
        (r'from manimlib\.mobject import', 'from manim.mobject import'),
        (r'from manimlib\.scene import', 'from manim.scene import'),
        (r'from manimlib\.utils import', 'from manim.utils import'),
        (r'from manimlib\.camera import', 'from manim.camera import'),
        (r'from manimlib\.constants import', 'from manim.constants import'),
    ]
    
    for old_pattern, new_pattern in valid_module_conversions:
        content = re.sub(old_pattern, new_pattern, content)
    
    # For any remaining deep manimlib imports, convert to general manim import
    # e.g., from manimlib.scene.scene import Scene -> from manim import *
    content = re.sub(r'from manimlib\.[.\w]+ import .*', 'from manim import *', content)
    
    # General import statement
    content = re.sub(r'import manimlib', 'import manim', content)
    
    # Replace manim_imports_ext
    content = re.sub(r'from manim_imports_ext import \*', 'from manim import *', content)
    
    # Remove custom imports that don't exist in ManimCE
    custom_imports = [
        r'from custom\..*',
        r'from once_useful_constructs.*',
        r'from script_wrapper import.*',
        r'from stage_scenes import.*',
    ]
    
    for pattern in custom_imports:
        content = re.sub(pattern + r'\n?', '', content)
    
    return content


def fix_common_import_errors(content: str):
    """Fix common import errors based on error patterns."""
    # Import the list of imports to remove
    try:
        from scripts.api_mappings import IMPORTS_TO_REMOVE
    except ImportError:
        # Fallback list if import fails
        IMPORTS_TO_REMOVE = [
            'import displayer as disp',
            'from displayer import *',
            'import constants',
            'from constants import *',
            'import helpers',
            'from helpers import *',
        ]
    
    # First, remove/comment out problematic imports
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        # Check if this is a problematic import
        if any(imp in stripped_line for imp in IMPORTS_TO_REMOVE):
            # Comment out instead of removing to preserve line numbers
            cleaned_lines.append(f"# {line}  # Removed ManimGL-specific import")
        else:
            cleaned_lines.append(line)
    
    content = '\n'.join(cleaned_lines)
    
    # Add missing essential imports if not present
    if 'from manim import' not in content and 'import manim' not in content:
        # Find first import or start of file
        lines = content.split('\n')
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip() and (line.startswith('import') or line.startswith('from')):
                insert_pos = i
                break
        
        # Add comprehensive imports
        lines.insert(insert_pos, 'from manim import *')
        content = '\n'.join(lines)
    
    # Fix specific missing imports based on usage
    import_fixes = {
        r'\bShowCreation\b': 'from manim import Create',
        r'\bTextMobject\b': 'from manim import Text',
        r'\bTexMobject\b': 'from manim import MathTex',
        r'\bDrawBorderThenFill\b': 'from manim import DrawBorderThenFill',
        r'\bFadeInFromDown\b': 'from manim import FadeIn',
        r'\bFadeOutAndShiftDown\b': 'from manim import FadeOut',
    }
    
    # Check if specific imports are needed
    for pattern, import_stmt in import_fixes.items():
        if re.search(pattern, content) and import_stmt not in content:
            # Add after main manim import
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'from manim import *' in line:
                    lines.insert(i + 1, import_stmt)
                    content = '\n'.join(lines)
                    break
    
    return content


def fix_method_signature_mismatches(content: str) -> str:
    """Fix method signature mismatches based on common patterns."""
    # Fix scale_to_fit_width/height with wrong arguments
    content = re.sub(
        r'\.scale_to_fit_width\(([^,)]+),\s*maintain_aspect_ratio\s*=\s*False\)',
        r'.scale_to_fit_width(\1)',
        content
    )
    content = re.sub(
        r'\.scale_to_fit_height\(([^,)]+),\s*maintain_aspect_ratio\s*=\s*False\)',
        r'.scale_to_fit_height(\1)',
        content
    )
    
    # Fix animate syntax changes
    content = re.sub(
        r'\.animate\.set_color\(([^)]+)\)',
        r'.animate.become(self.copy().set_color(\1))',
        content
    )
    
    return content


def add_missing_base_methods(content: str) -> str:
    """Add missing base methods that ManimCE expects."""
    # Check if we have custom Scene classes
    scene_classes = re.findall(r'class\s+(\w+)\(.*Scene.*?\):', content)
    
    for scene_class in scene_classes:
        # More robust check for existing construct method within the class
        # Find the class definition and check if it already has a construct method
        class_match = re.search(rf'class\s+{scene_class}\(.*?\):(.*?)(?=\nclass|\Z)', content, re.DOTALL)
        if class_match:
            class_body = class_match.group(1)
            # Check if construct method exists within this specific class body
            if not re.search(r'def\s+construct\s*\(', class_body):
                # Find the class and add construct method
                class_pattern = rf'(class\s+{scene_class}\(.*?\):)'
                replacement = r'\1\n    def construct(self):\n        pass  # TODO: Implement scene construction\n'
                content = re.sub(class_pattern, replacement, content, count=1)  # Only replace first occurrence
    
    return content


def fix_color_constant_errors(content: str) -> str:
    """Fix color constant errors more comprehensively."""
    # Extended color mappings
    extended_color_mappings = {
        r'\bCOLOR_MAP\["([^"]+)"\]': lambda m: f'MANIM_COLORS["{m.group(1)}"]',
        r'\bLIGHT_GRAY\b': 'LIGHT_GREY',
        r'\bDARK_GRAY\b': 'DARK_GREY',
        r'\bGRAY\b': 'GREY',
        r'\bGRAY_A\b': 'GREY_A',
        r'\bGRAY_B\b': 'GREY_B',
        r'\bGRAY_C\b': 'GREY_C',
        r'\bGRAY_D\b': 'GREY_D',
        r'\bGRAY_E\b': 'GREY_E',
    }
    
    for pattern, replacement in extended_color_mappings.items():
        if callable(replacement):
            content = re.sub(pattern, replacement, content)
        else:
            content = re.sub(pattern, replacement, content)
    
    return content


def fix_tex_parenthesis_bug(content: str) -> str:
    """Fix the specific bug where OldTex("(") becomes Tex("("))"""
    # More precise patterns that won't match already-correct code
    patterns = [
        # Fix OldTex("X")) -> Tex("X") where X is any single character
        (r'\b(?:Old)?Tex\("(.)"\)\)', r'Tex("\1")'),
        # Fix OldTexText("X")) -> Text("X") 
        (r'\b(?:Old)?TexText\("(.)"\)\)', r'Text("\1")'),
        # Fix double closing parentheses in Tex/MathTex calls with single char
        (r'\b(Tex|MathTex)\("(.)"\)\)', r'\1("\2")'),
    ]
    
    fixed = content
    changes_made = 0
    for pattern, replacement in patterns:
        matches = list(re.finditer(pattern, fixed))
        if matches:
            fixed = re.sub(pattern, replacement, fixed)
            changes_made += len(matches)
    
    # Log if we made any fixes
    if changes_made > 0:
        import logging
        logging.getLogger(__name__).info(f"Fixed {changes_made} Tex parenthesis bugs")
    
    return fixed


def contains_math_content(text: str) -> bool:
    """Detect if a string contains mathematical content that requires MathTex."""
    # Math patterns that indicate mathematical content
    math_patterns = [
        r'\\frac', r'\\cdot', r'\\sqrt', r'\\sum', r'\\int', r'\\lim',
        r'\\infty', r'\\alpha', r'\\beta', r'\\gamma', r'\\theta', r'\\phi',
        r'\\pi', r'\\sigma', r'\\omega', r'\\times', r'\\div', r'\\pm',
        r'\\leq', r'\\geq', r'\\neq', r'\\approx', r'\\equiv', r'\\propto',
        r'\\partial', r'\\nabla', r'\\forall', r'\\exists', r'\\in',
        r'\\subset', r'\\cup', r'\\cap', r'\\wedge', r'\\vee', r'\\oplus',
        r'\\otimes', r'\\perp', r'\\ldots', r'\\cdots', r'\\vdots', r'\\ddots',
        r'\^', r'_',  # Superscript and subscript
        r'\\\\', # Double backslash for line breaks in math
        r'\\zeta', r'\\Delta', r'\\Sigma', r'\\Lambda',
        r'\\left', r'\\right', r'\\big', r'\\Big',
        r'\\begin\{', r'\\end\{',  # Math environments
        r'\\mathbb', r'\\mathcal', r'\\mathfrak',
        r'\\text\{', r'\\mathrm\{',
    ]
    
    # Check for any math patterns
    for pattern in math_patterns:
        if pattern in text:
            return True
    
    # Check for dollar sign math mode
    if '$' in text:
        return True
        
    # Check for common equation patterns
    if any(op in text for op in ['=', '+', '-', '*', '/', '<', '>', '≤', '≥', '≠']):
        # But exclude simple text that happens to have these
        if not any(word in text.lower() for word in ['http', 'https', 'email', '@']):
            # Check if it looks like an equation
            if re.search(r'\b\w+\s*[=+\-*/]\s*\w+', text):
                return True
    
    return False


def convert_class_names(content: str) -> str:
    """Convert ManimGL class names to ManimCE equivalents."""
    # First handle OldTex with math detection
    def replace_oldtex(match):
        full_match = match.group(0)
        # Try to extract the string argument if present
        string_match = re.search(r'OldTex\(\s*["\']([^"\']*)["\']', full_match)
        if string_match:
            tex_content = string_match.group(1)
            if contains_math_content(tex_content):
                return full_match.replace('OldTex', 'MathTex')
        return full_match.replace('OldTex', 'Tex')
    
    # Apply OldTex conversion with content detection
    content = re.sub(r'OldTex\([^)]*\)', replace_oldtex, content)
    
    # Now handle direct Tex() calls
    def replace_tex(match):
        full_match = match.group(0)
        # Try to extract the string argument if present
        string_match = re.search(r'\bTex\(\s*["\']([^"\']*)["\']', full_match)
        if string_match:
            tex_content = string_match.group(1)
            if contains_math_content(tex_content):
                return full_match.replace('Tex(', 'MathTex(')
        return full_match
    
    # Apply Tex conversion with content detection
    content = re.sub(r'\bTex\(\s*["\'][^"\']*["\'][^)]*\)', replace_tex, content)
    
    # Other class mappings
    class_mappings = {
        r'\bTextMobject\b': 'Text',
        r'\bTexMobject\b': 'MathTex',
        r'\bTexText\b': 'Tex',
        r'\bOldTexText\b': 'Text',
        r'\bShowCreation\b': 'Create',
        r'\bUncreate\b': 'Uncreate',
        r'\bCircleIndicate\b': 'Indicate',
        r'\bShowCreationThenDestruction\b': 'ShowPassingFlash',
        r'\bShowCreationThenFadeOut\b': 'ShowPassingFlash',  # Approximation
    }
    
    for pattern, replacement in class_mappings.items():
        content = re.sub(pattern, replacement, content)
    
    return content


def fix_arrow_parameters(content: str) -> str:
    """Fix Arrow parameter mappings from ManimGL to ManimCE.
    
    ManimGL: Arrow(tail=point1, tip=point2)
    ManimCE: Arrow(start=point1, end=point2)
    """
    # Pattern to match Arrow with tail/tip parameters
    arrow_patterns = [
        # Arrow(tail=..., tip=...)
        (r'Arrow\s*\(\s*tail\s*=\s*([^,\)]+),\s*tip\s*=\s*([^,\)]+)\)',
         r'Arrow(start=\1, end=\2)'),
        # Arrow(tip=..., tail=...)  (reversed order)
        (r'Arrow\s*\(\s*tip\s*=\s*([^,\)]+),\s*tail\s*=\s*([^,\)]+)\)',
         r'Arrow(start=\2, end=\1)'),
        # Arrow with additional parameters
        (r'Arrow\s*\(\s*tail\s*=\s*([^,\)]+),\s*tip\s*=\s*([^,\)]+),\s*([^)]+)\)',
         r'Arrow(start=\1, end=\2, \3)'),
        (r'Arrow\s*\(\s*tip\s*=\s*([^,\)]+),\s*tail\s*=\s*([^,\)]+),\s*([^)]+)\)',
         r'Arrow(start=\2, end=\1, \3)'),
    ]
    
    fixed = content
    for pattern, replacement in arrow_patterns:
        fixed = re.sub(pattern, replacement, fixed)
    
    return fixed


def apply_all_conversions(content: str) -> str:
    """Apply all conversion utilities to the content."""
    conversions = [
        # fix_string_continuations,  # DISABLED: Too broad, affects non-string continuations
        fix_tex_parenthesis_bug,  # FIX: Apply BEFORE class name conversion to avoid double parenthesis
        convert_manimgl_imports,  # Convert imports first
        fix_common_import_errors,  # NEW: Fix imports early
        convert_latex_strings,  # Convert OldTex with list args BEFORE class name conversion
        convert_class_names,  # Convert class names
        convert_parameterized_scenes,  # NEW: Convert parameterized construct methods
        convert_continual_animation_to_updater,
        convert_old_color_names,
        fix_color_constant_errors,  # NEW: More comprehensive color fixes
        convert_old_methods,
        fix_method_signature_mismatches,  # NEW: Fix method signatures
        fix_arrow_parameters,  # NEW: Fix Arrow tail/tip to start/end
        convert_transform_animations,
        convert_3d_scene_methods,
        add_config_dict_conversion,
        convert_frame_constants,
        add_undefined_class_stubs,
        add_missing_base_methods,  # NEW: Add missing methods
        add_path_functions,  # NEW: Add path function implementations
        add_utility_functions,  # NEW: Add utility functions
        remove_pi_creature_dependencies,  # NEW: Comprehensive Pi Creature removal
    ]
    
    result = content
    for conversion_func in conversions:
        result = conversion_func(result)
    
    return result


# Additional helper functions for specific conversions

def extract_scenes(content: str) -> List[Tuple[str, str]]:
    """Extract all Scene classes from content."""
    pattern = r'class\s+(\w+)\(.*Scene.*?\):(.*?)(?=\nclass|\Z)'
    matches = re.findall(pattern, content, re.DOTALL)
    return matches


def convert_latex_strings(content: str) -> str:
    """
    Convert LaTeX string formatting from old to new style.
    
    Old: TextMobject("$x^2$")
    New: MathTex("x^2")
    
    Also handles OldTex with list arguments.
    """
    # Pattern for TextMobject with LaTeX
    pattern = r'TextMobject\(\s*["\'](\$[^"\']+\$)["\']'
    
    def replace_latex(match):
        latex_content = match.group(1)
        # ManimCE's MathTex expects LaTeX without dollar signs
        # Strip outer dollar signs
        clean_latex = latex_content.strip('$')
        
        # However, some symbols like \Leftrightarrow need to be in math mode
        # Check if the content has LaTeX commands that require math mode
        math_mode_required = any(cmd in clean_latex for cmd in [
            r'\Leftrightarrow', r'\Rightarrow', r'\Leftarrow', 
            r'\leftrightarrow', r'\rightarrow', r'\leftarrow',
            r'\iff', r'\implies', r'\therefore', r'\because'
        ])
        
        if math_mode_required and '$' not in clean_latex:
            # Wrap in dollar signs for math mode
            clean_latex = f'${clean_latex}$'
            
        return f'MathTex("{clean_latex}"'
    
    content = re.sub(pattern, replace_latex, content)
    
    # Handle OldTex with list arguments BEFORE class name conversion
    # OldTex(SOME_LIST) -> MathTex(*SOME_LIST) for math content
    content = re.sub(
        r'\bOldTex\(([A-Z_]+(?:_TEXT|_LIST)?)\)',
        r'MathTex(*\1)',
        content
    )
    
    # OldTex with size parameter
    content = re.sub(
        r'\bOldTex\(([A-Z_]+(?:_TEXT|_LIST)?),\s*size\s*=\s*[^)]+\)',
        r'MathTex(*\1)',
        content
    )
    
    # Fix Tex/MathTex with list/constant arguments - add unpacking
    # For variables that likely contain math content based on their names
    math_var_patterns = ['equation', 'formula', 'math', 'expr', 'sum', 'integral', 'derivative']
    
    def should_use_mathtex_for_var(var_name):
        """Check if a variable name suggests mathematical content."""
        var_lower = var_name.lower()
        return any(pattern in var_lower for pattern in math_var_patterns)
    
    # Handle Tex with variable arguments
    def replace_tex_with_var(match):
        var_name = match.group(2)
        if should_use_mathtex_for_var(var_name):
            return f'MathTex(*{var_name})'
        else:
            # Keep as Tex for text content
            return f'Tex(*{var_name})'
    
    content = re.sub(
        r'\b(Tex)\(([A-Z_]+(?:_TEXT|_LIST)?)\)',
        replace_tex_with_var,
        content
    )
    
    # Already converted MathTex should keep the unpacking
    content = re.sub(
        r'\bMathTex\(([A-Z_]+(?:_TEXT|_LIST)?)\)',
        r'MathTex(*\1)',
        content
    )
    
    # Handle cases with size parameter - check if it's math content
    def replace_tex_with_size(match):
        var_name = match.group(1)
        if should_use_mathtex_for_var(var_name):
            return f'MathTex(*{var_name})'
        else:
            # For text content, keep as Tex and remove size parameter
            return f'Tex(*{var_name})'
    
    content = re.sub(
        r'\bTex\(([A-Z_]+(?:_TEXT|_LIST)?),\s*size\s*=\s*[^)]+\)',
        replace_tex_with_size,
        content
    )
    
    return content


def add_scene_config_decorator(content: str) -> str:
    """
    Add config decorator for scenes that need special configuration.
    """
    # Check if scene needs special config
    if 'ThreeDScene' in content:
        config_decorator = """
# For 3D scenes in ManimCE, you might need:
# from manim import config
# config.renderer = "opengl"  # For interactive 3D scenes
"""
        
        # Add after imports
        import_end = 0
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith(('import', 'from', '#')):
                import_end = i
                break
        
        lines.insert(import_end, config_decorator)
        return '\n'.join(lines)
    
    return content


def generate_test_scene(scene_name: str, is_3d: bool = False) -> str:
    """Generate a simple test scene for the converted code."""
    base_class = "ThreeDScene" if is_3d else "Scene"
    
    test_code = f'''
class Test{scene_name}({base_class}):
    """Test scene to verify {scene_name} renders correctly."""
    
    def construct(self):
        # Simple test animation
        test_text = Text("Testing {scene_name}", font_size=48)
        self.play(Write(test_text))
        self.wait()
        
        # Add more specific tests based on original scene
        # TODO: Add scene-specific test code
        
        self.play(FadeOut(test_text))
'''
    
    return test_code


def add_path_functions(content: str) -> str:
    """Add path function implementations if they're used in the code."""
    path_functions_code = '''
# Path functions for motion animations
def straight_path(start_point, end_point):
    """Create a straight path function from start to end."""
    def path_func(t):
        return interpolate(start_point, end_point, t)
    return path_func

def clockwise_path(start_point, end_point, center=None):
    """Create a clockwise arc path function."""
    if center is None:
        center = (start_point + end_point) / 2
    
    def path_func(t):
        # Calculate angles
        start_angle = np.angle(complex(*(start_point - center)[:2]))
        end_angle = np.angle(complex(*(end_point - center)[:2]))
        
        # Ensure clockwise motion
        if end_angle > start_angle:
            end_angle -= 2 * PI
        
        angle = interpolate(start_angle, end_angle, t)
        radius = np.linalg.norm(start_point - center)
        
        return center + radius * np.array([np.cos(angle), np.sin(angle), 0])
    
    return path_func

def counterclockwise_path(start_point, end_point, center=None):
    """Create a counterclockwise arc path function."""
    if center is None:
        center = (start_point + end_point) / 2
    
    def path_func(t):
        # Calculate angles
        start_angle = np.angle(complex(*(start_point - center)[:2]))
        end_angle = np.angle(complex(*(end_point - center)[:2]))
        
        # Ensure counterclockwise motion
        if end_angle < start_angle:
            end_angle += 2 * PI
        
        angle = interpolate(start_angle, end_angle, t)
        radius = np.linalg.norm(start_point - center)
        
        return center + radius * np.array([np.cos(angle), np.sin(angle), 0])
    
    return path_func
'''
    
    # Check if any path functions are used
    needs_path_functions = any(
        func in content for func in 
        ['clockwise_path', 'counterclockwise_path', 'straight_path']
    )
    
    if needs_path_functions:
        # Add after imports
        lines = content.split('\n')
        insert_pos = 0
        
        # Find position after imports
        for i, line in enumerate(lines):
            if 'from manim import *' in line:
                insert_pos = i + 1
                # Skip any existing comments or empty lines
                while insert_pos < len(lines) and (
                    lines[insert_pos].strip() == '' or 
                    lines[insert_pos].strip().startswith('#')
                ):
                    insert_pos += 1
                break
        
        # Also need to import numpy and interpolate
        if 'import numpy as np' not in content:
            lines.insert(insert_pos, 'import numpy as np')
            insert_pos += 1
        
        if 'from manim import interpolate' not in content:
            # Check if we need to import interpolate and PI
            needs_interpolate = 'interpolate' in path_functions_code
            needs_pi = 'PI' in path_functions_code
            imports_needed = []
            
            if needs_interpolate:
                imports_needed.append('interpolate')
            if needs_pi:
                imports_needed.append('PI')
                
            if imports_needed:
                lines.insert(insert_pos, f'from manim import {", ".join(imports_needed)}')
                insert_pos += 1
        
        lines.insert(insert_pos, path_functions_code)
        return '\n'.join(lines)
    
    return content


def add_utility_functions(content: str) -> str:
    """Add utility functions like get_room_colors if they're used."""
    utility_functions_code = '''
# Utility functions
def get_room_colors():
    """Return a color scheme for room visualization."""
    return {
        'walls': GREY_D,
        'floor': GREY_E,
        'ceiling': GREY_C,
        'furniture': GREY_B,
        'accent': BLUE_D,
        'light': YELLOW,
        'shadow': BLACK
    }
'''
    
    if 'get_room_colors' in content:
        # Add after imports
        lines = content.split('\n')
        insert_pos = 0
        
        for i, line in enumerate(lines):
            if 'from manim import *' in line:
                insert_pos = i + 1
                while insert_pos < len(lines) and (
                    lines[insert_pos].strip() == '' or 
                    lines[insert_pos].strip().startswith('#')
                ):
                    insert_pos += 1
                break
        
        lines.insert(insert_pos, utility_functions_code)
        return '\n'.join(lines)
    
    return content


def convert_parameterized_scenes(content: str) -> str:
    """Convert ManimGL parameterized scenes to ManimCE compatible format.
    
    ManimGL allows construct(self, param1, param2) but ManimCE only supports construct(self).
    This function:
    1. Detects parameterized construct methods
    2. Creates an __init__ method to store parameters
    3. Converts construct to use self.param instead of direct parameters
    """
    import re
    
    lines = content.split('\n')
    result_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Look for class definitions
        class_match = re.match(r'^class\s+(\w+).*:', line)
        if class_match:
            class_name = class_match.group(1)
            result_lines.append(line)
            i += 1
            
            # Look for parameterized construct within this class
            class_indent = len(line) - len(line.lstrip())
            method_indent = ' ' * (class_indent + 4)
            
            # Find the construct method
            construct_start = -1
            construct_params = None
            
            j = i
            while j < len(lines) and (lines[j].strip() == '' or lines[j].startswith(' ')):
                construct_match = re.match(
                    rf'^{method_indent}def\s+construct\s*\(\s*self\s*,\s*([^)]+)\)\s*:',
                    lines[j]
                )
                
                if construct_match:
                    construct_start = j
                    # Parse parameters
                    params_str = construct_match.group(1)
                    # Remove default values for parsing
                    params_str = re.sub(r'=\s*[^,)]+', '', params_str)
                    construct_params = [p.strip() for p in params_str.split(',') if p.strip()]
                    break
                    
                # Stop if we hit another method or class
                if lines[j].strip() and not lines[j].startswith(' '):
                    break
                j += 1
            
            if construct_start >= 0 and construct_params:
                # We found a parameterized construct method
                # First, check if __init__ already exists
                has_init = False
                for k in range(i, construct_start):
                    if re.match(rf'^{method_indent}def\s+__init__', lines[k]):
                        has_init = True
                        break
                
                if not has_init:
                    # Add __init__ method
                    init_lines = [
                        f'{method_indent}def __init__(self, {", ".join(construct_params)}):',
                        f'{method_indent}    super().__init__()'
                    ]
                    for param in construct_params:
                        init_lines.append(f'{method_indent}    self.{param} = {param}')
                    init_lines.append('')
                    
                    # Insert __init__ after class definition
                    result_lines.extend(init_lines)
                
                # Now process the construct method and replace parameters
                while i < construct_start:
                    result_lines.append(lines[i])
                    i += 1
                
                # Change construct signature
                result_lines.append(f'{method_indent}def construct(self):')
                i += 1
                
                # Process construct body, replacing parameter references
                while i < len(lines):
                    if i >= len(lines):
                        break
                        
                    line = lines[i]
                    
                    # Check if we've left the construct method
                    if line.strip() and not line.startswith(method_indent + ' '):
                        # We've hit another method or end of class
                        break
                    
                    # Replace parameter references with self.param
                    modified_line = line
                    for param in construct_params:
                        # Match param as a standalone word (not part of another identifier)
                        modified_line = re.sub(
                            rf'\b{param}\b',
                            f'self.{param}',
                            modified_line
                        )
                    
                    result_lines.append(modified_line)
                    i += 1
                
                continue
        
        result_lines.append(line)
        i += 1
    
    return '\n'.join(result_lines)