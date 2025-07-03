# ManimGL to ManimCE Conversion Guide: LLM-Optimized Reference

## 🚨 CRITICAL CONVERSION RULES - ALWAYS APPLY 🚨

### ⚡ RULE 1: Import Detection and Conversion
```python
### PATTERN: Import Conversion ###
# INPUT: from manimlib.imports import *
# OUTPUT: from manim import *

# INPUT: from manimlib import *
# OUTPUT: from manim import *

# INPUT: from manimlib.{anything} import {something}
# OUTPUT: from manim.{anything} import {something}

# INPUT: import manimlib
# OUTPUT: import manim

# LEGACY: from big_ol_pile_of_manim_imports import *  # Pre-2020 ManimCairo
# OUTPUT: from manim import *
```

### ⚡ RULE 2: Text Class Decision Tree
```
### DECISION TREE: Text Class Selection ###
START
  ↓
  Does string contain math/LaTeX? 
  ├─ NO → USE: Text()  [Pango rendering, faster, better Unicode]
  └─ YES → Does it contain ONLY math (no plain text)?
           ├─ YES → USE: MathTex()  [Wraps in $ $ automatically]
           └─ NO → Does it need custom LaTeX template?
                   ├─ YES → USE: Tex() or MathTex() with tex_template
                   └─ NO → USE: Tex()  [For mixed text/math]
```

### ⚡ RULE 3: CONFIG Dictionary Conversion (SILENT FAILURE IF NOT CONVERTED!)
```python
### PATTERN A: Custom Variables ###
# INPUT:
class MyScene(Scene):
    CONFIG = {"my_var": 5, "wait_time": 2}  # ← SILENTLY IGNORED IN CE!

# OUTPUT:
class MyScene(Scene):
    my_var = 5
    wait_time = 2

### PATTERN B: Parent Class Properties ###
# INPUT:
class RedCircle(Circle):
    CONFIG = {"color": RED, "fill_opacity": 0.5}  # ← SILENTLY IGNORED!

# OUTPUT:
class RedCircle(Circle):
    def __init__(self, color=RED, fill_opacity=0.5, **kwargs):
        super().__init__(color=color, fill_opacity=fill_opacity, **kwargs)

### PATTERN C: Camera Config ###
# INPUT:
class MyScene(Scene):
    CONFIG = {"camera_config": {"background_color": BLUE}}

# OUTPUT:
class MyScene(Scene):
    def construct(self):
        self.camera.background_color = BLUE  # Set in construct!
```

### ⚡ RULE 4: Transform Cleanup (LEAVES GHOST OBJECTS IF FORGOTTEN!)
```python
### MANDATORY PATTERN: Transform + Remove ###
# INPUT:
self.play(Transform(A, B))
# OR
self.play(ReplacementTransform(A, B))

# OUTPUT:
self.play(Transform(A, B))
self.remove(A)  # ← MANDATORY! NEVER FORGET THIS LINE!
```

### ⚡ RULE 5: Animation Method Updates
```python
### PATTERN: ApplyMethod → .animate ###
# INPUT: self.play(ApplyMethod(obj.shift, UP))
# OUTPUT: self.play(obj.animate.shift(UP))

# FOOTGUN: .animate interpolates start→end state
# If start == end visually, NO ANIMATION OCCURS!
# Example: obj.animate.rotate(PI) on a circle shows nothing
# FIX: Use explicit Rotate(obj, angle=PI) for guaranteed motion
```

---

## 📊 COMPREHENSIVE CLASS MAPPING TABLES

### 📝 TEXT AND LATEX CLASSES (MAJOR ARCHITECTURAL CHANGE)
```
╔═══════════════════════════╦═══════════════════════════╦═══════════════════════════╦═══════════════════════════╗
║ MANIMGL CLASS             ║ MANIMCE CLASS             ║ EXAMPLE INPUT             ║ CRITICAL NOTES            ║
╠═══════════════════════════╬═══════════════════════════╬═══════════════════════════╬═══════════════════════════╣
║ TextMobject("Hello")      ║ Text("Hello")             ║ Plain text only           ║ Cairo→Pango, faster       ║
║ TextMobject("$x^2$")      ║ Tex("$x^2$")              ║ Text with math            ║ Requires LaTeX            ║
║ TexMobject("x^2")         ║ MathTex("x^2")            ║ Pure math expression      ║ Auto-wraps in $ $         ║
║ TexText("Hello $x$")      ║ Tex("Hello $x$")          ║ Mixed text and math       ║ Text mode + math mode     ║
║ OldTex("\\sum")           ║ MathTex("\\sum")          ║ Old math syntax           ║ Legacy name               ║
║ OldTexText("text")        ║ Tex("text")               ║ Old mixed syntax          ║ Legacy name               ║
║ Title("Big Title")        ║ Text("Big Title",         ║ Title text                ║ No Title class in CE      ║
║                           ║      font_size=48)        ║                           ║                           ║
║ BulletedList("a", "b")    ║ VGroup(*[Text("• " + s)   ║ Bulleted lists            ║ Manual construction       ║
║                           ║         for s in items])  ║                           ║ required                  ║
╚═══════════════════════════╩═══════════════════════════╩═══════════════════════════╩═══════════════════════════╝

FOOTGUN: NameError: name 'TextMobject' is not defined
CAUSE: Using old class names in newer ManimGL or any ManimCE
```

