#!/usr/bin/env python3
"""
Comprehensive API mapping database for ManimGL to ManimCE conversion.

This module contains detailed mappings of all API differences between
ManimGL and ManimCE, including animations, methods, classes, and parameters.
"""

from typing import Dict, List, Optional, Any, Tuple

# Animation mappings with parameter information
ANIMATION_MAPPINGS: Dict[str, Dict[str, Any]] = {
    # Creation animations
    'ShowCreation': {
        'new_name': 'Create',
        'param_mappings': {
            'run_time': 'run_time',
            'rate_func': 'rate_func',
            'lag_ratio': None  # Not supported, needs workaround
        },
        'workaround': 'For lag_ratio, use AnimationGroup with delays',
        'notes': 'Most common animation conversion'
    },
    'DrawBorderThenFill': {
        'new_name': 'DrawBorderThenFill',
        'param_mappings': {
            'run_time': 'run_time',
            'rate_func': 'rate_func',
            'stroke_width': 'stroke_width',
            'stroke_color': 'stroke_color'
        }
    },
    'ShowPassingFlash': {
        'new_name': 'ShowPassingFlash',
        'param_mappings': {
            'time_width': 'time_width'
        }
    },
    'ShowCreationThenDestruction': {
        'new_name': 'ShowPassingFlash',
        'param_mappings': {},
        'notes': 'Approximate replacement'
    },
    'ShowCreationThenFadeOut': {
        'new_name': 'Succession',
        'special_handling': 'Needs to be wrapped: Succession(Create(mob), FadeOut(mob))',
        'param_mappings': {}
    },
    'Uncreate': {
        'new_name': 'Uncreate',
        'param_mappings': {
            'run_time': 'run_time',
            'rate_func': 'rate_func'
        }
    },
    
    # Transform animations
    'ApplyMethod': {
        'new_name': 'ApplyMethod',
        'param_mappings': {},
        'notes': 'Consider using mob.animate syntax instead'
    },
    'ApplyPointwiseFunction': {
        'new_name': 'ApplyPointwiseFunction',
        'param_mappings': {}
    },
    'ApplyMatrix': {
        'new_name': 'ApplyMatrix',
        'param_mappings': {}
    },
    'WiggleOutThenIn': {
        'new_name': 'Wiggle',
        'param_mappings': {
            'scale_value': 'scale_value',
            'rotation_angle': 'rotation_angle'
        }
    },
    'CircleIndicate': {
        'new_name': 'Indicate',
        'param_mappings': {
            'scale_factor': 'scale_factor',
            'color': 'color'
        }
    },
    'Flash': {
        'new_name': 'Flash',
        'param_mappings': {
            'flash_radius': 'flash_radius',
            'line_length': 'line_length',
            'num_lines': 'num_lines'
        }
    },
    
    # Text animations
    'WriteFrame': {
        'new_name': 'Create',
        'param_mappings': {},
        'notes': 'Frame writing not directly supported'
    },
    
    # Camera animations
    'MoveCamera': {
        'new_name': 'MoveCamera',
        'param_mappings': {
            'frame_center': 'frame_center',
            'zoom_factor': 'zoom'
        },
        'notes': '3D scene specific'
    },
    
    # Special animations
    'ContinualAnimation': {
        'new_name': None,
        'special_handling': 'Convert to mob.add_updater(lambda m, dt: ...)',
        'notes': 'Base class for continuous animations'
    },
    
    # Custom 3b1b animations
    'FlipThroughNumbers': {
        'new_name': None,
        'special_handling': 'Create custom implementation using AnimationGroup',
        'notes': 'Animation that flips through number displays',
        'param_mappings': {
            'numbers': 'numbers',
            'run_time': 'run_time'
        }
    },
    'DelayByOrder': {
        'new_name': 'LaggedStart',
        'param_mappings': {
            'animation': 'animations',  # Need to wrap single animation
            'lag_ratio': 'lag_ratio'
        },
        'special_handling': 'Convert to LaggedStart with submobject animations',
        'notes': 'Delays animations based on submobject order'
    },
    
    # NEW: Critical missing animations from 3b1b codebase
    'FadeToColor': {
        'new_name': None,
        'special_handling': 'Use mob.animate.set_color() or custom implementation',
        'param_mappings': {
            'color': 'color',
            'run_time': 'run_time'
        },
        'notes': 'Gradual color change animation - very common in 3b1b videos'
    },
    'UpdateFromFunc': {
        'new_name': None,
        'special_handling': 'Convert to mob.add_updater(lambda m, dt: ...)',
        'param_mappings': {
            'func': 'update_function',
            'suspend_mobject_updating': None
        },
        'notes': 'Function-based continuous update - convert to updater pattern'
    },
    'MaintainPositionRelativeTo': {
        'new_name': None,
        'special_handling': 'Convert to updater that maintains relative position',
        'param_mappings': {
            'mobject': 'tracked_mobject'
        },
        'notes': 'Keep mobject positioned relative to another'
    },
}

