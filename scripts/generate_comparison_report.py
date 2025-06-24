#!/usr/bin/env python3
"""
Generate comparison reports between original YouTube videos and rendered ManimCE videos.
Creates both JSON data files and HTML dashboards for easy comparison.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import subprocess
import urllib.parse


class ComparisonReportGenerator:
    def __init__(self, base_dir: str, verbose: bool = False):
        self.base_dir = Path(base_dir)
        self.output_base_dir = self.base_dir / 'outputs'
        self.comparison_dir = self.output_base_dir / 'comparison_reports'
        self.verbose = verbose
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if verbose:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
            
    def get_youtube_metadata(self, video_id: str) -> Dict:
        """
        Get YouTube video metadata using yt-dlp.
        Returns basic metadata without downloading the video.
        """
        try:
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                metadata = json.loads(result.stdout)
                return {
                    'title': metadata.get('title', ''),
                    'duration': metadata.get('duration', 0),
                    'upload_date': metadata.get('upload_date', ''),
                    'description': metadata.get('description', '')[:500],  # First 500 chars
                    'width': metadata.get('width', 0),
                    'height': metadata.get('height', 0),
                    'fps': metadata.get('fps', 0),
                    'view_count': metadata.get('view_count', 0),
                    'like_count': metadata.get('like_count', 0),
                    'channel': metadata.get('channel', ''),
                    'thumbnail': metadata.get('thumbnail', '')
                }
            else:
                self.logger.error(f"Failed to get metadata for {video_id}: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout getting metadata for {video_id}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting metadata for {video_id}: {e}")
            return None
            
    def get_rendered_video_info(self, video_dir: Path) -> Dict:
        """Extract information about rendered videos from a video directory."""
        render_metadata_file = video_dir / 'rendered_videos' / 'render_metadata.json'
        
        if not render_metadata_file.exists():
            return None
            
        try:
            with open(render_metadata_file) as f:
                data = json.load(f)
                return data.get('results', {})
        except Exception as e:
            self.logger.error(f"Error reading render metadata: {e}")
            return None
            
    def get_video_duration(self, video_path: Path) -> float:
        """Get duration of a video file using ffprobe."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return float(result.stdout.strip())
            return 0.0
            
        except:
            return 0.0
            
    def calculate_comparison_metrics(self, original_meta: Dict, rendered_info: Dict) -> Dict:
        """Calculate comparison metrics between original and rendered videos."""
        if not original_meta or not rendered_info:
            return {
                'status': 'missing_data',
                'duration_match': 0.0,
                'scene_coverage': 0.0,
                'resolution_match': False
            }
            
        metrics = {}
        
        # Calculate total rendered duration
        total_rendered_duration = 0.0
        if rendered_info.get('rendered_scenes'):
            for scene in rendered_info['rendered_scenes']:
                if 'output_file' in scene:
                    video_path = Path(scene['output_file'])
                    if video_path.exists():
                        duration = self.get_video_duration(video_path)
                        total_rendered_duration += duration
        
        # Duration match percentage
        original_duration = original_meta.get('duration', 0)
        if original_duration > 0:
            metrics['duration_match'] = min(1.0, total_rendered_duration / original_duration)
        else:
            metrics['duration_match'] = 0.0
            
        # Scene coverage
        total_scenes = rendered_info.get('total_scenes', 0)
        rendered_scenes = len(rendered_info.get('rendered_scenes', []))
        if total_scenes > 0:
            metrics['scene_coverage'] = rendered_scenes / total_scenes
        else:
            metrics['scene_coverage'] = 0.0
            
        # Resolution match (considering we render at different qualities)
        metrics['resolution_match'] = True  # We control this via quality settings
        
        # Overall status
        if metrics['scene_coverage'] == 1.0:
            metrics['status'] = 'success'
        elif metrics['scene_coverage'] > 0:
            metrics['status'] = 'partial'
        else:
            metrics['status'] = 'failed'
            
        metrics['total_rendered_duration'] = total_rendered_duration
        metrics['original_duration'] = original_duration
        metrics['scenes_rendered'] = rendered_scenes
        metrics['total_scenes'] = total_scenes
        
        return metrics
        
    def generate_video_comparison(self, year: int, video_id: str, video_dir: Path) -> Dict:
        """Generate comparison data for a single video."""
        self.logger.info(f"Generating comparison for {video_id}")
        
        # Get matches.json to find YouTube video ID
        matches_file = video_dir / 'matches.json'
        if not matches_file.exists():
            return None
            
        with open(matches_file) as f:
            matches = json.load(f)
            
        youtube_id = matches.get('video_id')
        if not youtube_id:
            self.logger.warning(f"No YouTube ID found for {video_id}")
            return None
            
        # Get YouTube metadata
        youtube_meta = self.get_youtube_metadata(youtube_id)
        
        # Get rendered video info
        rendered_info = self.get_rendered_video_info(video_dir)
        
        # Calculate comparison metrics
        metrics = self.calculate_comparison_metrics(youtube_meta, rendered_info)
        
        # Build comparison data
        comparison = {
            'video_name': video_id,
            'year': year,
            'timestamp': datetime.now().isoformat(),
            'original': {
                'youtube_id': youtube_id,
                'youtube_url': f'https://www.youtube.com/watch?v={youtube_id}',
                'title': youtube_meta.get('title', '') if youtube_meta else '',
                'duration': youtube_meta.get('duration', 0) if youtube_meta else 0,
                'resolution': f"{youtube_meta.get('width', 0)}x{youtube_meta.get('height', 0)}" if youtube_meta else 'unknown',
                'fps': youtube_meta.get('fps', 0) if youtube_meta else 0,
                'upload_date': youtube_meta.get('upload_date', '') if youtube_meta else '',
                'view_count': youtube_meta.get('view_count', 0) if youtube_meta else 0,
                'thumbnail': youtube_meta.get('thumbnail', '') if youtube_meta else ''
            },
            'rendered': {
                'status': metrics['status'],
                'scenes_rendered': metrics['scenes_rendered'],
                'total_scenes': metrics['total_scenes'],
                'total_duration': metrics['total_rendered_duration'],
                'render_date': rendered_info.get('timestamp', '') if rendered_info else '',
                'quality': rendered_info.get('quality', '') if rendered_info else '',
                'file_paths': [s['output_file'] for s in rendered_info.get('rendered_scenes', [])] if rendered_info else []
            },
            'comparison': {
                'duration_match': metrics['duration_match'],
                'scene_coverage': metrics['scene_coverage'],
                'resolution_match': metrics['resolution_match'],
                'missing_duration': max(0, metrics['original_duration'] - metrics['total_rendered_duration']),
                'issues': []
            }
        }
        
        # Identify issues
        if metrics['scene_coverage'] < 1.0:
            failed_scenes = rendered_info.get('failed_scenes', []) if rendered_info else []
            for scene in failed_scenes:
                comparison['comparison']['issues'].append(f"Failed to render: {scene.get('scene_name', 'unknown')}")
                
        if metrics['duration_match'] < 0.9:
            comparison['comparison']['issues'].append(f"Duration mismatch: {metrics['duration_match']:.1%} of original")
            
        return comparison
        
    def generate_year_comparison(self, year: int) -> Dict:
        """Generate comparison report for an entire year."""
        self.logger.info(f"Generating comparison report for year {year}")
        
        year_output_dir = self.output_base_dir / str(year)
        if not year_output_dir.exists():
            self.logger.error(f"No output directory found for year {year}")
            return None
            
        comparisons = []
        stats = {
            'total_videos': 0,
            'fully_successful': 0,
            'partially_successful': 0,
            'failed': 0,
            'not_processed': 0
        }
        
        # Process each video directory
        for video_dir in sorted(year_output_dir.iterdir()):
            if not video_dir.is_dir():
                continue
                
            stats['total_videos'] += 1
            
            # Check if video has been rendered
            render_dir = video_dir / 'rendered_videos'
            if not render_dir.exists():
                stats['not_processed'] += 1
                continue
                
            # Generate comparison
            comparison = self.generate_video_comparison(year, video_dir.name, video_dir)
            
            if comparison:
                comparisons.append(comparison)
                
                # Update stats
                status = comparison['comparison'].get('status', 'failed')
                if status == 'success':
                    stats['fully_successful'] += 1
                elif status == 'partial':
                    stats['partially_successful'] += 1
                else:
                    stats['failed'] += 1
                    
        # Create year comparison report
        year_report = {
            'year': year,
            'generated_at': datetime.now().isoformat(),
            'statistics': stats,
            'success_rate': stats['fully_successful'] / stats['total_videos'] if stats['total_videos'] > 0 else 0,
            'videos': comparisons
        }
        
        # Save comparison data
        comparison_year_dir = self.comparison_dir / str(year)
        comparison_year_dir.mkdir(parents=True, exist_ok=True)
        
        comparison_data_file = comparison_year_dir / 'comparison_data.json'
        with open(comparison_data_file, 'w') as f:
            json.dump(year_report, f, indent=2)
            
        self.logger.info(f"Saved comparison data to {comparison_data_file}")
        
        # Generate HTML dashboard
        self.generate_html_dashboard(year_report, comparison_year_dir)
        
        return year_report
        
    def generate_html_dashboard(self, report: Dict, output_dir: Path):
        """Generate an HTML dashboard for the comparison report."""
        html_file = output_dir / 'comparison_dashboard.html'
        
        # Calculate additional stats
        stats = report['statistics']
        success_rate = stats['fully_successful'] / stats['total_videos'] * 100 if stats['total_videos'] > 0 else 0
        partial_rate = stats['partially_successful'] / stats['total_videos'] * 100 if stats['total_videos'] > 0 else 0
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3Blue1Brown Video Comparison - {report['year']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .header {{ background-color: #1a73e8; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #1a73e8; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        .video-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }}
        .video-card {{ background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .video-header {{ padding: 15px; border-bottom: 1px solid #eee; }}
        .video-title {{ font-weight: bold; margin-bottom: 5px; }}
        .video-id {{ color: #666; font-size: 0.9em; }}
        .video-body {{ padding: 15px; }}
        .metric {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
        .metric-label {{ color: #666; }}
        .metric-value {{ font-weight: bold; }}
        .status-success {{ background-color: #4caf50; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; }}
        .status-partial {{ background-color: #ff9800; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; }}
        .status-failed {{ background-color: #f44336; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; }}
        .progress-bar {{ width: 100%; height: 20px; background-color: #eee; border-radius: 10px; overflow: hidden; margin-top: 5px; }}
        .progress-fill {{ height: 100%; background-color: #4caf50; transition: width 0.3s; }}
        .issues {{ margin-top: 10px; padding: 10px; background-color: #fff3cd; border-radius: 4px; font-size: 0.9em; }}
        .thumbnail {{ width: 100%; height: 150px; object-fit: cover; }}
        .filters {{ margin-bottom: 20px; }}
        .filter-button {{ padding: 8px 16px; margin-right: 10px; border: none; border-radius: 4px; cursor: pointer; }}
        .filter-button.active {{ background-color: #1a73e8; color: white; }}
        .youtube-link {{ color: #1a73e8; text-decoration: none; font-size: 0.9em; }}
        .youtube-link:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>3Blue1Brown Video Recreation Report - {report['year']}</h1>
        <p>Generated: {datetime.fromisoformat(report['generated_at']).strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{stats['total_videos']}</div>
            <div class="stat-label">Total Videos</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats['fully_successful']}</div>
            <div class="stat-label">Fully Recreated</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats['partially_successful']}</div>
            <div class="stat-label">Partially Recreated</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats['failed']}</div>
            <div class="stat-label">Failed</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{success_rate:.1f}%</div>
            <div class="stat-label">Success Rate</div>
        </div>
    </div>
    
    <div class="filters">
        <button class="filter-button active" onclick="filterVideos('all')">All Videos</button>
        <button class="filter-button" onclick="filterVideos('success')">Successful</button>
        <button class="filter-button" onclick="filterVideos('partial')">Partial</button>
        <button class="filter-button" onclick="filterVideos('failed')">Failed</button>
    </div>
    
    <div class="video-grid" id="videoGrid">
"""
        
        # Add video cards
        for video in sorted(report['videos'], key=lambda x: x['comparison']['scene_coverage'], reverse=True):
            status = video['rendered']['status']
            status_class = f'status-{status}'
            scene_coverage = video['comparison']['scene_coverage'] * 100
            duration_match = video['comparison']['duration_match'] * 100
            
            # Get thumbnail if available
            thumbnail_html = ""
            if video['original'].get('thumbnail'):
                thumbnail_html = f'<img src="{video["original"]["thumbnail"]}" alt="{video["original"]["title"]}" class="thumbnail">'
            
            # Issues section
            issues_html = ""
            if video['comparison']['issues']:
                issues_list = '<br>'.join(video['comparison']['issues'])
                issues_html = f'<div class="issues">Issues:<br>{issues_list}</div>'
            
            html_content += f"""
        <div class="video-card" data-status="{status}">
            {thumbnail_html}
            <div class="video-header">
                <div class="video-title">{video['original']['title'] or video['video_name']}</div>
                <div class="video-id">{video['video_name']}</div>
                <a href="{video['original']['youtube_url']}" target="_blank" class="youtube-link">View on YouTube →</a>
            </div>
            <div class="video-body">
                <span class="{status_class}">{status.upper()}</span>
                
                <div class="metric">
                    <span class="metric-label">Scenes Rendered:</span>
                    <span class="metric-value">{video['rendered']['scenes_rendered']} / {video['rendered']['total_scenes']}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {scene_coverage}%"></div>
                </div>
                
                <div class="metric" style="margin-top: 10px;">
                    <span class="metric-label">Duration Match:</span>
                    <span class="metric-value">{duration_match:.1f}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {duration_match}%"></div>
                </div>
                
                {issues_html}
            </div>
        </div>
"""
        
        html_content += """
    </div>
    
    <script>
        function filterVideos(status) {
            const buttons = document.querySelectorAll('.filter-button');
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            const cards = document.querySelectorAll('.video-card');
            cards.forEach(card => {
                if (status === 'all' || card.dataset.status === status) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }
    </script>
</body>
</html>
"""
        
        with open(html_file, 'w') as f:
            f.write(html_content)
            
        self.logger.info(f"Generated HTML dashboard at {html_file}")
        
    def generate_text_summary(self, report: Dict) -> str:
        """Generate a text summary of the comparison report."""
        stats = report['statistics']
        
        summary = f"""
## {report['year']} Video Recreation Status

Total Videos: {stats['total_videos']}
Successfully Recreated: {stats['fully_successful']} ({stats['fully_successful']/stats['total_videos']*100:.1f}%)
Partially Recreated: {stats['partially_successful']} ({stats['partially_successful']/stats['total_videos']*100:.1f}%)
Failed: {stats['failed']} ({stats['failed']/stats['total_videos']*100:.1f}%)
Not Processed: {stats['not_processed']}

### Fully Successful Videos:
"""
        
        # Add successful videos
        for video in sorted(report['videos'], key=lambda x: x['comparison']['scene_coverage'], reverse=True):
            if video['rendered']['status'] == 'success':
                summary += f"✓ {video['video_name']} ({video['rendered']['scenes_rendered']} scenes, {video['comparison']['duration_match']*100:.0f}% duration match)\n"
        
        summary += "\n### Partial Success:\n"
        
        # Add partial videos
        for video in sorted(report['videos'], key=lambda x: x['comparison']['scene_coverage'], reverse=True):
            if video['rendered']['status'] == 'partial':
                summary += f"⚠ {video['video_name']} ({video['rendered']['scenes_rendered']}/{video['rendered']['total_scenes']} scenes, {video['comparison']['scene_coverage']*100:.0f}% coverage)\n"
                if video['comparison']['issues']:
                    for issue in video['comparison']['issues']:
                        summary += f"  - {issue}\n"
        
        summary += "\n### Failed Videos:\n"
        
        # Add failed videos
        for video in report['videos']:
            if video['rendered']['status'] == 'failed':
                summary += f"✗ {video['video_name']} (0/{video['rendered']['total_scenes']} scenes rendered)\n"
                if video['comparison']['issues']:
                    for issue in video['comparison']['issues']:
                        summary += f"  - {issue}\n"
        
        return summary


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate comparison reports between YouTube and rendered videos'
    )
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create report generator
    base_dir = Path(__file__).parent.parent
    generator = ComparisonReportGenerator(base_dir, verbose=args.verbose)
    
    # Generate comparison report
    report = generator.generate_year_comparison(args.year)
    
    if report:
        # Print text summary
        summary = generator.generate_text_summary(report)
        print(summary)
        
        # Save text summary
        comparison_year_dir = generator.comparison_dir / str(args.year)
        summary_file = comparison_year_dir / 'comparison_summary.txt'
        with open(summary_file, 'w') as f:
            f.write(summary)
            
        print(f"\nComparison reports saved to: {comparison_year_dir}")
        print(f"View the dashboard at: {comparison_year_dir / 'comparison_dashboard.html'}")


if __name__ == '__main__':
    main()