### 🎬 ANIMATION CLASSES
```
╔═══════════════════════════════════╦═══════════════════════════════════╦═══════════════════════════════════╗
║ MANIMGL ANIMATION                 ║ MANIMCE ANIMATION                 ║ NOTES & FOOTGUNS                  ║
╠═══════════════════════════════════╬═══════════════════════════════════╬═══════════════════════════════════╣
║ ShowCreation                      ║ Create                            ║ ⭐ Most common conversion         ║
║ ShowPartial                       ║ Create                            ║ Older alias for ShowCreation      ║
║ ShowCreationThenFadeOut           ║ Succession(Create, FadeOut)       ║ No direct equivalent              ║
║ ShowCreationThenDestruction       ║ Succession(Create, Uncreate)      ║ No direct equivalent              ║
║ ShowCreationThenDestructionAround ║ No direct equivalent              ║ Custom implementation needed      ║
║ DrawBorderThenFill                ║ DrawBorderThenFill                ║ ✓ Same name                       ║
║ Write                             ║ Write                             ║ ✓ Same but CE slower by default   ║
║ FadeIn                            ║ FadeIn                            ║ ✓ Same but opacity curve differs  ║
║ FadeOut                           ║ FadeOut                           ║ ✓ Same name                       ║
║ FadeInFromDown                    ║ FadeIn(shift=DOWN)                ║ Composed in CE                    ║
║ FadeOutAndShift(direction)        ║ FadeOut(shift=direction)          ║ Composed in CE                    ║
║ FadeInFromLarge                   ║ FadeIn(scale=1.5)                 ║ Parameter-based in CE             ║
║ Transform                         ║ Transform                         ║ ⚠️ CE doesn't auto-remove A       ║
║ ReplacementTransform              ║ Transform                         ║ ⚠️ MUST self.remove(A) after!    ║
║ TransformMatchingTex              ║ TransformMatchingShapes           ║ More refined mismatch handling    ║
║ TransformMatchingParts            ║ TransformMatchingShapes           ║ Unified in CE                     ║
║ ApplyMethod                       ║ .animate                          ║ ⭐ Major syntax change             ║
║ Rotating                          ║ Rotate                            ║ Simple rename                     ║
║ Rotation                          ║ Rotate                            ║ Simple rename                     ║
╚═══════════════════════════════════╩═══════════════════════════════════╩═══════════════════════════════════╝
```

---

## 🔧 METHOD AND PROPERTY CONVERSIONS

### 🎨 COLOR AND GRADIENT METHODS (DEFAULT BEHAVIOR CHANGES)
```python
### COLOR GRADIENT CONVERSION ###
# INPUT: obj.set_color_by_gradient(RED, BLUE)
# OUTPUT: obj.set_color((RED, BLUE))

# INPUT: obj.set_submobject_colors_by_gradient(RED, BLUE)
# OUTPUT: obj.set_color((RED, BLUE))

# INPUT: obj.set_colors_by_radial_gradient(inner, outer)
# OUTPUT: 
obj.set_color((inner, outer))
obj.set_sheen_direction(OUT)  # Must set direction explicitly!

### STYLE METHOD SEPARATION ###
# INPUT: obj.set_style(fill_color=BLUE, fill_opacity=0.5, stroke_width=2)
# OUTPUT:
obj.set_fill(color=BLUE, opacity=0.5)
obj.set_stroke(width=2)

# FOOTGUN: Gradient directions may differ by default!
# GL diagonal gradient might appear horizontal in CE
# FIX: Always set sheen_direction explicitly
```

### 📍 POSITIONING METHODS (GETTER SYNTAX CHANGE)
```python
### GETTER METHOD CONVERSION ###
# INPUT: obj.get_center  # ← No parentheses in GL!
# OUTPUT: obj.get_center()  # ← MUST add parentheses!

# Same for ALL getters:
# get_top → get_top()
# get_bottom → get_bottom()
# get_left → get_left()
# get_right → get_right()
# get_width → get_width()
# get_height → get_height()
```