# Method to property conversions
METHOD_TO_PROPERTY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    # Getters
    'get_width': {
        'property': 'width',
        'read_only': True
    },
    'get_height': {
        'property': 'height',
        'read_only': True
    },
    'get_x': {
        'property': 'x',
        'read_only': True
    },
    'get_y': {
        'property': 'y',
        'read_only': True
    },
    'get_z': {
        'property': 'z',
        'read_only': True
    },
    'get_center': {
        'property': None,
        'notes': 'Still a method in ManimCE'
    },
    'get_tex_string': {
        'property': 'tex_string',
        'read_only': True
    },
    'get_fill_color': {
        'property': 'fill_color',
        'read_only': True
    },
    'get_stroke_color': {
        'property': 'stroke_color',
        'read_only': True
    },
    'get_fill_opacity': {
        'property': 'fill_opacity',
        'read_only': True
    },
    'get_stroke_opacity': {
        'property': 'stroke_opacity',
        'read_only': True
    },
    'get_stroke_width': {
        'property': 'stroke_width',
        'read_only': True
    },
    
    # NEW: Critical missing method mappings from 3b1b codebase
    'get_top': {
        'property': 'top',
        'read_only': True,
        'notes': 'Boundary point getter - very common'
    },
    'get_bottom': {
        'property': 'bottom',
        'read_only': True,
        'notes': 'Boundary point getter'
    },
    'get_left': {
        'property': 'left',
        'read_only': True,
        'notes': 'Boundary point getter'
    },
    'get_right': {
        'property': 'right',
        'read_only': True,
        'notes': 'Boundary point getter'
    },
    'get_corner': {
        'method': 'get_corner',
        'notes': 'Still exists in ManimCE'
    },
    'get_points': {
        'property': 'points',
        'read_only': True,
        'notes': 'Access underlying point array'
    },
    'get_anchors': {
        'property': 'points',
        'special_handling': 'Filter for anchor points only',
        'notes': 'Bezier curve anchor points'
    },
    'get_boundary_point': {
        'method': 'point_from_proportion',
        'special_handling': 'Use point_from_proportion for parametric boundary',
        'notes': 'Get point on object boundary'
    },
    'sort_points': {
        'method': None,
        'special_handling': 'Use custom sorting logic or remove',
        'notes': 'Common point ordering method - frequently causes errors'
    },
    'nudge': {
        'method': 'shift',
        'param_mappings': {
            'scale_factor': 'scale_factor'
        },
        'notes': 'Small position adjustment method'
    },
    'center_of_mass': {
        'method': 'get_center_of_mass',
        'notes': 'Calculate geometric center'
    },
    'add_to_back': {
        'method': 'add',
        'special_handling': 'Use add() - ManimCE handles z-order differently',
        'notes': 'Add submobject behind others'
    },
    'replace_submobject': {
        'method': None,
        'special_handling': 'Use remove() and add() sequence',
        'notes': 'Replace specific submobject'
    },
    
    # Setters
    'set_width': {
        'property': 'width',
        'setter': True,
        'alternative': 'scale_to_fit_width'
    },
    'set_height': {
        'property': 'height',
        'setter': True,
        'alternative': 'scale_to_fit_height'
    },
    'set_x': {
        'method': 'move_to',
        'special_handling': 'Use move_to([x, old_y, old_z])'
    },
    'set_y': {
        'method': 'move_to',
        'special_handling': 'Use move_to([old_x, y, old_z])'
    },
    'set_z': {
        'method': 'move_to',
        'special_handling': 'Use move_to([old_x, old_y, z])'
    },
    'set_fill': {
        'method': 'set_fill',
        'param_mappings': {
            'color': 'color',
            'opacity': 'opacity'
        }
    },
    'set_stroke': {
        'method': 'set_stroke',
        'param_mappings': {
            'color': 'color',
            'width': 'width',
            'opacity': 'opacity'
        }
    },
    'set_color': {
        'method': 'set_color',
        'param_mappings': {
            'color': 'color'
        }
    },
    
    # Pi Creature instance methods - comment out as no ManimCE equivalent
    'change': {
        'method': None,
        'special_handling': 'Comment out - Pi Creature method',
        'notes': 'Pi Creature emotion change method'
    },
    'look_at': {
        'method': None,
        'special_handling': 'Comment out when used on Pi Creatures',
        'notes': 'Pi Creature look direction method'
    },
    'blink': {
        'method': None,
        'special_handling': 'Comment out when used on Pi Creatures',
        'notes': 'Pi Creature blink method'
    },
    'wave': {
        'method': None,
        'special_handling': 'Comment out when used on Pi Creatures',
        'notes': 'Pi Creature wave method'
    },
    'get_bubble': {
        'method': None,
        'special_handling': 'Comment out - Pi Creature method',
        'notes': 'Pi Creature bubble creation method'
    },
    'says': {
        'method': None,
        'special_handling': 'Comment out - Pi Creature method',
        'notes': 'Pi Creature speech method'
    },
    'thinks': {
        'method': None,
        'special_handling': 'Comment out - Pi Creature method',
        'notes': 'Pi Creature thought method'
    },
    
    # TeacherStudentsScene methods - comment out as no ManimCE equivalent
    'student_says': {
        'method': None,
        'special_handling': 'Comment out - TeacherStudentsScene method',
        'notes': 'TeacherStudentsScene student speech method'
    },
    'teacher_says': {
        'method': None,
        'special_handling': 'Comment out - TeacherStudentsScene method',
        'notes': 'TeacherStudentsScene teacher speech method'
    },
    'student_thinks': {
        'method': None,
        'special_handling': 'Comment out - TeacherStudentsScene method',
        'notes': 'TeacherStudentsScene student thought method'
    },
    'teacher_thinks': {
        'method': None,
        'special_handling': 'Comment out - TeacherStudentsScene method',
        'notes': 'TeacherStudentsScene teacher thought method'
    },
    'play_student_changes': {
        'method': None,
        'special_handling': 'Comment out - TeacherStudentsScene method',
        'notes': 'TeacherStudentsScene animation method'
    },
    'change_students': {
        'method': None,
        'special_handling': 'Comment out - TeacherStudentsScene method',
        'notes': 'TeacherStudentsScene student emotion method'
    },
    'get_student_changes': {
        'method': None,
        'special_handling': 'Comment out - TeacherStudentsScene method',
        'notes': 'TeacherStudentsScene method for getting student change animations'
    },
    'random_blink_wait': {
        'method': None,
        'special_handling': 'Comment out - TeacherStudentsScene method',
        'notes': 'TeacherStudentsScene method for random blinking'
    },
    'shift_onto_screen': {
        'method': None,
        'special_handling': 'Comment out when used on Pi Creatures',
        'notes': 'Pi Creature method for moving onto screen'
    },
    'change_mode': {
        'method': None,
        'special_handling': 'Comment out when used on Pi Creatures',
        'notes': 'Pi Creature method for changing emotional state'
    },
    'bubble_thought': {
        'method': None,
        'special_handling': 'Comment out - Pi Creature method',
        'notes': 'Pi Creature method for thought bubbles'
    },
    'bubble_speak': {
        'method': None,
        'special_handling': 'Comment out - Pi Creature method',
        'notes': 'Pi Creature method for speech bubbles'
    }
}

