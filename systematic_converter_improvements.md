# Systematic Converter Coverage Improvements

## Evidence Summary

Based on analysis of the brachistochrone video pipeline run:
- **19 files** contain `.split()` calls on Text objects
- **3 files** use `OldTexText(list(word))` pattern  
- **10 files** use `rush_into`/`rush_from` functions
- **22 files** inherit from custom scene base classes like `CycloidScene`

## Concrete Solutions

### 1. OldTexText(list(word)) → Text("".join(word))

**Problem**: OldTexText accepts list arguments, but Text in ManimCE only accepts strings.

**Code Pattern Examples**:
```python
# Pattern 1: OldTexText(list(word))
word_mob = OldTexText(list(word))  # Creates individual letter mobjects

# Pattern 2: OldTexText(["with ", "Steven Strogatz"])  
new_text = OldTexText(["with ", "Steven Strogatz"])
```

**AST Converter Solution** (already added):
```python
# In _fix_class_instantiation method, case 6:
if class_name == 'OldTexText' and node.args:
    first_arg = node.args[0]
    # Case 1: OldTexText(list(word)) → Text(word)
    if (isinstance(first_arg, ast.Call) and 
        isinstance(first_arg.func, ast.Name) and 
        first_arg.func.id == 'list' and 
        len(first_arg.args) == 1):
        node.func.id = 'Text'
        node.args[0] = first_arg.args[0]  # Remove list() wrapper
    # Case 2: OldTexText(["a", "b"]) → Text("ab")
    elif isinstance(first_arg, ast.List):
        if all(isinstance(elt, ast.Constant) for elt in first_arg.elts):
            joined_text = ''.join(elt.value for elt in first_arg.elts)
            node.func.id = 'Text'
            node.args[0] = ast.Constant(value=joined_text)
```

### 2. .split() on Text Objects

**Problem**: ManimGL Text objects have `.split()` method to get individual letters, but ManimCE Text objects don't.

**Code Pattern Examples**:
```python
self.end_letters = end_word.split()  # Get list of letter mobjects
for part in new_text.split():         # Iterate over letters
    # animate each letter
```

**AST Converter Solution** (needs to be added):
```python
# In _fix_method_calls method, add before check #1:
if method_name == 'split' and len(node.args) == 0:
    # Text objects don't have split() in ManimCE
    # Replace text.split() with [text]
    return ast.List(
        elts=[node.func.value],
        ctx=ast.Load()
    )
```

### 3. rush_into/rush_from Functions

**Problem**: These are ManimGL-specific rate functions not available in ManimCE.

**Code Pattern Examples**:
```python
angle = -rush_into(alpha)*np.pi/2
position = interpolate(start, end, rush_from(alpha))
```

**Solution**: Add to function_conversions dictionary:
```python
# In __init__ method:
self.function_conversions = {
    'get_norm': 'np.linalg.norm',
    'rush_into': 'smooth',      # or 'rush_into' with custom implementation
    'rush_from': 'smooth',      # or 'rush_from' with custom implementation
}
```

**Alternative**: Add custom implementations in _add_missing_methods:
```python
def _add_rush_functions(self, tree):
    """Add rush_into/rush_from if used but not defined."""
    # Check if functions are used
    used_funcs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ['rush_into', 'rush_from']:
                used_funcs.add(node.func.id)
    
    if used_funcs:
        # Add function definitions at module level
        rush_defs = []
        if 'rush_into' in used_funcs:
            rush_defs.append(ast.parse('''
def rush_into(t, inflection=10.0):
    """Smooth acceleration from 0 to 1."""
    return 2 * smooth(t / 2, inflection)
''').body[0])
        
        if 'rush_from' in used_funcs:
            rush_defs.append(ast.parse('''
def rush_from(t, inflection=10.0):
    """Smooth deceleration from 0 to 1."""  
    return 2 * smooth(t / 2 + 0.5, inflection) - 1
''').body[0])
        
        # Insert after imports
        for i, node in enumerate(tree.body):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                tree.body[i:i] = rush_defs
                break
```

### 4. Custom Scene Base Classes

**Problem**: Files inherit from custom scene classes (CycloidScene, PathSlidingScene, etc.) that may not be defined or may use ManimGL-specific features.

**Code Pattern Examples**:
```python
class SlidingObject(CycloidScene):
    # Uses custom scene functionality
    
class ShowDiscretePath(MultilayeredScene):
    # Uses layered scene features
```

**Solution** (already implemented in _fix_custom_scene_classes):
```python
def _fix_custom_scene_classes(self, code: str) -> Tuple[str, List[str]]:
    """Handle custom scene base classes like CycloidScene."""
    custom_scenes = [
        'CycloidScene', 'PathSlidingScene', 'MultilayeredScene',
        'PhotonScene', 'ThetaTGraph', 'VideoLayout'
    ]
    
    # If inheriting from custom scene not defined in file
    if parent_class in custom_scenes:
        if f'class {parent_class}' not in code:
            # Change inheritance to Scene
            fixed_line = f'class {class_name}(Scene):'
```

## Implementation Priority

1. **`.split()` fix** - Affects 19 files, simple to implement
2. **OldTexText list handling** - Already implemented, affects 3 files
3. **rush functions** - Affects 10 files, moderate complexity
4. **Custom scene classes** - Already handled, affects 22 files

## Testing

Test with these specific scenes from brachistochrone:
- `BrachistochroneWordSliding.py` - Uses OldTexText(list(word)) and .split()
- `Intro.py` - Uses OldTexText(["with ", "Steven Strogatz"]) and .split()
- `MultilayeredGlass.py` - Uses rush_into function
- `SlidingObject.py` - Inherits from CycloidScene

## Expected Impact

These improvements should reduce "Syntax error: invalid syntax at line 1" errors significantly and increase the AST converter success rate from ~10% to ~50%+ for the brachistochrone video.