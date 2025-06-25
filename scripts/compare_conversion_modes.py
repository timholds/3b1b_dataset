#!/usr/bin/env python3
"""
Compare monolithic vs scene-by-scene conversion approaches.
This script runs both modes on the same video and generates a comparison report.
"""

import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple
import logging


class ConversionModeComparer:
    """Compare different conversion modes on the same video."""
    
    def __init__(self, base_dir: str, verbose: bool = False):
        self.base_dir = Path(base_dir)
        self.output_dir = self.base_dir / 'outputs'
        self.verbose = verbose
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO if verbose else logging.WARNING,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def backup_existing_files(self, video_dir: Path) -> Dict[str, Path]:
        """Backup existing cleaned and converted files."""
        backup_dir = video_dir / '.backup'
        backup_dir.mkdir(exist_ok=True)
        
        backups = {}
        files_to_backup = [
            'cleaned_code.py',
            'manimce_code.py',
            'logs.json'
        ]
        
        for filename in files_to_backup:
            file_path = video_dir / filename
            if file_path.exists():
                backup_path = backup_dir / f"{filename}.{int(time.time())}"
                file_path.rename(backup_path)
                backups[filename] = backup_path
                self.logger.info(f"Backed up {filename} to {backup_path}")
        
        # Also backup directories
        for dirname in ['cleaned_scenes', 'manimce_scenes']:
            dir_path = video_dir / dirname
            if dir_path.exists():
                backup_path = backup_dir / f"{dirname}.{int(time.time())}"
                dir_path.rename(backup_path)
                backups[dirname] = backup_path
        
        return backups
    
    def restore_backups(self, video_dir: Path, backups: Dict[str, Path]):
        """Restore backed up files."""
        for filename, backup_path in backups.items():
            if backup_path.exists():
                restore_path = video_dir / filename
                if restore_path.exists():
                    if restore_path.is_dir():
                        import shutil
                        shutil.rmtree(restore_path)
                    else:
                        restore_path.unlink()
                backup_path.rename(restore_path)
                self.logger.info(f"Restored {filename} from backup")
    
    def run_cleaning_mode(self, year: int, video: str, mode: str) -> Tuple[Dict, float]:
        """Run cleaning in specified mode and measure time."""
        self.logger.info(f"Running cleaning in {mode} mode for {video}")
        
        start_time = time.time()
        
        cmd = [
            "python", "scripts/clean_matched_code.py",
            "--year", str(year),
            "--video", video,
            "--mode", mode,
            "--force"  # Force re-cleaning
        ]
        
        if self.verbose:
            cmd.append("-v")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        elapsed_time = time.time() - start_time
        
        # Parse output for results
        success = result.returncode == 0
        output_data = {
            'success': success,
            'elapsed_time': elapsed_time,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
        # Check if cleaning produced expected outputs
        video_dir = self.output_dir / str(year) / video
        if mode == 'monolithic':
            output_data['cleaned_file_exists'] = (video_dir / 'cleaned_code.py').exists()
        else:
            scenes_dir = video_dir / 'cleaned_scenes'
            output_data['cleaned_scenes_exist'] = scenes_dir.exists()
            output_data['num_scenes'] = len(list(scenes_dir.glob('*.py'))) if scenes_dir.exists() else 0
        
        return output_data, elapsed_time
    
    def run_conversion_mode(self, year: int, video: str, mode: str) -> Tuple[Dict, float]:
        """Run conversion in specified mode and measure time."""
        self.logger.info(f"Running conversion in {mode} mode for {video}")
        
        start_time = time.time()
        
        cmd = [
            "python", "scripts/build_dataset_pipeline.py",
            "--year", str(year),
            "--video", video,
            "--conversion-mode", mode,
            "--clean-only",  # Only run conversion, skip other stages
            "--force-convert"
        ]
        
        if self.verbose:
            cmd.append("-v")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        elapsed_time = time.time() - start_time
        
        # Parse output for results
        success = result.returncode == 0
        output_data = {
            'success': success,
            'elapsed_time': elapsed_time,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
        # Check conversion outputs
        video_dir = self.output_dir / str(year) / video
        output_data['manimce_file_exists'] = (video_dir / 'manimce_code.py').exists()
        
        if mode == 'scene':
            scenes_dir = video_dir / 'manimce_scenes'
            output_data['converted_scenes_exist'] = scenes_dir.exists()
            output_data['num_converted_scenes'] = len(list(scenes_dir.glob('*.py'))) if scenes_dir.exists() else 0
        
        return output_data, elapsed_time
    
    def analyze_code_quality(self, file_path: Path) -> Dict:
        """Analyze the quality of converted code."""
        if not file_path.exists():
            return {'exists': False}
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        analysis = {
            'exists': True,
            'lines': len(content.splitlines()),
            'size_bytes': len(content),
            'has_syntax_errors': False,
            'imports_manim': 'from manim import' in content,
            'has_pi_creatures': 'Pi Creature' in content or 'REMOVED:' in content,
            'has_scenes': 'class ' in content and '(Scene' in content
        }
        
        # Check syntax
        try:
            compile(content, str(file_path), 'exec')
        except SyntaxError as e:
            analysis['has_syntax_errors'] = True
            analysis['syntax_error'] = str(e)
        
        return analysis
    
    def compare_modes(self, year: int, video: str) -> Dict:
        """Run both modes and compare results."""
        self.logger.info(f"Comparing conversion modes for {video} ({year})")
        
        video_dir = self.output_dir / str(year) / video
        if not video_dir.exists():
            return {'error': f'Video directory not found: {video_dir}'}
        
        comparison = {
            'video': video,
            'year': year,
            'timestamp': datetime.now().isoformat(),
            'results': {}
        }
        
        # Test both cleaning modes
        for cleaning_mode in ['monolithic', 'scene']:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Testing {cleaning_mode} cleaning mode")
            self.logger.info(f"{'='*60}")
            
            # Backup existing files
            backups = self.backup_existing_files(video_dir)
            
            try:
                # Run cleaning
                clean_result, clean_time = self.run_cleaning_mode(year, video, cleaning_mode)
                
                # Only test matching conversion mode
                conversion_mode = cleaning_mode
                
                # Run conversion
                convert_result, convert_time = self.run_conversion_mode(year, video, conversion_mode)
                
                # Analyze output
                manimce_file = video_dir / 'manimce_code.py'
                code_analysis = self.analyze_code_quality(manimce_file)
                
                # Store results
                mode_key = f"{cleaning_mode}_cleaning_{conversion_mode}_conversion"
                comparison['results'][mode_key] = {
                    'cleaning': {
                        'success': clean_result['success'],
                        'time': clean_time,
                        'details': clean_result
                    },
                    'conversion': {
                        'success': convert_result['success'],
                        'time': convert_time,
                        'details': convert_result
                    },
                    'total_time': clean_time + convert_time,
                    'code_analysis': code_analysis
                }
                
            except Exception as e:
                self.logger.error(f"Error in {cleaning_mode} mode: {e}")
                comparison['results'][f"{cleaning_mode}_mode"] = {
                    'error': str(e)
                }
            
            finally:
                # Restore backups for next test
                self.restore_backups(video_dir, backups)
        
        # Generate summary
        comparison['summary'] = self.generate_summary(comparison['results'])
        
        return comparison
    
    def generate_summary(self, results: Dict) -> Dict:
        """Generate summary comparing the modes."""
        summary = {
            'best_mode': None,
            'fastest_mode': None,
            'most_successful': None,
            'recommendations': []
        }
        
        # Find fastest mode
        min_time = float('inf')
        for mode, data in results.items():
            if 'total_time' in data and data['total_time'] < min_time:
                min_time = data['total_time']
                summary['fastest_mode'] = mode
        
        # Find most successful mode
        for mode, data in results.items():
            if 'error' not in data:
                clean_success = data.get('cleaning', {}).get('success', False)
                convert_success = data.get('conversion', {}).get('success', False)
                syntax_ok = not data.get('code_analysis', {}).get('has_syntax_errors', True)
                
                if clean_success and convert_success and syntax_ok:
                    summary['most_successful'] = mode
                    break
        
        # Determine best mode
        if summary['most_successful']:
            summary['best_mode'] = summary['most_successful']
        elif summary['fastest_mode']:
            summary['best_mode'] = summary['fastest_mode']
        
        # Generate recommendations
        if 'scene' in summary.get('best_mode', ''):
            summary['recommendations'].append("Scene-by-scene mode recommended for this video")
            summary['recommendations'].append("Better error isolation and focused conversion")
        else:
            summary['recommendations'].append("Monolithic mode recommended for this video")
            summary['recommendations'].append("Simpler process with fewer steps")
        
        return summary
    
    def save_comparison_report(self, comparison: Dict, output_file: Path):
        """Save comparison report to file."""
        with open(output_file, 'w') as f:
            json.dump(comparison, f, indent=2)
        
        # Also create human-readable report
        report_text = f"""
Conversion Mode Comparison Report
================================
Video: {comparison['video']} ({comparison['year']})
Date: {comparison['timestamp']}

Results:
"""
        
        for mode, data in comparison['results'].items():
            report_text += f"\n{mode}:\n"
            report_text += f"  Cleaning: {'✓' if data.get('cleaning', {}).get('success') else '✗'}"
            report_text += f" ({data.get('cleaning', {}).get('time', 0):.1f}s)\n"
            report_text += f"  Conversion: {'✓' if data.get('conversion', {}).get('success') else '✗'}"
            report_text += f" ({data.get('conversion', {}).get('time', 0):.1f}s)\n"
            report_text += f"  Total Time: {data.get('total_time', 0):.1f}s\n"
            
            analysis = data.get('code_analysis', {})
            if analysis.get('exists'):
                report_text += f"  Code Quality:\n"
                report_text += f"    - Lines: {analysis.get('lines', 0)}\n"
                report_text += f"    - Syntax Valid: {'✓' if not analysis.get('has_syntax_errors') else '✗'}\n"
                report_text += f"    - Has Scenes: {'✓' if analysis.get('has_scenes') else '✗'}\n"
        
        report_text += f"\nSummary:\n"
        report_text += f"  Best Mode: {comparison['summary']['best_mode']}\n"
        report_text += f"  Fastest: {comparison['summary']['fastest_mode']}\n"
        report_text += f"  Most Successful: {comparison['summary']['most_successful']}\n"
        report_text += f"\nRecommendations:\n"
        for rec in comparison['summary']['recommendations']:
            report_text += f"  - {rec}\n"
        
        report_file = output_file.with_suffix('.txt')
        with open(report_file, 'w') as f:
            f.write(report_text)
        
        print(report_text)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Compare conversion modes')
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    parser.add_argument('--video', type=str, required=True,
                        help='Video to compare')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--output', type=str,
                        help='Output file for comparison report')
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent.parent
    comparer = ConversionModeComparer(base_dir, verbose=args.verbose)
    
    # Run comparison
    comparison = comparer.compare_modes(args.year, args.video)
    
    # Save report
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = base_dir / 'outputs' / 'comparison_reports' / f'{args.video}_comparison.json'
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    comparer.save_comparison_report(comparison, output_file)
    
    print(f"\nComparison report saved to: {output_file}")


if __name__ == '__main__':
    main()