# Class mappings
CLASS_MAPPINGS: Dict[str, Dict[str, Any]] = {
    # Text objects
    'TextMobject': {
        'new_class': 'Text',
        'param_mappings': {
            'tex_to_color_map': None,  # Needs special handling
            'arg_separator': None,
            'alignment': 'alignment'
        },
        'special_handling': 'tex_to_color_map → use set_color_by_text()',
        'notes': 'Major API difference'
    },
    'TexMobject': {
        'new_class': 'MathTex',
        'param_mappings': {
            'tex_to_color_map': None,
            'arg_separator': None
        },
        'special_handling': 'Use raw strings for LaTeX'
    },
    'TexText': {
        'new_class': 'Tex',
        'param_mappings': {},
        'special_handling': 'Use raw strings for LaTeX'
    },
    'OldTex': {
        'new_class': 'Tex',
        'param_mappings': {},
        'notes': 'Convert to raw strings'
    },
    'OldTexText': {
        'new_class': 'Text',
        'param_mappings': {},
        'notes': 'Legacy class'
    },
    
    # Base classes
    'Mobject': {
        'new_class': 'Mobject',
        'param_mappings': {},
        'notes': 'Base class exists in both, but API may differ'
    },
    
    # Shapes
    'Mobject1D': {
        'new_class': 'VMobject',
        'param_mappings': {},
        'notes': 'No direct equivalent, use VMobject'
    },
    'Mobject2D': {
        'new_class': 'VMobject',
        'param_mappings': {},
        'notes': 'No direct equivalent, use VMobject'
    },
    
    # Scenes
    'GraphScene': {
        'new_class': 'Scene',
        'special_handling': 'Need to manually add Axes and coordinate methods',
        'required_imports': ['Axes', 'Create'],
        'notes': 'Complex conversion needed'
    },
    'NumberLineScene': {
        'new_class': 'Scene',
        'special_handling': 'Need to manually add NumberLine',
        'required_imports': ['NumberLine'],
        'notes': 'Requires setup method'
    },
    'RearrangeEquation': {
        'new_class': 'Scene',
        'special_handling': 'Custom implementation provided in stubs',
        'required_imports': ['MathTex', 'Write', 'Transform', 'TransformMatchingTex', 'FadeIn', 'FadeOut'],
        'notes': 'Static method pattern needs special handling'
    },
    'ThreeDScene': {
        'new_class': 'ThreeDScene',
        'param_mappings': {},
        'config_updates': {
            'renderer': 'opengl'  # May need this for interactive 3D
        }
    },
    'SpecialThreeDScene': {
        'new_class': 'ThreeDScene',
        'param_mappings': {},
        'notes': 'Custom 3b1b class'
    },
    
    # Animation base classes
    'ContinualAnimation': {
        'new_class': None,
        'special_handling': 'Convert to updater functions',
        'notes': 'Fundamental API difference'
    },
    
    # Groups
    'VectorizedPoint': {
        'new_class': 'VectorizedPoint',
        'param_mappings': {}
    },
    
    # Special objects
    'PiCreature': {
        'new_class': None,
        'special_handling': 'Comment out - no equivalent',
        'notes': 'Proprietary 3b1b asset'
    },
    'Randolph': {
        'new_class': None,
        'special_handling': 'Comment out - no equivalent',
        'notes': 'Proprietary 3b1b asset'
    },
    'Mortimer': {
        'new_class': None,
        'special_handling': 'Comment out - no equivalent',
        'notes': 'Proprietary 3b1b asset'
    },
    'ThoughtBubble': {
        'new_class': None,
        'special_handling': 'Comment out - no equivalent',
        'notes': 'Proprietary 3b1b asset - part of Pi Creature system'
    },
    'SpeechBubble': {
        'new_class': None,
        'special_handling': 'Comment out - no equivalent',
        'notes': 'Proprietary 3b1b asset - part of Pi Creature system'
    },
    'SimpleTex': {
        'new_class': 'MathTex',
        'param_mappings': {},
        'notes': 'SimpleTex is a specialized Tex class - map to MathTex'
    },
    
    # NEW: Critical missing class mappings from 3b1b codebase
    'OldTexText': {
        'new_class': 'Tex',  # LaTeX-based text, not Text
        'param_mappings': {
            'arg_separator': None,
            'tex_to_color_map': None
        },
        'special_handling': 'Use raw LaTeX strings with Tex class',
        'notes': 'Legacy LaTeX text renderer - frequently used in 3b1b videos'
    },
    'Point': {
        'new_class': 'Dot',
        'special_handling': 'Use Dot with radius=0 for invisible point',
        'param_mappings': {
            'location': 'point'
        },
        'notes': 'Invisible point object used for positioning'
    },
    'ComplexPlane': {
        'new_class': 'ComplexPlane',
        'param_mappings': {},
        'notes': 'Exists in ManimCE but may have different parameters'
    },
    'RearrangeEquation': {
        'new_class': None,
        'special_handling': 'Create custom implementation using TransformMatchingTex',
        'required_imports': ['TransformMatchingTex', 'MathTex'],
        'notes': 'Equation rearrangement helper - very common in math videos'
    },
    
    # Pi Creature animations - comment out as no ManimCE equivalent
    'WaveArm': {
        'new_class': None,
        'special_handling': 'Comment out - no equivalent',
        'notes': 'Pi Creature animation - proprietary 3b1b asset'
    },
    'BlinkPiCreature': {
        'new_class': None,
        'special_handling': 'Comment out - no equivalent',
        'notes': 'Pi Creature animation - proprietary 3b1b asset'
    },
    'Blink': {
        'new_class': None,
        'special_handling': 'Comment out when used with Pi Creatures',
        'notes': 'Generic animation but often used with Pi Creatures'
    },
    'RemovePiCreatureBubble': {
        'new_class': None,
        'special_handling': 'Comment out - no equivalent',
        'notes': 'Pi Creature bubble animation - proprietary 3b1b asset'
    },
    'PiCreatureBubbleIntroduction': {
        'new_class': None,
        'special_handling': 'Comment out - no equivalent',
        'notes': 'Pi Creature bubble introduction animation - proprietary 3b1b asset'
    },
    
    # Pi Creature scene classes
    'PiCreatureScene': {
        'new_class': 'Scene',
        'special_handling': 'Remove Pi Creature methods and convert to basic Scene',
        'notes': 'Scene with Pi Creature functionality - needs cleanup'
    },
    'TeacherStudentsScene': {
        'new_class': 'Scene',
        'special_handling': 'Remove Pi Creature methods and convert to basic Scene',
        'notes': 'Classroom scene with Pi Creatures - needs cleanup'
    }
}

