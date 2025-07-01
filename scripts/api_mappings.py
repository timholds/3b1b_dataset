#!/usr/bin/env python3
"""
API Mappings - Comprehensive ManimGL to ManimCE API Differences

This module contains all known API differences between ManimGL and ManimCE.
It serves as the central knowledge base for conversion operations.

Structure:
- CLASS_MAPPINGS: Direct class name changes
- METHOD_MAPPINGS: Method name changes and signature differences
- PARAMETER_CHANGES: Parameter differences for methods
- REMOVED_APIS: APIs that no longer exist in ManimCE
- BEHAVIOR_CHANGES: APIs that exist but behave differently
- PROPERTY_CHANGES: Attributes that became properties or vice versa
"""

# Direct class name mappings
CLASS_MAPPINGS = {
    # Text objects
    'TextMobject': 'Text',
    'TexMobject': 'MathTex',
    'TextWithFixedWidthLetters': 'Text',  # No direct equivalent
    
    # Animations
    'ShowCreation': 'Create',
    'ShowCreationThenDestruction': 'ShowPassingFlash',
    'ShowCreationThenDestructionAround': 'ShowPassingFlashAround',
    'ShowCreationThenFadeOut': 'ShowPassingFlash',
    'ShowCreationThenFadeAround': 'ShowPassingFlashAround',
    'Uncreate': 'Uncreate',
    'DrawBorderThenFill': 'DrawBorderThenFill',
    'ShowIncreasingSubsets': 'ShowIncreasingSubsets',
    'ShowSubmobjectsOneByOne': 'ShowSubmobjectsOneByOne',
    
    # Transform animations
    'CounterclockwiseTransform': 'Transform',  # Use Transform with path_arc
    'ClockwiseTransform': 'Transform',  # Use Transform with path_arc
    
    # Special scenes
    'GraphScene': 'GraphScene',  # Exists but with different API
    'MovingCameraScene': 'MovingCameraScene',
    'ZoomedScene': 'ZoomedScene',
    'ThreeDScene': 'ThreeDScene',
    
    # 3D objects
    'ThreeDMobject': 'Mobject3D',
    'ThreeDVMobject': 'VMobject3D',
    
    # Other objects
    'DashedMobject': 'DashedVMobject',
    'SmallDot': 'Dot',  # Use Dot with smaller radius
}

# Method name changes and signatures
METHOD_MAPPINGS = {
    # Mobject methods
    'get_center': {
        'new_name': 'get_center',
        'returns_array': True,  # Now returns numpy array, not Point
    },
    'get_width': {
        'new_name': 'width',
        'is_property': True,
    },
    'get_height': {
        'new_name': 'height', 
        'is_property': True,
    },
    'get_depth': {
        'new_name': 'depth',
        'is_property': True,
    },
    'set_submobjects': {
        'new_name': 'set_submobjects',
        'note': 'Parameter handling may differ'
    },
    'get_pieces': {
        'new_name': 'get_parts',
        'note': 'May not exist in all contexts'
    },
    'get_family': {
        'new_name': 'get_family',
        'note': 'Returns flat list now'
    },
    
    # Animation methods
    'get_all_mobjects': {
        'new_name': 'get_all_mobjects',
        'note': 'May need to be called differently'
    },
    
    # Color methods
    'set_color_by_gradient': {
        'new_name': 'set_color_by_gradient',
        'note': 'Signature may differ'
    },
    'set_colors_by_radial_gradient': {
        'new_name': 'set_color_by_radial_gradient',
    },
    
    # Scene methods
    'get_mobjects': {
        'new_name': 'mobjects',
        'is_property': True,
    },
    'get_moving_mobjects': {
        'new_name': 'moving_mobjects',
        'is_property': True,
    },
}

# Parameter changes for specific methods/classes
PARAMETER_CHANGES = {
    'Tex.__init__': {
        'removed': ['size'],
        'renamed': {},
        'added': [],
        'notes': 'Size should be handled with scale() after creation'
    },
    'MathTex.__init__': {
        'removed': ['size'],
        'renamed': {},
        'added': [],
        'notes': 'Size should be handled with scale() after creation'
    },
    'Text.__init__': {
        'removed': ['size'],
        'renamed': {'size': 'font_size'},
        'added': ['line_spacing', 'disable_ligatures'],
        'notes': 'Many parameters changed between TextMobject and Text'
    },
    'Circle.__init__': {
        'removed': [],
        'renamed': {},
        'added': [],
        'notes': 'Parameters mostly compatible'
    },
    'Transform.__init__': {
        'removed': [],
        'renamed': {},
        'added': ['replace_mobject_with_target_in_scene'],
        'notes': 'New parameter for scene handling'
    },
    'Scene.play': {
        'removed': [],
        'renamed': {},
        'added': ['subcaption', 'subcaption_duration', 'subcaption_offset'],
        'notes': 'New subcaption features'
    },
}