### 📊 GRAPH AND AXES METHODS
```python
### AXES METHOD RENAMING ###
# INPUT: axes.get_graph(lambda x: x**2)
# OUTPUT: axes.plot(lambda x: x**2)

# INPUT: axes.get_parametric_curve(lambda t: [t, t**2])
# OUTPUT: axes.plot_parametric_curve(lambda t: [t, t**2])

# INPUT: graph.get_point_from_function(x_val)
# OUTPUT: axes.input_to_graph_point(graph, x_val)  # Moved to axes!

# INPUT: ParametricCurve
# OUTPUT: ParametricFunction  # Class renamed
```

### 🔄 UPDATER PATTERNS AND PERFORMANCE FOOTGUNS
```python
### UPDATER SYNTAX ###
# Both versions support:
obj.add_updater(lambda m: ...)
always_redraw(lambda: ...)

### CE-SPECIFIC: .become() method ###
# Powerful but dangerous with DecimalNumber!
# WRONG (PERFORMANCE DECAY):
decimal.add_updater(lambda d: d.become(DecimalNumber(tracker.get_value())))
# ↑ Points grow unboundedly each frame!

# CORRECT:
decimal.add_updater(lambda d: d.set_value(tracker.get_value()))
```

---

## ⚠️ METHODS TO DELETE - DO NOT CONVERT

### 🚫 INTERACTIVE METHODS (NO CE EQUIVALENT)
```python
# DELETE: self.embed()  # Opens IPython shell in GL
# DELETE: self.embed(close_scene_on_exit=False)
# DELETE: checkpoint_paste()  # Grant's custom editor integration
# DELETE: self.interact()
# DELETE: self.pose_at_arg()
# DELETE: self.get_external_args()  # Workflow specific

# These are GL's interactive development features
# CE uses Jupyter notebooks for interactivity instead
```

### 🚫 PI CREATURE METHODS (3B1B SPECIFIC)
```python
# DELETE ALL:
self.play_student_changes()
self.teacher_says()
self.student_says()
self.change_students()
self.pi_creature_says()
self.play_pi_creature_scene()
# These are custom to Grant's videos
```

---

## 💡 COMMON CONVERSION PATTERNS

### 📐 PATTERN: Text with set_color_by_tex
```python
### INPUT PATTERN ###
formula = TextMobject("The formula ", "$E=mc^2$", " changed physics")
formula.set_color_by_tex("E=mc^2", YELLOW)  # GL string matching

### OUTPUT PATTERN ###
formula = Tex("The formula ", "$E=mc^2$", " changed physics")
formula[1].set_color(YELLOW)  # CE uses indexing!
```

### 🔢 PATTERN: Number Animation Methods
```python
### INPUT PATTERN ###
number = DecimalNumber(0)
self.play(ChangingDecimal(number, lambda a: a.set_value(100)))

### OUTPUT PATTERN ###
number = DecimalNumber(0)
self.play(number.animate.set_value(100))
# OR with tracker:
tracker = ValueTracker(0)
number.add_updater(lambda n: n.set_value(tracker.get_value()))
self.play(tracker.animate.set_value(100))
```

### 📹 PATTERN: Camera Frame Access
```python
### GL PATTERNS ###
self.camera_frame  # Sometimes used
self.camera.frame  # Standard

### CE PATTERN ###
self.camera.frame  # Only this works

# 3D Camera:
# GL: class uses SpecialThreeDScene
# CE: class uses ThreeDScene
```

---

## ❌ ERROR PATTERNS TO DETECT AND FIX

### 🐛 ERROR: "No scenes inside that module"
```python
# CAUSE: Python environment mixup - using wrong manim executable
# Running manimgl on CE code or vice versa

# FIX: Use explicit module execution
python -m manim file.py SceneName  # Forces correct library
```

### 🐛 ERROR: LaTeX Error - standalone.cls not found
```python
# CAUSE: Incomplete LaTeX installation
# FIX: Install via package manager:
# - MiKTeX: Use MiKTeX Console
# - TeX Live: tlmgr install standalone
```

### 🐛 ERROR: Silent CONFIG Failure
```python
### WRONG (SILENT FAILURE!) ###
class MyCircle(Circle):
    CONFIG = {"color": RED}  # ← Circle stays white!

### CORRECT ###
class MyCircle(Circle):
    def __init__(self, **kwargs):
        super().__init__(color=RED, **kwargs)
```

### 🐛 ERROR: Animate Ambiguity
```python
### WRONG (NO VISIBLE ANIMATION) ###
# Circle rotated 360° looks identical!
self.play(circle.animate.rotate(TAU))

### CORRECT ###
self.play(Rotate(circle, angle=TAU))
```

---

## 📋 ARCHITECTURE & PERFORMANCE NOTES

