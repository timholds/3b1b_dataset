"""
Improved Claude prompts for the 3Blue1Brown dataset pipeline.
These prompts use structured templates, few-shot examples, and validation steps.
"""

# Video Matching Prompt Template
VIDEO_MATCHING_PROMPT = """You are helping match 3Blue1Brown videos to their Manim source code.

## Example of a successful match:

### Input:
Video: "Binary Counting Introduction"
Transcript: "Let's talk about binary numbers. When we count in binary, we use only 0s and 1s..."
Year: 2015

### Process:
1. Searched for "binary", "counting", "decimal" in data/videos/_2015/
2. Found BinaryCountingScene.py containing "class BinaryCountingScene" 
3. Verified the class creates binary number animations matching the transcript

### Output (saved to file):
{
    "primary_files": ["BinaryCountingScene.py"],
    "supporting_files": ["helpers/binary_utils.py"],
    "confidence_score": 0.95,
    "evidence": [
        "Found class BinaryCountingScene that creates binary number animations",
        "Transcript mentions 'binary counting' which matches CountingInBinary class",
        "Animation methods like show_binary_number() align with video content"
    ],
    "search_queries_used": ["binary", "counting", "decimal", "base-2"],
    "video_id": "abc123",
    "status": "matched"
}

## Your Task:

Video Information:
- Title: {title}
- YouTube ID: {video_id}
- Year: {year}
- Caption Directory: {caption_dir}

Transcript:
{transcript[:3000]}...

SEARCH STRATEGY:
1. Extract 3-5 key technical terms from the transcript
2. Search in data/videos/_{year}/ for files containing these terms
3. Look for Scene classes that would generate the described visuals
4. Check file names similar to: {expected_filename}

VALIDATION STEPS:
Before saving your result:
1. Verify the primary files contain Scene classes
2. Confirm the animations described match the transcript
3. Check that confidence score reflects match quality

OUTPUT REQUIREMENTS:
- Save to: {output_path}
- Create parent directory if needed
- Write valid JSON matching the example format
- Set status="low_confidence" if confidence < 0.5
- Set status="no_transcript" if transcript is empty

IMPORTANT: Use the Write tool to save the file. Do not just output JSON."""


# Code Cleaning Prompt Template
CODE_CLEANING_PROMPT = """You are cleaning and inlining Manim code for the 3Blue1Brown dataset.

## Example of successful cleaning:

### Input files:
main_scene.py:
```python
from helpers import calculate_angle
class MyScene(Scene):
    def construct(self):
        angle = calculate_angle(0, 1)
```

helpers.py:
```python
def calculate_angle(x, y):
    return np.arctan2(y, x)
```

### Output (single self-contained file):
```python
# Video: Example Video
# YouTube ID: xyz789
# Generated from: main_scene.py, helpers.py
# Cleaned on: 2024-12-30T10:00:00
# Manim version: ManimGL (original 3b1b version)

from manimlib import *
import numpy as np

# Inlined from helpers.py
def calculate_angle(x, y):
    return np.arctan2(y, x)

class MyScene(Scene):
    def construct(self):
        angle = calculate_angle(0, 1)
```

## Your Task:

Video: {video_id} ({caption_dir})
Year: {year}
Files to process:
- Primary: {primary_files}
- Supporting: {supporting_files}

CRITICAL REQUIREMENTS:
1. PRESERVE ManimGL - Do NOT convert to ManimCE
2. Keep "from manimlib import *" or "from manim_imports_ext import *" exactly as is
3. Inline all local imports while keeping external imports
4. Each function/class on its own line - NEVER merge statements
5. Validate Python syntax before saving

VALIDATION CHECKLIST:
□ All imports from supporting files are inlined
□ No local import statements remain
□ Original ManimGL syntax preserved
□ Code is syntactically valid Python
□ Header comment block included

Save cleaned code to: {output_path}

If files are missing or code is incomplete, create a file explaining what went wrong."""


# Error Fixing Prompt Template  
ERROR_FIXING_PROMPT = """Fix this ManimCE scene rendering error.

## Common Fix Patterns:

### Pattern 1: Missing imports
Error: "name 'reduce' is not defined"
Fix: Add "from functools import reduce"

### Pattern 2: Color constants
Error: "name 'BLUE_E' is not defined" 
Fix: Add color definition or import from manimce_constants_helpers

### Pattern 3: Animation names
Error: "ShowCreation not found"
Fix: Change to "Create" (ManimCE equivalent)

## Current Error:

Scene: {scene_name}
Error: {error_message}
Attempt: {attempt_number}

## Code to fix:
```python
{code}
```

## Fix Strategy for Attempt {attempt_number}:
{attempt_specific_strategy}

REQUIREMENTS:
1. Edit file at: {file_path}
2. Make MINIMAL changes to fix the error
3. Add comment explaining the fix
4. Preserve all functionality
5. Test that your fix is syntactically valid

VALIDATION:
After making changes, verify:
- The specific error line is addressed
- No new syntax errors introduced
- Original scene logic preserved"""


# Scene Dependency Cleaning Template
SCENE_CLEANING_PROMPT = """Clean and inline code for a single Manim scene.

## Successful dependency resolution example:

### Input:
Scene uses: Face(), SpeechBubble(), interpolate()
Unresolved: ['Face', 'SpeechBubble', 'interpolate']
Available files: ['characters.py', 'helpers.py']

### Process:
1. Found Face and SpeechBubble classes in characters.py
2. Found interpolate function in helpers.py
3. Inlined all dependencies before the scene class

### Output structure:
```python
# Scene: ExampleScene
# From Video: video_id
# Dependencies inlined from: characters.py, helpers.py

from manimlib import *

# From characters.py
class Face(VGroup):
    ...

# From helpers.py  
def interpolate(start, end, alpha):
    ...

class ExampleScene(Scene):
    # Original scene code
```

## Your Task:

Scene: {scene_name}
Video: {video_id} ({caption_dir})
Dependencies provided: {dependencies_count} items
Unresolved references: {unresolved_refs}

PROCESS:
1. Use the pre-extracted dependencies provided
2. ONLY search files if unresolved references remain
3. Place all dependencies BEFORE the scene class
4. Ensure no duplicate definitions

VALIDATION:
□ All functions/classes used are defined
□ Dependencies appear before usage
□ No duplicate definitions
□ Original ManimGL code preserved
□ Single self-contained file created

Save to: {output_path}"""


def format_prompt(template: str, **kwargs) -> str:
    """Format a prompt template with the given parameters."""
    return template.format(**kwargs)