# Color mappings
COLOR_MAPPINGS: Dict[str, str] = {
    'COLOR_MAP': 'MANIM_COLORS',
    'LIGHT_GRAY': 'LIGHT_GREY',
    'DARK_GRAY': 'DARK_GREY',
    'GRAY': 'GREY',
    'GRAY_A': 'GREY_A',
    'GRAY_B': 'GREY_B',
    'GRAY_C': 'GREY_C',
    'GRAY_D': 'GREY_D',
    'GRAY_E': 'GREY_E',
    # Extended color variants from ManimGL
    # Map to closest ManimCE equivalents or use interpolated colors
    'BLUE_A': 'PURE_BLUE',  # Lightest blue
    'BLUE_B': 'BLUE',       # Light blue
    'BLUE_C': 'BLUE',       # Standard blue (default)
    'BLUE_D': 'DARK_BLUE',  # Dark blue
    'BLUE_E': 'DARKER_BLUE', # Darkest blue
    'GREEN_A': 'LIGHT_GREEN',
    'GREEN_B': 'GREEN',
    'GREEN_C': 'GREEN',      # Standard green (default)
    'GREEN_D': 'DARK_GREEN',
    'GREEN_E': 'DARK_GREEN', # No darker variant, use same
    'RED_A': 'LIGHT_RED',
    'RED_B': 'RED',
    'RED_C': 'RED',          # Standard red (default)
    'RED_D': 'DARK_RED',
    'RED_E': 'MAROON',       # Darkest red
    'YELLOW_A': 'LIGHT_YELLOW',
    'YELLOW_B': 'YELLOW',
    'YELLOW_C': 'YELLOW',    # Standard yellow (default)
    'YELLOW_D': 'GOLD',      # Darker yellow
    'YELLOW_E': 'GOLD_E',    # Darkest yellow
    'PINK_A': 'LIGHT_PINK',
    'PINK_B': 'PINK',
    'PINK_C': 'PINK',        # Standard pink (default)
    'PINK_D': 'LIGHT_MAROON',
    'PINK_E': 'MAROON',
    'TEAL_A': 'LIGHT_BLUE',  # No direct teal variants
    'TEAL_B': 'TEAL',
    'TEAL_C': 'TEAL',        # Standard teal (default)
    'TEAL_D': 'DARK_BLUE',   # Approximate with dark blue
    'TEAL_E': 'DARKER_BLUE', # Approximate with darker blue
    'PURPLE_A': 'LIGHT_PURPLE',
    'PURPLE_B': 'PURPLE',
    'PURPLE_C': 'PURPLE',    # Standard purple (default)
    'PURPLE_D': 'DARK_PURPLE',
    'PURPLE_E': 'DARK_PURPLE', # No darker variant
    'MAROON_A': 'LIGHT_MAROON',
    'MAROON_B': 'MAROON',
    'MAROON_C': 'MAROON',    # Standard maroon (default)
    'MAROON_D': 'DARK_MAROON',
    'MAROON_E': 'DARK_MAROON', # No darker variant
    'ORANGE_A': 'LIGHT_ORANGE',
    'ORANGE_B': 'ORANGE', 
    'ORANGE_C': 'ORANGE',    # Standard orange (default)
    'ORANGE_D': 'DARK_ORANGE',
    'ORANGE_E': 'DARK_ORANGE', # No darker variant
}

