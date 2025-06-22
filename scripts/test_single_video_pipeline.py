#!/usr/bin/env python3
"""
Test the complete pipeline on a single video.
This script runs all stages (matching, cleaning, conversion) on one video for testing.
"""

import json
import sys
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional

class SingleVideoPipelineTester:
    def __init__(self, base_dir: str, video_caption_dir: str, year: int = 2015, verbose: bool = True):
        self.base_dir = Path(base_dir)
        self.video_caption_dir = video_caption_dir
        self.year = year
        self.verbose = verbose
        self.output_dir = self.base_dir / 'output' / 'v5' / str(year) / video_caption_dir
        
    def run_stage(self, stage_name: str, command: list) -> Dict:
        """Run a pipeline stage and capture results."""
        print(f"\n{'='*60}")
        print(f"Running {stage_name}")
        print(f"{'='*60}")
        
        if self.verbose:
            print(f"Command: {' '.join(command)}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=self.base_dir
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                print(f"✅ {stage_name} completed in {duration:.1f}s")
                if self.verbose and result.stdout:
                    print(f"Output:\n{result.stdout}")
                return {"status": "success", "duration": duration}
            else:
                print(f"❌ {stage_name} failed (exit code: {result.returncode})")
                if result.stderr:
                    print(f"Error:\n{result.stderr}")
                return {"status": "failed", "error": result.stderr, "duration": duration}
                
        except Exception as e:
            print(f"❌ {stage_name} crashed: {e}")
            return {"status": "crashed", "error": str(e)}
    
    def check_file_exists(self, file_path: Path, description: str) -> bool:
        """Check if a file exists and report."""
        if file_path.exists():
            print(f"✅ {description} found: {file_path}")
            
            # If it's a JSON file, try to load and show summary
            if file_path.suffix == '.json':
                try:
                    with open(file_path) as f:
                        data = json.load(f)
                    
                    if 'confidence_score' in data:
                        print(f"   Confidence: {data['confidence_score']}")
                    if 'primary_files' in data:
                        print(f"   Primary files: {data['primary_files']}")
                except:
                    pass
                    
            # If it's a Python file, show size
            elif file_path.suffix == '.py':
                size = file_path.stat().st_size
                print(f"   Size: {size:,} bytes")
                
            return True
        else:
            print(f"❌ {description} not found: {file_path}")
            return False
    
    def create_test_mappings(self) -> Path:
        """Create a test mappings file with just our single video."""
        # First, we need to get the video info
        original_mappings = self.base_dir / 'data' / 'youtube_metadata' / f'{self.year}_video_mappings.json'
        
        if not original_mappings.exists():
            print(f"❌ Original mappings not found: {original_mappings}")
            print("   Run extract_video_urls.py first")
            return None
            
        with open(original_mappings) as f:
            all_mappings = json.load(f)
            
        if self.video_caption_dir not in all_mappings:
            print(f"❌ Video '{self.video_caption_dir}' not found in mappings")
            print(f"   Available videos: {list(all_mappings.keys())[:5]}...")
            return None
            
        # Create test mappings with just our video
        test_mappings = {self.video_caption_dir: all_mappings[self.video_caption_dir]}
        
        test_mappings_file = self.base_dir / 'data' / 'youtube_metadata' / 'test_single_video_mappings.json'
        with open(test_mappings_file, 'w') as f:
            json.dump(test_mappings, f, indent=2)
            
        return test_mappings_file
    
    def run_matching(self) -> Dict:
        """Run the matching stage for a single video."""
        # Create temporary mappings file
        test_mappings = self.create_test_mappings()
        if not test_mappings:
            return {"status": "failed", "error": "Could not create test mappings"}
            
        # Temporarily replace the mappings file
        original_mappings = self.base_dir / 'data' / 'youtube_metadata' / f'{self.year}_video_mappings.json'
        backup_mappings = original_mappings.with_suffix('.json.backup')
        
        try:
            # Backup original and use test mappings
            import shutil
            shutil.move(original_mappings, backup_mappings)
            shutil.move(test_mappings, original_mappings)
            
            # Run matching
            result = self.run_stage(
                "Matching",
                ["python", "scripts/claude_match_videos.py", "--year", str(self.year)]
            )
            
            return result
            
        finally:
            # Restore original mappings
            if backup_mappings.exists():
                shutil.move(backup_mappings, original_mappings)
            if test_mappings.exists():
                test_mappings.unlink()
    
    def run_cleaning(self) -> Dict:
        """Run the cleaning stage for a single video."""
        return self.run_stage(
            "Cleaning",
            ["python", "scripts/clean_matched_code.py", 
             "--year", str(self.year),
             "--video", self.video_caption_dir]
        )
    
    def run_conversion(self) -> Dict:
        """Run the ManimGL to ManimCE conversion for a single video."""
        cleaned_file = self.output_dir / 'cleaned_code.py'
        manimce_file = self.output_dir / 'manimce_code.py'
        
        if not cleaned_file.exists():
            return {"status": "skipped", "error": "No cleaned file to convert"}
            
        return self.run_stage(
            "Conversion",
            ["python", "scripts/convert_manimgl_to_manimce.py", 
             str(cleaned_file), str(manimce_file)]
        )
    
    def validate_python_syntax(self, file_path: Path) -> bool:
        """Validate that a Python file has correct syntax."""
        try:
            with open(file_path) as f:
                code = f.read()
            compile(code, str(file_path), 'exec')
            print(f"✅ Valid Python syntax: {file_path.name}")
            return True
        except SyntaxError as e:
            print(f"❌ Syntax error in {file_path.name}: {e}")
            return False
        except Exception as e:
            print(f"❌ Error validating {file_path.name}: {e}")
            return False
    
    def run_full_test(self):
        """Run the complete pipeline test on a single video."""
        print(f"Testing pipeline on video: {self.video_caption_dir}")
        print(f"Year: {self.year}")
        print(f"Output directory: {self.output_dir}")
        
        results = {
            "video": self.video_caption_dir,
            "year": self.year,
            "stages": {}
        }
        
        # Stage 1: Matching
        matching_result = self.run_matching()
        results["stages"]["matching"] = matching_result
        
        if matching_result["status"] != "success":
            print("\n❌ Pipeline failed at matching stage")
            return results
            
        # Check matching output
        match_file = self.output_dir / 'matches.json'
        if not self.check_file_exists(match_file, "Match results"):
            results["stages"]["matching"]["output_missing"] = True
            return results
            
        # Stage 2: Cleaning
        print("\nWaiting 2 seconds before cleaning...")
        time.sleep(2)
        
        cleaning_result = self.run_cleaning()
        results["stages"]["cleaning"] = cleaning_result
        
        if cleaning_result["status"] != "success":
            print("\n❌ Pipeline failed at cleaning stage")
            return results
            
        # Check cleaning output
        cleaned_file = self.output_dir / 'cleaned_code.py'
        if not self.check_file_exists(cleaned_file, "Cleaned code"):
            results["stages"]["cleaning"]["output_missing"] = True
            return results
            
        # Validate cleaned code syntax
        if not self.validate_python_syntax(cleaned_file):
            results["stages"]["cleaning"]["syntax_invalid"] = True
            
        # Stage 3: Conversion
        print("\nWaiting 2 seconds before conversion...")
        time.sleep(2)
        
        conversion_result = self.run_conversion()
        results["stages"]["conversion"] = conversion_result
        
        if conversion_result["status"] == "success":
            # Check conversion output
            manimce_file = self.output_dir / 'manimce_code.py'
            if self.check_file_exists(manimce_file, "ManimCE code"):
                # Validate converted code syntax
                if not self.validate_python_syntax(manimce_file):
                    results["stages"]["conversion"]["syntax_invalid"] = True
                    
                # Check that it actually converted
                with open(cleaned_file) as f:
                    cleaned_content = f.read()
                with open(manimce_file) as f:
                    manimce_content = f.read()
                    
                if 'from manimlib' in manimce_content:
                    print("⚠️  Warning: ManimCE file still contains manimlib imports")
                    results["stages"]["conversion"]["incomplete_conversion"] = True
                elif cleaned_content == manimce_content:
                    print("⚠️  Warning: ManimCE file is identical to cleaned file")
                    results["stages"]["conversion"]["no_changes"] = True
                else:
                    print("✅ Conversion appears successful")
            else:
                results["stages"]["conversion"]["output_missing"] = True
        
        # Final summary
        print(f"\n{'='*60}")
        print("Pipeline Test Summary")
        print(f"{'='*60}")
        
        all_success = all(
            stage.get("status") == "success" 
            for stage in results["stages"].values()
        )
        
        if all_success:
            print("✅ All stages completed successfully!")
            
            # Show final outputs
            print("\nGenerated files:")
            for file_name in ['matches.json', 'cleaned_code.py', 'manimce_code.py']:
                file_path = self.output_dir / file_name
                if file_path.exists():
                    size = file_path.stat().st_size
                    print(f"  - {file_name}: {size:,} bytes")
        else:
            print("❌ Pipeline test failed")
            
            for stage_name, stage_result in results["stages"].items():
                if stage_result.get("status") != "success":
                    print(f"  - {stage_name}: {stage_result.get('status')}")
                    
        # Save test results
        results_file = self.output_dir / 'pipeline_test_results.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nTest results saved to: {results_file}")
        
        return results

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Test the complete pipeline on a single video'
    )
    parser.add_argument('video', 
                        help='Video caption directory name (e.g., "inventing-math")')
    parser.add_argument('--year', type=int, default=2015,
                        help='Year of the video (default: 2015)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Reduce output verbosity')
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent.parent
    tester = SingleVideoPipelineTester(
        base_dir, 
        args.video, 
        args.year,
        verbose=not args.quiet
    )
    
    results = tester.run_full_test()
    
    # Exit with appropriate code
    all_success = all(
        stage.get("status") == "success" 
        for stage in results["stages"].values()
    )
    sys.exit(0 if all_success else 1)

if __name__ == '__main__':
    main()