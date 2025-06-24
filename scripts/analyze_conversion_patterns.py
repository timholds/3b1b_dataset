#!/usr/bin/env python3
"""
Analyze conversion patterns from collected errors.

This script analyzes the error database to identify common patterns,
generate insights, and create actionable recommendations for improving
the conversion process.
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from conversion_error_collector import ConversionErrorCollector


class ConversionPatternAnalyzer:
    """Analyzes conversion error patterns and generates insights."""
    
    def __init__(self, database_path: Optional[Path] = None):
        """Initialize the analyzer with error database."""
        self.collector = ConversionErrorCollector(database_path)
        self.patterns = self.collector.get_error_patterns()
        
    def analyze_error_trends(self) -> Dict[str, List[Tuple[str, int]]]:
        """Analyze error trends over time."""
        # Group errors by date
        errors_by_date = defaultdict(lambda: Counter())
        
        for error in self.collector.error_db['errors']:
            if 'timestamp' in error:
                date = error['timestamp'][:10]  # Extract date portion
                category = error['category']
                errors_by_date[date][category] += error.get('occurrences', 1)
        
        # Convert to sorted lists
        trends = {}
        for category in self.patterns.keys():
            trend_data = []
            for date in sorted(errors_by_date.keys()):
                count = errors_by_date[date].get(category, 0)
                trend_data.append((date, count))
            trends[category] = trend_data
        
        return trends
    
    def identify_fix_patterns(self) -> Dict[str, List[Dict]]:
        """Identify successful fix patterns for each error category."""
        fix_patterns = defaultdict(list)
        
        # Analyze successful fixes
        for fix in self.collector.error_db['fixes']:
            if fix['success']:
                category = fix['error_category']
                
                # Find similar successful fixes
                pattern = {
                    'description': fix['description'],
                    'type': fix['fix_type'],
                    'code_pattern': self._extract_code_pattern(fix.get('fixed_code_snippet', '')),
                    'count': 1
                }
                
                # Check if pattern already exists
                found = False
                for existing in fix_patterns[category]:
                    if existing['description'] == pattern['description']:
                        existing['count'] += 1
                        found = True
                        break
                
                if not found:
                    fix_patterns[category].append(pattern)
        
        # Sort by frequency
        for category in fix_patterns:
            fix_patterns[category].sort(key=lambda x: x['count'], reverse=True)
        
        return dict(fix_patterns)
    
    def _extract_code_pattern(self, code: str) -> str:
        """Extract a generalized pattern from code snippet."""
        if not code:
            return ""
        
        # Simple pattern extraction - can be made more sophisticated
        patterns = []
        
        if 'Create(' in code and 'ShowCreation(' not in code:
            patterns.append("ShowCreation -> Create")
        if 'Text(' in code and 'TextMobject(' not in code:
            patterns.append("TextMobject -> Text")
        if 'MathTex(' in code and 'TexMobject(' not in code:
            patterns.append("TexMobject -> MathTex")
        if 'from manim import' in code:
            patterns.append("Updated imports")
        if '.add_updater(' in code:
            patterns.append("ContinualAnimation -> updater")
        
        return ", ".join(patterns) if patterns else "Custom fix"
    
    def generate_conversion_rules(self) -> List[Dict[str, str]]:
        """Generate conversion rules based on successful fixes."""
        rules = []
        fix_patterns = self.identify_fix_patterns()
        
        # Create rules from most successful patterns
        for category, patterns in fix_patterns.items():
            for pattern in patterns[:3]:  # Top 3 patterns per category
                if pattern['count'] >= 2:  # At least 2 occurrences
                    rule = {
                        'category': category,
                        'pattern': pattern['code_pattern'],
                        'description': pattern['description'],
                        'frequency': pattern['count'],
                        'confidence': min(0.9, pattern['count'] / 10.0)  # Cap at 0.9
                    }
                    rules.append(rule)
        
        # Sort by confidence and frequency
        rules.sort(key=lambda x: (x['confidence'], x['frequency']), reverse=True)
        
        return rules
    
    def analyze_problem_files(self) -> List[Dict]:
        """Identify files with the most conversion issues."""
        file_errors = defaultdict(lambda: {
            'error_count': 0,
            'categories': Counter(),
            'fixed_count': 0,
            'error_ids': []
        })
        
        for error in self.collector.error_db['errors']:
            file_path = error['file_path']
            file_errors[file_path]['error_count'] += error.get('occurrences', 1)
            file_errors[file_path]['categories'][error['category']] += 1
            file_errors[file_path]['error_ids'].append(error['id'])
            if error['fixed']:
                file_errors[file_path]['fixed_count'] += 1
        
        # Convert to list and calculate fix rate
        problem_files = []
        for file_path, data in file_errors.items():
            fix_rate = data['fixed_count'] / data['error_count'] if data['error_count'] > 0 else 0
            problem_files.append({
                'file': file_path,
                'error_count': data['error_count'],
                'fix_rate': fix_rate,
                'main_category': data['categories'].most_common(1)[0][0] if data['categories'] else 'unknown',
                'categories': dict(data['categories'])
            })
        
        # Sort by error count
        problem_files.sort(key=lambda x: x['error_count'], reverse=True)
        
        return problem_files
    
    def generate_recommendations(self) -> List[Dict[str, str]]:
        """Generate specific recommendations for improving conversion."""
        recommendations = []
        
        # Analyze patterns
        for category, data in self.patterns.items():
            if data['count'] > 5:  # Significant number of errors
                if data['success_rate'] < 50:
                    rec = {
                        'priority': 'HIGH',
                        'category': category,
                        'issue': f"Low fix success rate ({data['success_rate']:.1f}%) for {category}",
                        'recommendation': self._get_category_recommendation(category, data),
                        'impact': f"Could fix ~{int(data['count'] * 0.7)} errors"
                    }
                    recommendations.append(rec)
                
                # Check for common items
                if data['most_common_items']:
                    for item in data['most_common_items'][:2]:
                        rec = {
                            'priority': 'MEDIUM',
                            'category': category,
                            'issue': f"Frequent {category} with '{item}'",
                            'recommendation': self._get_item_recommendation(category, item),
                            'impact': f"Addresses common pattern"
                        }
                        recommendations.append(rec)
        
        # Sort by priority
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return recommendations
    
    def _get_category_recommendation(self, category: str, data: Dict) -> str:
        """Get recommendation for a specific error category."""
        recommendations = {
            'import_error': "Add comprehensive import mapping and pre-import validation",
            'name_error': "Implement name resolution and undefined identifier detection",
            'attribute_error': "Create method/attribute migration mapping",
            'animation_error': "Enhance animation conversion rules in ANIMATION_MAPPINGS",
            'pi_creature_error': "Improve Pi Creature detection and alternative suggestions",
            'config_error': "Add CONFIG to __init__ parameter conversion",
            'color_constant_error': "Update color constant mappings",
            'method_not_found': "Expand method conversion mappings"
        }
        return recommendations.get(category, "Add specific handling for this error type")
    
    def _get_item_recommendation(self, category: str, item: str) -> str:
        """Get recommendation for a specific problematic item."""
        # Specific recommendations for known items
        item_recs = {
            'ShowCreation': "Add to import mappings: ShowCreation -> Create",
            'TextMobject': "Add to class mappings: TextMobject -> Text",
            'COLOR_MAP': "Add to color mappings: COLOR_MAP -> MANIM_COLORS",
            'ContinualAnimation': "Implement ContinualAnimation to add_updater converter",
            'get_center': "Verify get_center() method compatibility",
            'CONFIG': "Implement CONFIG dictionary converter"
        }
        
        if item in item_recs:
            return item_recs[item]
        
        # Generic recommendations by category
        if category == 'import_error':
            return f"Add '{item}' to import resolution or provide ManimCE equivalent"
        elif category == 'name_error':
            return f"Define '{item}' or map to ManimCE equivalent"
        elif category == 'attribute_error':
            return f"Add method/attribute mapping for '{item}'"
        
        return f"Add specific handling for '{item}'"
    
    def create_visualization(self, output_path: Path):
        """Create visualization of error patterns."""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('ManimGL to ManimCE Conversion Error Analysis', fontsize=16)
        
        # 1. Error distribution by category
        categories = list(self.patterns.keys())
        counts = [self.patterns[cat]['count'] for cat in categories]
        colors = plt.cm.Set3(range(len(categories)))
        
        ax1.bar(categories, counts, color=colors)
        ax1.set_xlabel('Error Category')
        ax1.set_ylabel('Count')
        ax1.set_title('Error Distribution by Category')
        ax1.tick_params(axis='x', rotation=45)
        
        # 2. Fix success rates
        success_rates = [self.patterns[cat]['success_rate'] for cat in categories]
        ax2.bar(categories, success_rates, color=colors)
        ax2.set_xlabel('Error Category')
        ax2.set_ylabel('Success Rate (%)')
        ax2.set_title('Fix Success Rates by Category')
        ax2.tick_params(axis='x', rotation=45)
        ax2.axhline(y=50, color='r', linestyle='--', alpha=0.5)
        
        # 3. Top problem files
        problem_files = self.analyze_problem_files()[:10]
        if problem_files:
            file_names = [Path(f['file']).stem[:20] for f in problem_files]
            error_counts = [f['error_count'] for f in problem_files]
            
            ax3.barh(file_names, error_counts, color='coral')
            ax3.set_xlabel('Error Count')
            ax3.set_title('Top 10 Problem Files')
        
        # 4. Recommendations summary
        recommendations = self.generate_recommendations()[:5]
        ax4.axis('off')
        ax4.set_title('Top Recommendations')
        
        y_pos = 0.9
        for i, rec in enumerate(recommendations):
            color = 'red' if rec['priority'] == 'HIGH' else 'orange'
            ax4.text(0.05, y_pos - i*0.15, f"• [{rec['priority']}] {rec['issue']}", 
                    fontsize=10, weight='bold', color=color)
            ax4.text(0.05, y_pos - i*0.15 - 0.05, f"  → {rec['recommendation'][:60]}...", 
                    fontsize=9)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def generate_report(self) -> str:
        """Generate comprehensive analysis report."""
        report = "# ManimGL to ManimCE Conversion Pattern Analysis\n\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Summary statistics
        total_errors = self.collector.error_db['statistics']['total_errors']
        total_fixes = self.collector.error_db['statistics']['total_fixes']
        overall_success = (total_fixes / total_errors * 100) if total_errors > 0 else 0
        
        report += "## Summary Statistics\n\n"
        report += f"- Total errors collected: {total_errors}\n"
        report += f"- Total fix attempts: {total_fixes}\n"
        report += f"- Overall success rate: {overall_success:.1f}%\n\n"
        
        # Error patterns
        report += "## Error Patterns by Category\n\n"
        for category, data in sorted(self.patterns.items(), 
                                   key=lambda x: x[1]['count'], 
                                   reverse=True):
            report += f"### {category.replace('_', ' ').title()}\n"
            report += f"- **Count**: {data['count']}\n"
            report += f"- **Success Rate**: {data['success_rate']:.1f}%\n"
            
            if data['most_common_items']:
                report += f"- **Most Common**: {', '.join(data['most_common_items'][:5])}\n"
            
            report += "\n"
        
        # Conversion rules
        report += "## Recommended Conversion Rules\n\n"
        rules = self.generate_conversion_rules()
        for i, rule in enumerate(rules[:10], 1):
            report += f"{i}. **{rule['pattern']}** (confidence: {rule['confidence']:.2f})\n"
            report += f"   - Category: {rule['category']}\n"
            report += f"   - Used {rule['frequency']} times successfully\n\n"
        
        # Problem files
        report += "## Most Problematic Files\n\n"
        problem_files = self.analyze_problem_files()[:10]
        for i, file_info in enumerate(problem_files, 1):
            report += f"{i}. `{file_info['file']}`\n"
            report += f"   - Errors: {file_info['error_count']}\n"
            report += f"   - Fix rate: {file_info['fix_rate']*100:.1f}%\n"
            report += f"   - Main issue: {file_info['main_category']}\n\n"
        
        # Recommendations
        report += "## Recommendations for Improvement\n\n"
        recommendations = self.generate_recommendations()
        for rec in recommendations:
            report += f"### [{rec['priority']}] {rec['issue']}\n"
            report += f"**Recommendation**: {rec['recommendation']}\n"
            report += f"**Expected Impact**: {rec['impact']}\n\n"
        
        # Fix patterns
        report += "## Successful Fix Patterns\n\n"
        fix_patterns = self.identify_fix_patterns()
        for category, patterns in fix_patterns.items():
            if patterns:
                report += f"### {category.replace('_', ' ').title()}\n"
                for pattern in patterns[:3]:
                    report += f"- {pattern['description']} ({pattern['count']} times)\n"
                report += "\n"
        
        return report


def main():
    """Main entry point for pattern analysis."""
    parser = argparse.ArgumentParser(
        description='Analyze ManimGL to ManimCE conversion error patterns'
    )
    parser.add_argument('--database', type=str, 
                       help='Path to error database (default: outputs/conversion_errors_db.json)')
    parser.add_argument('--output-dir', type=str, default='outputs/analysis',
                       help='Output directory for reports and visualizations')
    parser.add_argument('--no-viz', action='store_true',
                       help='Skip visualization generation')
    
    args = parser.parse_args()
    
    # Create analyzer
    db_path = Path(args.database) if args.database else None
    analyzer = ConversionPatternAnalyzer(db_path)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate report
    print("Generating analysis report...")
    report = analyzer.generate_report()
    report_path = output_dir / f'conversion_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md'
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"Report saved to: {report_path}")
    
    # Generate visualization
    if not args.no_viz:
        print("Creating visualization...")
        viz_path = output_dir / f'conversion_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        analyzer.create_visualization(viz_path)
        print(f"Visualization saved to: {viz_path}")
    
    # Print summary
    print("\n" + analyzer.collector.generate_error_summary())
    
    # Print top recommendations
    print("\nTop Recommendations:")
    recommendations = analyzer.generate_recommendations()[:5]
    for rec in recommendations:
        print(f"- [{rec['priority']}] {rec['issue']}")
        print(f"  → {rec['recommendation']}")


if __name__ == "__main__":
    main()