#!/usr/bin/env python3
"""Test conversion on a single file."""

import sys
from pathlib import Path

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

from convert_manimgl_to_manimce import ManimConverter

def test_single_file(input_file: str):
    """Test conversion on a single file."""
    input_path = Path(input_file)
    output_dir = Path("output_manimce_test")
    
    converter = ManimConverter(input_path.parent, output_dir)
    converter.setup_output_directory()
    
    # Convert single file
    converted_content, was_converted = converter.convert_file(input_path)
    
    if was_converted:
        # Save converted file
        output_file = output_dir / 'converted' / input_path.name
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            f.write(converted_content)
        
        print(f"✓ Converted: {input_path} → {output_file}")
        
        # Print issues if any
        if converter.issues:
            print("\nIssues found:")
            for issue in converter.issues:
                print(f"  - {issue['issue']}: {issue.get('description', '')}")
        
        # Print if has pi_creature
        if converter.pi_creature_files:
            print("\nFile uses pi_creature - replacement characters have been suggested")
    else:
        print(f"✗ File was not converted (may already be in ManimCE format)")
    
    return converted_content

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_single_conversion.py <input_file.py>")
        sys.exit(1)
    
    test_single_file(sys.argv[1])