#!/usr/bin/env python3
"""
Test script to validate video rendering functionality
"""

import json
import subprocess
import sys
from pathlib import Path
from render_videos import VideoRenderer

def check_dependencies():
    """Check if required dependencies are installed."""
    print("Checking dependencies...")
    
    # Check for manim
    try:
        result = subprocess.run(['manim', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Manim installed: {result.stdout.strip()}")
        else:
            print("✗ Manim not found. Install with: pip install manim")
            return False
    except FileNotFoundError:
        print("✗ Manim not found. Install with: pip install manim")
        return False
        
    # Check for ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ FFmpeg installed")
        else:
            print("✗ FFmpeg not found. Install ffmpeg for thumbnail generation")
    except FileNotFoundError:
        print("✗ FFmpeg not found. Install ffmpeg for thumbnail generation")
        
    return True

def find_test_video(base_dir: Path, year: int = 2015) -> tuple:
    """Find a suitable video for testing."""
    output_dir = base_dir / 'output' / 'v5' / str(year)
    
    if not output_dir.exists():
        print(f"No output directory found for year {year}")
        return None, None
        
    # Look for videos with cleaned or converted code
    for video_dir in output_dir.iterdir():
        if not video_dir.is_dir():
            continue
            
        manimce_file = video_dir / 'manimce_code.py' 
        cleaned_file = video_dir / 'cleaned_code.py'
        
        code_file = manimce_file if manimce_file.exists() else cleaned_file
        
        if code_file.exists():
            # Check if it has scenes
            renderer = VideoRenderer(base_dir)
            scenes = renderer.extract_scene_classes(code_file)
            if scenes:
                return video_dir.name, code_file
                
    return None, None

def test_single_video_render():
    """Test rendering a single video."""
    base_dir = Path(__file__).parent.parent
    
    # Check dependencies
    if not check_dependencies():
        print("\nPlease install missing dependencies and try again.")
        return
        
    print("\n" + "="*60)
    print("Testing Video Rendering")
    print("="*60)
    
    # Find a test video
    video_id, code_file = find_test_video(base_dir)
    
    if not video_id:
        print("No suitable test video found. Run the pipeline first to generate cleaned code.")
        return
        
    print(f"\nTest video: {video_id}")
    print(f"Code file: {code_file}")
    
    # Create renderer
    renderer = VideoRenderer(base_dir, verbose=True)
    
    # Extract scenes
    scenes = renderer.extract_scene_classes(code_file)
    print(f"\nFound {len(scenes)} scenes: {', '.join(scenes)}")
    
    if not scenes:
        print("No scenes found in code file")
        return
        
    # Test title extraction
    title = renderer.get_video_title(2015, video_id)
    safe_title = renderer.sanitize_title_for_filename(title)
    print(f"\nVideo title: {title}")
    print(f"Safe filename: {safe_title}")
    
    # Render just the first scene as a test
    print(f"\nRendering first scene: {scenes[0]}")
    print("This may take a minute...")
    
    result = renderer.render_video(
        year=2015,
        video_id=video_id,
        code_file=code_file,
        quality='preview',
        scenes_limit=1  # Just render first scene
    )
    
    print("\n" + "="*60)
    print("Rendering Result")
    print("="*60)
    
    if result['status'] == 'success':
        print("✓ Rendering successful!")
        
        if result['rendered_scenes']:
            scene_info = result['rendered_scenes'][0]
            output_file = Path(scene_info['output_file'])
            
            if output_file.exists():
                size_mb = output_file.stat().st_size / (1024 * 1024)
                print(f"\nOutput file: {output_file}")
                print(f"File size: {size_mb:.2f} MB")
                print(f"Render time: {scene_info['duration']:.1f} seconds")
                
                # Try to generate thumbnail
                print("\nGenerating thumbnail...")
                thumb = renderer.generate_thumbnail(output_file)
                if thumb:
                    print(f"✓ Thumbnail created: {thumb}")
                else:
                    print("✗ Thumbnail generation failed (ffmpeg may not be installed)")
                    
                print(f"\nYou can view the video with:")
                print(f"  open {output_file}")
            else:
                print("✗ Output file not found")
    else:
        print(f"✗ Rendering failed: {result.get('status')}")
        
        if result.get('failed_scenes'):
            for failed in result['failed_scenes']:
                print(f"\nScene: {failed['scene_name']}")
                print(f"Error: {failed.get('error')}")
                if failed.get('stderr'):
                    print(f"Stderr: {failed['stderr']}")
                    
    # Show where results are saved
    render_dir = base_dir / 'output' / 'rendered_videos' / '2015' / video_id
    if render_dir.exists():
        print(f"\nAll rendering outputs saved to:")
        print(f"  {render_dir}")
        
        # List files
        files = list(render_dir.iterdir())
        if files:
            print("\nGenerated files:")
            for f in files:
                print(f"  - {f.name}")

def main():
    """Run the test."""
    try:
        test_single_video_render()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()