# Constant mappings
CONSTANT_MAPPINGS: Dict[str, Dict[str, Any]] = {
    'FRAME_HEIGHT': {
        'new_value': 'config.frame_height',
        'type': 'config_attr'
    },
    'FRAME_WIDTH': {
        'new_value': 'config.frame_width',
        'type': 'config_attr'
    },
    'FRAME_X_RADIUS': {
        'new_value': 'config.frame_width / 2',
        'type': 'expression'
    },
    'FRAME_Y_RADIUS': {
        'new_value': 'config.frame_height / 2',
        'type': 'expression'
    },
    'PIXEL_HEIGHT': {
        'new_value': 'config.pixel_height',
        'type': 'config_attr'
    },
    'PIXEL_WIDTH': {
        'new_value': 'config.pixel_width',
        'type': 'config_attr'
    },
    'DEFAULT_MOBJECT_TO_EDGE_BUFFER': {
        'new_value': 'MED_SMALL_BUFF',
        'type': 'constant'
    },
    'DEFAULT_MOBJECT_TO_MOBJECT_BUFFER': {
        'new_value': 'MED_SMALL_BUFF',
        'type': 'constant'
    },
    'VIDEO_DIR': {
        'new_value': '"./"',
        'type': 'string',
        'notes': 'Default to current directory'
    }
}

