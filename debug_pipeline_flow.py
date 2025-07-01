#!/usr/bin/env python3
"""Debug the actual pipeline flow for inventing-math."""

from pathlib import Path

def debug_inventing_math_flow():
    """Debug the exact flow for the inventing-math video."""
    
    video_dir = Path("/Users/timholdsworth/code/3b1b_dataset/outputs/2015/inventing-math")
    
    # Check what's in the cleaned scenes
    cleaned_dir = video_dir / "cleaned_scenes"
    if cleaned_dir.exists():
        print("=== Cleaned Scenes ===")
        for file in sorted(cleaned_dir.glob("*.py")):
            print(f"Found: {file.name}")
            
    # Check what's in the validated snippets  
    snippets_dir = video_dir / "validated_snippets"
    if snippets_dir.exists():
        print(f"\n=== Validated Snippets ===")
        for file in sorted(snippets_dir.glob("*.py")):
            print(f"Found: {file.name}")
            
        # Check a specific file for the divergent_sum function
        dist_file = snippets_dir / "DistanceIsAFunction.py"
        if dist_file.exists():
            print(f"\n=== DistanceIsAFunction.py snippet ===")
            content = dist_file.read_text()
            
            # Look for the divergent_sum function
            for i, line in enumerate(content.split('\n'), 1):
                if 'def divergent_sum' in line:
                    print(f"Line {i}: {line}")
                    # Get the next line too
                    lines = content.split('\n')
                    if i < len(lines):
                        print(f"Line {i+1}: {lines[i]}")
                    break
                    
            # Look for the DIVERGENT_SUM_TEXT constant
            for i, line in enumerate(content.split('\n'), 1):
                if 'DIVERGENT_SUM_TEXT' in line and '=' in line:
                    print(f"Line {i}: {line}")
                    break
    
    # Check the monolithic file
    monolith_file = video_dir / "monolith_manimce.py"
    if monolith_file.exists():
        print(f"\n=== Monolithic file ===")
        content = monolith_file.read_text()
        
        # Look for the divergent_sum function
        for i, line in enumerate(content.split('\n'), 1):
            if 'def divergent_sum' in line:
                print(f"Line {i}: {line}")
                # Get the next line too
                lines = content.split('\n')
                if i < len(lines):
                    print(f"Line {i+1}: {lines[i]}")
                break

if __name__ == "__main__":
    debug_inventing_math_flow()