### 🏗️ FUNDAMENTAL ARCHITECTURE DIFFERENCES
```
MANIMGL:
- OpenGL renderer (GPU accelerated)
- ~5x faster than ManimCE
- Real-time preview with interactive controls
- Command: manimgl file.py Scene
- Interactive: self.embed() for IPython terminal
- Window controls: s (pan), z (zoom), d (rotate)

MANIMCE:
- Cairo renderer (CPU) by default
- Experimental OpenGL (still slower than GL)
- Batch rendering workflow
- Command: manim file.py Scene -pql
- Quality flags: -ql (480p), -qm (720p), -qh (1080p), -qk (4K)
- Interactive: Jupyter notebook integration
```

### 🎨 COLOR SYSTEM CHANGES (CE v0.18.0+)
```python
# CE has ManimColor class with expanded palettes:
from manim.utils.color import XKCD  # Hundreds of colors

# GL: Limited predefined colors in constants.py
# CE: AS2700, BS381, DVIPSNAMES, SVGNAMES, XKCD, X11

# Breaking change in CE:
# OLD: ManimColor.from_hex(hex="...")
# NEW: ManimColor.from_hex(hex_str="...")
```

### 📁 CONFIGURATION FILE FORMATS
```yaml
# ManimGL: custom_config.yml (YAML)
camera_config:
  background_color: "#000000"
  pixel_height: 1080
  pixel_width: 1920
```

```ini
# ManimCE: manim.cfg (INI format)
[CLI]
quality = medium_quality
preview = True

[camera]
background_color = BLACK
frame_height = 8.0
```

---

## 📋 COMMAND LINE CONVERSION

```bash
### COMMAND MAPPING TABLE ###
manimgl file.py Scene      → manim file.py Scene
manimgl file.py Scene -w   → manim file.py Scene -p      # Write/preview
manimgl file.py Scene -s   → manim file.py Scene -ps     # Save last frame
manimgl file.py Scene -l   → manim file.py Scene -pql    # Low quality
manimgl file.py Scene -m   → manim file.py Scene -pqm    # Medium quality
manimgl file.py Scene -h   → manim file.py Scene -pqh    # High quality
manimgl file.py -a         → manim file.py -a            # All scenes

# CE-specific flags:
--format=gif  # Output as GIF
--format=png  # Output as PNG sequence
-n 0,10       # Render frames 0-10 only
```

---

## ✅ POST-TRANSLATION AUDIT CHECKLIST

### Visual Style Verification:
- [ ] Colors and opacity correct (CONFIG conversion)
- [ ] Gradients present with correct orientation (sheen_direction)
- [ ] Text rendering matches (correct class choice)

### Animation Verification:
- [ ] Smooth motion without jumps (.animate footguns)
- [ ] Timing preserved (run_time, rate_func)
- [ ] No ghost objects (Transform cleanup)

### Dynamic Elements:
- [ ] Updaters work without performance decay
- [ ] ValueTrackers update correctly
- [ ] No growing point counts (DecimalNumber.become)

### Code Quality:
- [ ] All workflow artifacts removed (embed, checkpoint_paste)
- [ ] Modern CE idioms used
- [ ] No deprecated patterns remaining

---

## 🚨 VERSION-SPECIFIC BREAKING CHANGES

### ManimCE Breaking Changes by Version:
- **v0.2.0**: CONFIG dictionaries removed
- **v0.3.0**: Text → Pango rendering (Cairo → Pango)
- **v0.18.0**: Color system rewrite (ManimColor class)
- **v0.19.0**: Point3D typing, Code mobject rewrite

### ManimGL Breaking Changes:
- **Undocumented** - GL explicitly doesn't track breaking changes
- Version pinning critical for GL stability

---

## 🛑 WHEN NOT TO CONVERT

### Do NOT attempt conversion if code contains:
1. **Heavy OpenGL customization** - Shaders, direct GL calls
2. **Performance-critical rendering** - CE is ~5x slower
3. **Live camera interaction** - s/z/d keys during preview
4. **Custom Pi creatures** - Grant's specific animations
5. **Extensive embed() usage** - Interactive development workflow

---

## 📝 CRITICAL REMINDERS

1. **CONFIG = {...}** → ALWAYS convert or styling breaks silently
2. **Transform/ReplacementTransform** → ALWAYS add self.remove()
3. **TextMobject** → Choose Text/Tex/MathTex based on content
4. **ApplyMethod** → ALWAYS use .animate syntax
5. **get_center** → ALWAYS add parentheses: get_center()
6. **ShowCreation** → ALWAYS use Create
7. **self.embed()** → ALWAYS delete
8. **DecimalNumber + become()** → Use set_value() instead

This guide preserves all footguns, edge cases, and architectural differences for accurate ManimGL→ManimCE conversion.