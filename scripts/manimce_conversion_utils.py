#!/usr/bin/env python3
"""
Utility functions for ManimGL to ManimCE conversion.

This module contains helper functions for common conversion tasks
and patterns that appear frequently in the conversion process.
"""

import re
from typing import Dict, List, Tuple, Optional


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
        'GraphScene': '''class GraphScene(Scene):
    """Basic GraphScene compatibility stub."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.x_min = -1
        self.x_max = 10
        self.y_min = -1
        self.y_max = 10
        self.axes = None
        
    def setup_axes(self, animate=False):
        """Create and add axes to the scene."""
        self.axes = Axes(
            x_range=[self.x_min, self.x_max, 1],
            y_range=[self.y_min, self.y_max, 1],
        )
        if animate:
            self.play(Create(self.axes))
        else:
            self.add(self.axes)
        return self.axes
    
    def coords_to_point(self, x, y):
        """Convert graph coordinates to point."""
        if self.axes:
            return self.axes.c2p(x, y)
        return ORIGIN
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


def apply_all_conversions(content: str) -> str:
    """Apply all conversion utilities to the content."""
    conversions = [
        convert_continual_animation_to_updater,
        convert_old_color_names,
        convert_old_methods,
        convert_transform_animations,
        convert_3d_scene_methods,
        add_config_dict_conversion,
        convert_frame_constants,
        add_undefined_class_stubs,
        suggest_pi_creature_replacement,
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
    """
    # Pattern for TextMobject with LaTeX
    pattern = r'TextMobject\(\s*["\'](\$[^"\']+\$)["\']'
    
    def replace_latex(match):
        latex_content = match.group(1)
        # Remove dollar signs
        clean_latex = latex_content.strip('$')
        return f'MathTex("{clean_latex}"'
    
    return re.sub(pattern, replace_latex, content)


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