#!/usr/bin/env python3
"""
View pipeline processing history from logs.json files.

This script helps visualize what stages have been completed for each video
and when they were processed.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import argparse


def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return timestamp_str[:16] if len(timestamp_str) > 16 else timestamp_str


def load_video_logs(video_dir: Path) -> Dict:
    """Load logs from both possible locations."""
    logs = {}
    
    # Check new location first
    new_log_path = video_dir / 'logs.json'
    if new_log_path.exists():
        try:
            with open(new_log_path, 'r') as f:
                logs.update(json.load(f))
        except:
            pass
    
    # Check old location
    old_log_path = video_dir / '.pipeline' / 'logs' / 'logs.json'
    if old_log_path.exists():
        try:
            with open(old_log_path, 'r') as f:
                old_logs = json.load(f)
                # Merge, preferring old logs for duplicate keys
                for key, value in old_logs.items():
                    if key not in logs:
                        logs[key] = value
        except:
            pass
    
    return logs


def analyze_pipeline_history(base_dir: Path, year: Optional[int] = None, 
                           video_filter: Optional[List[str]] = None) -> Dict:
    """Analyze pipeline processing history across videos."""
    outputs_dir = base_dir / 'outputs'
    
    if not outputs_dir.exists():
        return {'error': 'No outputs directory found'}
    
    results = {
        'years': {},
        'summary': {
            'total_videos': 0,
            'stages_completed': {
                'matching': 0,
                'cleaning': 0,
                'conversion': 0,
                'rendering': 0
            }
        }
    }
    
    # Determine which years to process
    if year:
        year_dirs = [outputs_dir / str(year)] if (outputs_dir / str(year)).exists() else []
    else:
        year_dirs = [d for d in outputs_dir.iterdir() if d.is_dir() and d.name.isdigit()]
    
    for year_dir in sorted(year_dirs):
        year_num = int(year_dir.name)
        year_data = {
            'videos': {},
            'total': 0,
            'with_logs': 0
        }
        
        # Process each video
        for video_dir in sorted(year_dir.iterdir()):
            if not video_dir.is_dir():
                continue
                
            # Apply video filter if specified
            if video_filter and video_dir.name not in video_filter:
                continue
            
            year_data['total'] += 1
            results['summary']['total_videos'] += 1
            
            # Load logs
            logs = load_video_logs(video_dir)
            
            if logs:
                year_data['with_logs'] += 1
                
                video_info = {
                    'stages': {},
                    'last_updated': None
                }
                
                # Track latest timestamp
                latest_timestamp = None
                
                # Process each stage
                for stage in ['matching', 'cleaning', 'parameterized_conversion', 
                            'conversion', 'rendering']:
                    if stage in logs:
                        stage_data = logs[stage]
                        timestamp = stage_data.get('timestamp', '')
                        
                        video_info['stages'][stage] = {
                            'completed': True,
                            'timestamp': format_timestamp(timestamp)
                        }
                        
                        # Track completion
                        if stage in results['summary']['stages_completed']:
                            results['summary']['stages_completed'][stage] += 1
                        
                        # Update latest timestamp
                        if timestamp and (not latest_timestamp or timestamp > latest_timestamp):
                            latest_timestamp = timestamp
                
                video_info['last_updated'] = format_timestamp(latest_timestamp) if latest_timestamp else 'Unknown'
                year_data['videos'][video_dir.name] = video_info
            else:
                year_data['videos'][video_dir.name] = {
                    'stages': {},
                    'last_updated': 'No logs found'
                }
        
        results['years'][year_num] = year_data
    
    return results


def print_history_report(results: Dict, detailed: bool = False):
    """Print formatted history report."""
    print("\n" + "="*80)
    print("PIPELINE PROCESSING HISTORY")
    print("="*80)
    
    # Summary
    summary = results['summary']
    print(f"\nTotal videos found: {summary['total_videos']}")
    print("\nStages completed:")
    for stage, count in summary['stages_completed'].items():
        percentage = (count / max(summary['total_videos'], 1)) * 100
        print(f"  {stage.capitalize():20} {count:4d} ({percentage:5.1f}%)")
    
    # Year-by-year breakdown
    for year, year_data in sorted(results['years'].items()):
        print(f"\n{'-'*80}")
        print(f"Year {year}: {year_data['total']} videos ({year_data['with_logs']} with logs)")
        
        if detailed and year_data['videos']:
            print(f"\nVideos:")
            for video_name, video_info in sorted(year_data['videos'].items()):
                stages = video_info['stages']
                stage_markers = []
                
                for stage in ['matching', 'cleaning', 'conversion', 'rendering']:
                    if stage in stages:
                        stage_markers.append(stage[0].upper())
                    else:
                        stage_markers.append('-')
                
                stage_str = ''.join(stage_markers)
                print(f"  {video_name:50} [{stage_str}] {video_info['last_updated']}")
        else:
            # Summary view
            stage_counts = {'matching': 0, 'cleaning': 0, 'conversion': 0, 'rendering': 0}
            
            for video_info in year_data['videos'].values():
                for stage in stage_counts:
                    if stage in video_info['stages']:
                        stage_counts[stage] += 1
            
            print("  Completed stages:")
            for stage, count in stage_counts.items():
                if count > 0:
                    print(f"    {stage.capitalize():15} {count:3d}")


def main():
    parser = argparse.ArgumentParser(
        description='View pipeline processing history from logs'
    )
    parser.add_argument('--year', type=int,
                       help='Show history for specific year only')
    parser.add_argument('--video', action='append',
                       help='Show history for specific video(s) only')
    parser.add_argument('--detailed', '-d', action='store_true',
                       help='Show detailed video-by-video breakdown')
    parser.add_argument('--json', action='store_true',
                       help='Output raw JSON data')
    
    args = parser.parse_args()
    
    # Get base directory
    base_dir = Path(__file__).parent.parent
    
    # Analyze history
    results = analyze_pipeline_history(base_dir, year=args.year, video_filter=args.video)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_history_report(results, detailed=args.detailed)


if __name__ == '__main__':
    main()