# APIs that were removed entirely
REMOVED_APIS = {
    'classes': [
        'ShowCreationThenDestruction',
        'ShowCreationThenFadeOut', 
        'CounterclockwiseTransform',
        'ClockwiseTransform',
        'ComplexPlane',  # Now part of NumberPlane
        'SmallDot',
    ],
    'methods': [
        'get_points_defining_boundary',
        'get_critical_point',
        'get_edge_center',
        'get_corner',
        'get_zenith',
        'get_nadir',
        'get_start_and_end',
        'point_from_proportion',
        'get_pieces',
        'get_z_index_reference_point',
    ],
    'attributes': [
        'LEFT_SIDE',
        'RIGHT_SIDE',
        'centered',
    ],
}

# APIs that exist but behave differently
BEHAVIOR_CHANGES = {
    'updaters': {
        'description': 'Updater API changed significantly',
        'changes': [
            'add_updater now requires dt parameter in function signature',
            'Some updater methods renamed or removed',
            'Time-based updaters work differently'
        ]
    },
    'coordinates': {
        'description': 'Coordinate system handling changed',
        'changes': [
            'Axes class has different defaults',
            'GraphScene coordinate methods changed',
            'NumberPlane has different parameters'
        ]
    },
    'tex_rendering': {
        'description': 'LaTeX rendering backend changed',
        'changes': [
            'Different default fonts',
            'Some LaTeX commands may not work',
            'Color handling in LaTeX differs'
        ]
    },
    'animations': {
        'description': 'Animation system refactored',
        'changes': [
            'Animation chaining syntax changed',
            'Some animations have different defaults',
            'Rate functions may behave differently'
        ]
    },
}

# Properties vs methods
PROPERTY_CHANGES = {
    # Things that were methods but are now properties
    'method_to_property': {
        'get_width': 'width',
        'get_height': 'height',
        'get_depth': 'depth',
        'get_center': 'center',  # Sometimes
        'get_mobjects': 'mobjects',
        'get_moving_mobjects': 'moving_mobjects',
    },
    # Things that were properties but are now methods
    'property_to_method': {
        # Less common direction
    },
    # Things that can be both
    'dual_access': {
        'center': 'Can be property or get_center() method',
    }
}

# Common error patterns and their fixes
ERROR_PATTERNS = {
    "name 'ShowCreation' is not defined": {
        'fix': "Replace ShowCreation with Create",
        'pattern': r'ShowCreation\(',
        'replacement': 'Create(',
    },
    "name 'TextMobject' is not defined": {
        'fix': "Replace TextMobject with Text",
        'pattern': r'TextMobject\(',
        'replacement': 'Text(',
    },
    "'Mobject' object has no attribute 'get_width'": {
        'fix': "Replace .get_width() with .width property",
        'pattern': r'\.get_width\(\)',
        'replacement': '.width',
    },
    "unexpected keyword argument 'size'": {
        'fix': "Remove size parameter and use .scale() instead",
        'pattern': r'(Tex|MathTex|TexMobject)\([^)]*size\s*=\s*[^,)]+',
        'replacement': 'Use .scale() after creation',
        'complex': True,
    },
    "No module named 'displayer'": {
        'fix': "Remove displayer import - not needed in ManimCE",
        'pattern': r'import displayer as disp\n',
        'replacement': '',
    },
}

# Import patterns to remove (common ManimGL-specific imports)
IMPORTS_TO_REMOVE = [
    'import displayer as disp',
    'from displayer import *',
    'import constants',
    'from constants import *',
    'import helpers',
    'from helpers import *',
]

# Helper functions
def get_class_mapping(manimgl_class: str) -> str:
    """Get the ManimCE equivalent of a ManimGL class."""
    return CLASS_MAPPINGS.get(manimgl_class, manimgl_class)

def is_removed_api(api_name: str, api_type: str = 'any') -> bool:
    """Check if an API has been removed in ManimCE."""
    if api_type == 'any':
        return (api_name in REMOVED_APIS.get('classes', []) or
                api_name in REMOVED_APIS.get('methods', []) or
                api_name in REMOVED_APIS.get('attributes', []))
    return api_name in REMOVED_APIS.get(api_type, [])

def get_method_info(method_name: str) -> dict:
    """Get information about method changes."""
    return METHOD_MAPPINGS.get(method_name, {})

def get_parameter_changes(class_method: str) -> dict:
    """Get parameter changes for a specific class/method."""
    return PARAMETER_CHANGES.get(class_method, {})

def should_be_property(method_name: str) -> bool:
    """Check if a method should be accessed as a property."""
    info = METHOD_MAPPINGS.get(method_name, {})
    return info.get('is_property', False)

def get_error_pattern_fix(error_message: str) -> dict:
    """Get fix information for a specific error pattern."""
    for pattern, fix_info in ERROR_PATTERNS.items():
        if pattern in error_message:
            return fix_info
    return {}