# Direction constant mappings (corner shortcuts)
DIRECTION_MAPPINGS: Dict[str, str] = {
    'DOWN+LEFT': 'DL',
    'DOWN+RIGHT': 'DR',
    'UP+LEFT': 'UL',
    'UP+RIGHT': 'UR',
    'LEFT+DOWN': 'DL',
    'RIGHT+DOWN': 'DR',
    'LEFT+UP': 'UL',
    'RIGHT+UP': 'UR',
}

# Complex conversion patterns that need special handling
COMPLEX_PATTERNS: Dict[str, Dict[str, Any]] = {
    'tex_to_color_map': {
        'pattern': r'tex_to_color_map\s*=\s*{([^}]+)}',
        'handler': 'convert_tex_to_color_map',
        'description': 'Convert to set_color_by_text() calls'
    },
    'CONFIG_dict': {
        'pattern': r'CONFIG\s*=\s*{',
        'handler': 'convert_config_dict',
        'description': 'Convert to class attributes'
    },
    'coordinate_labels': {
        'pattern': r'get_graph_label|get_axis_label',
        'handler': 'convert_graph_labels',
        'description': 'Update to new Axes API'
    },
    'updater_functions': {
        'pattern': r'def update_.*\(.*,\s*dt\)',
        'handler': 'identify_updater_pattern',
        'description': 'Identify updater function patterns'
    },
    'camera_orientation': {
        'pattern': r'set_camera_orientation\(',
        'handler': 'update_camera_calls',
        'description': '3D camera API updates'
    },
    'pi_creature_functions': {
        'pattern': r'def\s+(draw_you|create_pi_creature|make_pi_creature)\s*\(',
        'handler': 'comment_out_pi_creature_functions',
        'description': 'Comment out Pi Creature helper functions'
    },
    
    # NEW: Critical patterns from 3b1b codebase analysis
    'split_tex_objects': {
        'pattern': r'\.split\(\)',
        'handler': 'convert_tex_split_to_submobjects',
        'description': 'Convert .split() on Tex objects to submobject access'
    },
    'point_invisible_objects': {
        'pattern': r'\bPoint\(',
        'handler': 'convert_point_to_dot',
        'description': 'Convert Point() to Dot(radius=0) for invisible points'
    },
    'arrow_tail_direction': {
        'pattern': r'Arrow\([^)]*(?:tail\s*=|direction\s*=)',
        'handler': 'convert_arrow_tail_direction',
        'description': 'Convert tail/direction to start/end parameters'
    },
    'delay_by_order_patterns': {
        'pattern': r'DelayByOrder\(',
        'handler': 'convert_delay_by_order_to_lagged_start',
        'description': 'Convert DelayByOrder to LaggedStart with submobject animations'
    },
    'fade_to_color_patterns': {
        'pattern': r'FadeToColor\(',
        'handler': 'convert_fade_to_color_to_animate',
        'description': 'Convert FadeToColor to mob.animate.set_color()'
    },
    'updater_from_func_patterns': {
        'pattern': r'UpdateFromFunc\(',
        'handler': 'convert_update_from_func_to_updater',
        'description': 'Convert UpdateFromFunc to mob.add_updater() pattern'
    },
    'maintain_position_patterns': {
        'pattern': r'MaintainPositionRelativeTo\(',
        'handler': 'convert_maintain_position_to_updater',
        'description': 'Convert MaintainPositionRelativeTo to relative position updater'
    },
    'sort_points_removal': {
        'pattern': r'\.sort_points\(\)',
        'handler': 'comment_out_sort_points',
        'description': 'Comment out sort_points() calls - not available in ManimCE'
    },
    'rearrange_equation_patterns': {
        'pattern': r'RearrangeEquation\.',
        'handler': 'convert_rearrange_equation_to_transform_matching_tex',
        'description': 'Convert RearrangeEquation to TransformMatchingTex implementation'
    },
    'old_tex_text_usage': {
        'pattern': r'OldTexText\(',
        'handler': 'convert_old_tex_text_to_tex',
        'description': 'Convert OldTexText to Tex with proper LaTeX handling'
    },
    'boundary_point_getters': {
        'pattern': r'\.get_(top|bottom|left|right)\(\)',
        'handler': 'convert_boundary_getters_to_properties',
        'description': 'Convert get_*() boundary methods to properties'
    }
}

