# ManimGL to ManimCE Conversion Guide: Consolidated Technical Reference

## Introduction
This document serves as an authoritative technical guide for translating Python animation scripts from ManimGL (3Blue1Brown's version) to ManimCE (Community Edition). It provides a comprehensive resource for both LLM training and human developers performing quality assurance on the translation process.

## Section 1: Foundational Architecture & Import Structure

### 1.1 Import Statement Conversion
The fundamental identifier distinguishing versions is the module name:
- **ManimGL**: `manimlib`
- **ManimCE**: `manim`

```python
# ManimGL imports:
from manimlib import *
from manimlib import Scene, Circle, Square
from manimlib.imports import *  # Legacy pattern

# ManimCE equivalent:
from manim import *
from manim import Scene, Circle, Square
```

**Version Detection Pattern:**
```python
try:
    from manimlib import Scene
    USING_MANIMGL = True
except ImportError:
    from manim import Scene
    USING_MANIMGL = False
```

### 1.2 The CONFIG Paradigm Shift
ManimGL uses a class-level `CONFIG` dictionary for default parameters. ManimCE deprecated this in v0.2.0, requiring explicit initialization.

**Pattern 1: New Class Attributes**
```python
# ManimGL:
class MyScene(Scene):
    CONFIG = {"my_variable": 5}

# ManimCE:
class MyScene(Scene):
    my_variable = 5
```

**Pattern 2: Overriding Parent Attributes**
```python
# ManimGL:
class RedCircle(Circle):
    CONFIG = {"color": RED, "fill_opacity": 0.5}

# ManimCE:
class RedCircle(Circle):
    def __init__(self, color=RED, fill_opacity=0.5, **kwargs):
        super().__init__(color=color, fill_opacity=fill_opacity, **kwargs)
```

### 1.3 Configuration Files
- **ManimGL**: Uses `custom_config.yml` (YAML format)
- **ManimCE**: Uses `manim.cfg` (INI-style configparser format)

## Section 2: Mobject API Mappings

### 2.1 Text and LaTeX Classes
The most significant API change involves text rendering:

| ManimGL Class | ManimCE Class | Use Case |
|---------------|---------------|----------|
| `TextMobject` | `Text` | Plain text (uses Pango, not LaTeX) |
| `TextMobject` | `Tex` | Mixed text/math with LaTeX |
| `TexMobject` | `MathTex` | Pure mathematical expressions |
| `TexText` | `Tex` | Mixed content |

**Decision Heuristics:**
- No LaTeX/math → `Text`
- Mixed text and math → `Tex`
- Pure math → `MathTex`

### 2.2 Styling and Properties
ManimGL's bundled `set_style()` method is replaced with discrete methods in ManimCE:

```python
# ManimGL:
mobj.set_style(fill_color=BLUE, fill_opacity=0.5, stroke_width=2)

# ManimCE:
mobj.set_fill(color=BLUE, opacity=0.5)
mobj.set_stroke(width=2)
# Or in constructor:
Square(fill_color=BLUE, fill_opacity=0.5, stroke_width=2)
```

### 2.3 Color and Gradients
```python
# ManimGL:
text.set_color_by_gradient(RED, BLUE)
text.set_submobject_colors_by_gradient(RED, BLUE)

# ManimCE:
text = Text("...", color=(RED, BLUE))
# or
text.set_color((RED, BLUE))
```

## Section 3: Animation API

### 3.1 Animation Class Mappings

| ManimGL | ManimCE | Notes |
|---------|---------|-------|
| `ShowCreation` | `Create` | Direct replacement |
| `ShowPartial` | `Create` | Older alias |
| `TransformMatchingTex` | `TransformMatchingShapes` | More refined behavior |
| `FadeOutAndShift` | `FadeOut(shift=...)` | Composed in CE |
| `ApplyMethod` | `.animate` syntax | Modern replacement |
| `Rotating` | `Rotate` | Simple rename |

### 3.2 The .animate Syntax
```python
# ManimGL (both supported):
self.play(ApplyMethod(mobj.shift, UP))
self.play(mobj.animate.shift(UP))

# ManimCE (preferred):
self.play(mobj.animate.shift(UP))
```

**Warning**: `.animate` interpolates between start/end states. For rotations where start/end are identical, use explicit `Rotate(mobj, angle=PI)`.

### 3.3 Transform Behavior
Critical difference: ManimCE's `Transform` doesn't auto-remove the source object:

```python
# ManimGL:
self.play(ReplacementTransform(circle, square))

# ManimCE:
self.play(Transform(circle, square))
self.remove(circle)  # Required!
```

## Section 4: Scene Structure & Special Features

### 4.1 Camera and 3D Scenes
```python
# ManimGL:
self.camera.frame.set_height(10)

# ManimCE:
self.camera.frame_height = 10
```

For 3D scenes, both use `ThreeDScene`, but camera controls differ.

### 4.2 Updaters and ValueTracker
Core concepts remain similar:
- Use `.add_updater(lambda m: ...)` in both
- `always_redraw()` available in both
- ManimCE adds `.become()` method for dynamic updates

**Performance Warning**: Avoid `DecimalNumber.become()` in updaters; use `set_value()` instead.

### 4.3 Non-Translatable Elements
Remove these ManimGL-specific features:
- `self.embed()` - Interactive IPython shell
- `checkpoint_paste()` - External tooling artifact
- Live camera interaction references

## Section 5: Command Line Interface

```bash
# ManimGL:
manimgl file.py SceneName -w -o -s

# ManimCE:
manim file.py SceneName -pql  # Preview, quality low
manim file.py SceneName -pqh  # Preview, quality high
```

Quality flags: `-ql` (480p), `-qm` (720p), `-qh` (1080p), `-qk` (4K)

## Section 6: Common Errors & Solutions

### 6.1 Error Mapping
| Error | Cause | Solution |
|-------|-------|----------|
| `NameError: name 'TextMobject' is not defined` | Deprecated class | Use `Text`, `Tex`, or `MathTex` |
| `AttributeError: 'Square' object has no attribute 'set_style'` | Removed method | Use individual setters |
| "No scenes inside that module" | Environment mixup | Use `python -m manim` |
| `LaTeX Error: File 'standalone.cls' not found` | Missing LaTeX package | Install via TeX package manager |

### 6.2 Silent Failures
1. **CONFIG dictionary** - Silently ignored, causing default styling
2. **Incorrect .animate usage** - May produce no motion
3. **Missing object removal after Transform** - Leaves ghost objects
4. **Gradient direction changes** - May appear different without explicit `sheen_direction`

## Section 7: Architecture & Performance

### 7.1 Rendering Architecture
- **ManimGL**: OpenGL-based GPU rendering, ~5x faster
- **ManimCE**: Cairo-based CPU rendering (default), experimental OpenGL

### 7.2 Breaking Changes by Version
**ManimCE:**
- v0.2.0: CONFIG removal
- v0.3.0: Text → Pango rendering
- v0.18.0: Color system rewrite (`ManimColor` class)
- v0.19.0: Point3D type changes

**ManimGL**: Breaking changes undocumented; version pinning critical

## Section 8: Migration Checklist

### 8.1 Systematic Conversion Steps
1. ✓ Update imports: `manimlib` → `manim`
2. ✓ Convert text classes per heuristics
3. ✓ Replace animation classes
4. ✓ Convert CONFIG to constructor params
5. ✓ Add explicit `self.remove()` after transforms
6. ✓ Update `.animate` syntax
7. ✓ Remove workflow artifacts (`embed()`, etc.)
8. ✓ Update CLI commands

### 8.2 Visual Validation Checklist
- [ ] Colors and opacity correct
- [ ] Gradients present with correct orientation
- [ ] Text/equations render properly
- [ ] Animations smooth with correct timing
- [ ] Dynamic elements update correctly
- [ ] No performance degradation

## Section 9: Complete Example

```python
# ManimGL:
from manimlib.imports import *

class Example(Scene):
    CONFIG = {"wait_time": 2}
    
    def construct(self):
        title = TextMobject("Example")
        equation = TexMobject("E = mc^2")
        
        self.play(ShowCreation(title))
        self.play(ReplacementTransform(title, equation))
        self.play(ApplyMethod(equation.shift, UP))
        self.embed()

# ManimCE:
from manim import *

class Example(Scene):
    wait_time = 2
    
    def construct(self):
        title = Text("Example")
        equation = MathTex("E = mc^2")
        
        self.play(Create(title))
        self.play(Transform(title, equation))
        self.remove(title)
        self.play(equation.animate.shift(UP))
        # Remove embed() - not translatable
```

## Conclusion
This guide consolidates all critical information for ManimGL→ManimCE conversion. Key principles:
1. Systematic class/method replacement
2. Architectural awareness (CONFIG, rendering)
3. Visual validation of output
4. Removal of non-translatable elements

The translation process requires both syntactic conversion and semantic understanding, particularly for text rendering decisions and animation behavior differences.