# Pi Creature function patterns to remove completely
PI_CREATURE_FUNCTION_PATTERNS: Dict[str, Dict[str, Any]] = {
    'draw_you': {
        'pattern': r'def\s+draw_you\s*\([^)]*\):',
        'action': 'comment_out_function',
        'notes': 'Pi Creature helper function - no ManimCE equivalent'
    },
    'create_pi_creature': {
        'pattern': r'def\s+create_pi_creature\s*\([^)]*\):',
        'action': 'comment_out_function',
        'notes': 'Pi Creature creation helper - no ManimCE equivalent'
    },
    'make_pi_creature': {
        'pattern': r'def\s+make_pi_creature\s*\([^)]*\):',
        'action': 'comment_out_function',
        'notes': 'Pi Creature creation helper - no ManimCE equivalent'
    },
    'get_pi_creature': {
        'pattern': r'def\s+get_pi_creature\s*\([^)]*\):',
        'action': 'comment_out_function',
        'notes': 'Pi Creature getter function - no ManimCE equivalent'
    },
    'setup_pi_creature': {
        'pattern': r'def\s+setup_pi_creature\s*\([^)]*\):',
        'action': 'comment_out_function',
        'notes': 'Pi Creature setup function - no ManimCE equivalent'
    }
}

# Scene-specific conversion templates
SCENE_TEMPLATES: Dict[str, str] = {
    'GraphScene': '''
    def setup_axes(self, animate=False):
        """Create and add axes to the scene."""
        self.axes = Axes(
            x_range=[self.x_min, self.x_max, self.x_axis_step],
            y_range=[self.y_min, self.y_max, self.y_axis_step],
            axis_config=self.axis_config,
        )
        
        if self.include_tip:
            self.axes.add_tip()
            
        if animate:
            self.play(Create(self.axes))
        else:
            self.add(self.axes)
            
        return self.axes
    
    def coords_to_point(self, x, y):
        """Convert graph coordinates to scene point."""
        if hasattr(self, 'axes'):
            return self.axes.c2p(x, y)
        return np.array([x, y, 0])
    
    def point_to_coords(self, point):
        """Convert scene point to graph coordinates."""
        if hasattr(self, 'axes'):
            return self.axes.p2c(point)
        return point[:2]
    
    def get_graph(self, func, **kwargs):
        """Create a graph of the given function."""
        if hasattr(self, 'axes'):
            return self.axes.plot(func, **kwargs)
        raise Exception("Must call setup_axes first")
''',
    
    'NumberLineScene': '''
    def setup(self):
        """Create and add number line to the scene."""
        self.number_line = NumberLine(
            x_range=[-10, 10, 1],
            length=FRAME_WIDTH - 1,
            include_numbers=True,
        )
        self.add(self.number_line)
    
    def number_to_point(self, number):
        """Convert number to point on the number line."""
        return self.number_line.n2p(number)
    
    def point_to_number(self, point):
        """Convert point to number on the number line."""
        return self.number_line.p2n(point)
'''
}

def get_animation_conversion(animation_name: str) -> Optional[Dict[str, Any]]:
    """Get conversion info for a specific animation."""
    return ANIMATION_MAPPINGS.get(animation_name)

def get_method_conversion(method_name: str) -> Optional[Dict[str, Any]]:
    """Get conversion info for a specific method."""
    return METHOD_TO_PROPERTY_MAPPINGS.get(method_name)

def get_class_conversion(class_name: str) -> Optional[Dict[str, Any]]:
    """Get conversion info for a specific class."""
    return CLASS_MAPPINGS.get(class_name)

def get_color_mapping(color_name: str) -> Optional[str]:
    """Get ManimCE equivalent for a ManimGL color."""
    return COLOR_MAPPINGS.get(color_name, color_name)

def get_constant_mapping(constant_name: str) -> Optional[Dict[str, Any]]:
    """Get ManimCE equivalent for a ManimGL constant."""
    return CONSTANT_MAPPINGS.get(constant_name)

def get_required_imports_for_class(class_name: str) -> List[str]:
    """Get additional imports required for a converted class."""
    class_info = CLASS_MAPPINGS.get(class_name, {})
    return class_info.get('required_imports', [])

def get_all_manimce_imports() -> List[str]:
    """Get comprehensive list of ManimCE imports that might be needed."""
    return [
        # Core
        'Scene', 'ThreeDScene',
        # Mobjects
        'Mobject', 'VMobject', 'Group', 'VGroup',
        # Text
        'Text', 'MathTex', 'Tex', 'Code',
        # Shapes
        'Circle', 'Square', 'Rectangle', 'Line', 'Arrow', 'Dot',
        'Polygon', 'RegularPolygon', 'Triangle',
        # Animations
        'Animation', 'Create', 'Write', 'FadeIn', 'FadeOut',
        'Transform', 'ReplacementTransform', 'MoveToTarget',
        'Indicate', 'Flash', 'Wiggle', 'ShowPassingFlash',
        'DrawBorderThenFill', 'Uncreate',
        # Animation groups
        'AnimationGroup', 'Succession', 'LaggedStart',
        # Graphs
        'Axes', 'NumberLine', 'NumberPlane',
        # Constants
        'UP', 'DOWN', 'LEFT', 'RIGHT', 'ORIGIN',
        'UL', 'UR', 'DL', 'DR',
        'RED', 'BLUE', 'GREEN', 'YELLOW', 'WHITE', 'BLACK',
        'GREY', 'GREY_A', 'GREY_B', 'GREY_C',
        'PI', 'TAU', 'DEGREES',
        # Utilities
        'config', 'rate_functions',
    ]

def get_pi_creature_function_patterns() -> Dict[str, Dict[str, Any]]:
    """Get all Pi Creature function patterns that should be commented out."""
    return PI_CREATURE_FUNCTION_PATTERNS

def is_pi_creature_related(name: str) -> bool:
    """Check if a name is related to Pi Creatures and should be commented out."""
    pi_creature_names = {
        'PiCreature', 'Randolph', 'Mortimer', 'ThoughtBubble', 'SpeechBubble',
        'WaveArm', 'BlinkPiCreature', 'Blink', 'RemovePiCreatureBubble',
        'PiCreatureBubbleIntroduction', 'PiCreatureScene', 'TeacherStudentsScene', 
        'draw_you', 'get_bubble_introduction'
    }
    pi_creature_methods = {
        'change', 'look_at', 'blink', 'wave', 'get_bubble', 'says', 'thinks',
        'student_says', 'teacher_says', 'student_thinks', 'teacher_thinks',
        'play_student_changes', 'change_students', 'get_student_changes',
        'random_blink_wait', 'shift_onto_screen', 'change_mode', 
        'bubble_thought', 'bubble_speak'
    }
    return name in pi_creature_names or name in pi_creature_methods