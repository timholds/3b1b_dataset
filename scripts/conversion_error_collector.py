#!/usr/bin/env python3
"""
Conversion Error Collector for ManimGL to ManimCE conversion.

This module provides a centralized system for collecting, storing, and analyzing
compilation errors that occur during the conversion process. It helps identify
patterns and improve conversion accuracy over time.
"""

import json
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict, Counter
import logging

logger = logging.getLogger(__name__)


class ConversionErrorCollector:
    """Collects and analyzes conversion errors to improve future conversions."""
    
    def __init__(self, database_path: Optional[Path] = None):
        """Initialize the error collector with a database path."""
        if database_path is None:
            database_path = Path(__file__).parent.parent / 'outputs' / 'conversion_errors_db.json'
        
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing database or create new one
        self.error_db = self._load_database()
        
        # Error categorization patterns
        self.error_categories = {
            'import_error': [
                r"ImportError.*'(\w+)'",
                r"cannot import name '(\w+)'",
                r"No module named '(\w+)'",
            ],
            'name_error': [
                r"NameError.*'(\w+)' is not defined",
                r"name '(\w+)' is not defined",
            ],
            'attribute_error': [
                r"AttributeError.*'(\w+)' object has no attribute '(\w+)'",
                r"'(\w+)' has no attribute '(\w+)'",
            ],
            'type_error': [
                r"TypeError.*(\w+)\(\) takes",
                r"TypeError.*missing \d+ required positional argument",
                r"TypeError.*unexpected keyword argument",
            ],
            'syntax_error': [
                r"SyntaxError: (.+)",
                r"IndentationError: (.+)",
            ],
            'animation_error': [
                r".*Animation.*not found",
                r".*ShowCreation.*",
                r".*ContinualAnimation.*",
            ],
            'color_constant_error': [
                r".*COLOR_MAP.*",
                r".*color.*not defined",
            ],
            'method_not_found': [
                r".*has no attribute '(get_\w+|set_\w+)'",
                r".*method.*not found",
            ],
            'config_error': [
                r".*CONFIG.*",
                r".*config.*error",
            ],
            'pi_creature_error': [
                r".*PiCreature.*",
                r".*Randolph.*",
                r".*Mortimer.*",
            ]
        }
        
    def _load_database(self) -> Dict[str, Any]:
        """Load the error database from disk."""
        if self.database_path.exists():
            try:
                with open(self.database_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load error database: {e}")
                return self._create_empty_database()
        return self._create_empty_database()
    
    def _create_empty_database(self) -> Dict[str, Any]:
        """Create an empty error database structure."""
        return {
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'errors': [],
            'fixes': [],
            'patterns': {},
            'statistics': {
                'total_errors': 0,
                'total_fixes': 0,
                'error_by_category': {},
                'fix_success_rate': {}
            }
        }
    
    def _save_database(self):
        """Save the error database to disk."""
        self.error_db['last_updated'] = datetime.now().isoformat()
        with open(self.database_path, 'w') as f:
            json.dump(self.error_db, f, indent=2)
    
    def _categorize_error(self, error_message: str) -> Tuple[str, Optional[str]]:
        """Categorize an error message and extract key information."""
        for category, patterns in self.error_categories.items():
            for pattern in patterns:
                match = re.search(pattern, error_message, re.IGNORECASE)
                if match:
                    key_info = match.group(1) if match.groups() else None
                    return category, key_info
        return 'unknown', None
    
    def _generate_error_hash(self, error_data: Dict) -> str:
        """Generate a hash for an error to identify duplicates."""
        # Create a canonical representation
        canonical = f"{error_data['category']}:{error_data.get('key_info', '')}:{error_data.get('line_number', '')}"
        return hashlib.md5(canonical.encode()).hexdigest()[:8]
    
    def collect_error(self, 
                     file_path: str,
                     error_message: str,
                     error_type: str,
                     line_number: Optional[int] = None,
                     code_context: Optional[str] = None,
                     original_code: Optional[str] = None,
                     converted_code: Optional[str] = None) -> str:
        """
        Collect a conversion error and store it in the database.
        
        Returns: error_id for reference
        """
        # Categorize the error
        category, key_info = self._categorize_error(error_message)
        
        # Create error entry
        error_entry = {
            'id': len(self.error_db['errors']) + 1,
            'timestamp': datetime.now().isoformat(),
            'file_path': file_path,
            'error_type': error_type,
            'category': category,
            'key_info': key_info,
            'message': error_message,
            'line_number': line_number,
            'code_context': code_context,
            'original_code_snippet': original_code[:500] if original_code else None,
            'converted_code_snippet': converted_code[:500] if converted_code else None,
            'hash': None,
            'fix_attempts': 0,
            'fixed': False,
            'fix_id': None
        }
        
        # Generate hash
        error_entry['hash'] = self._generate_error_hash(error_entry)
        
        # Check if similar error exists
        similar_errors = [e for e in self.error_db['errors'] if e['hash'] == error_entry['hash']]
        if similar_errors:
            # Update occurrence count
            similar_errors[0]['occurrences'] = similar_errors[0].get('occurrences', 1) + 1
            similar_errors[0]['last_seen'] = datetime.now().isoformat()
            error_id = similar_errors[0]['id']
        else:
            # Add new error
            error_entry['occurrences'] = 1
            self.error_db['errors'].append(error_entry)
            error_id = error_entry['id']
        
        # Update statistics
        self.error_db['statistics']['total_errors'] += 1
        cat_stats = self.error_db['statistics']['error_by_category']
        cat_stats[category] = cat_stats.get(category, 0) + 1
        
        self._save_database()
        return str(error_id)
    
    def collect_fix(self,
                   error_id: str,
                   fix_description: str,
                   fixed_code: str,
                   success: bool,
                   fix_type: str = 'manual',
                   additional_info: Optional[Dict] = None) -> str:
        """
        Collect information about a fix attempt for an error.
        
        Returns: fix_id for reference
        """
        # Find the error
        error = next((e for e in self.error_db['errors'] if str(e['id']) == str(error_id)), None)
        if not error:
            logger.warning(f"Error ID {error_id} not found")
            return ""
        
        # Create fix entry
        fix_entry = {
            'id': len(self.error_db['fixes']) + 1,
            'error_id': error_id,
            'timestamp': datetime.now().isoformat(),
            'description': fix_description,
            'fixed_code_snippet': fixed_code[:500] if len(fixed_code) > 500 else fixed_code,
            'success': success,
            'fix_type': fix_type,  # 'manual', 'claude', 'automated'
            'error_category': error['category'],
            'additional_info': additional_info or {}
        }
        
        # Add fix
        self.error_db['fixes'].append(fix_entry)
        fix_id = fix_entry['id']
        
        # Update error entry
        error['fix_attempts'] += 1
        if success:
            error['fixed'] = True
            error['fix_id'] = fix_id
        
        # Update statistics
        self.error_db['statistics']['total_fixes'] += 1
        if success:
            cat = error['category']
            success_stats = self.error_db['statistics']['fix_success_rate']
            if cat not in success_stats:
                success_stats[cat] = {'attempts': 0, 'successes': 0}
            success_stats[cat]['attempts'] += 1
            success_stats[cat]['successes'] += 1
        
        self._save_database()
        return str(fix_id)
    
    def get_similar_errors(self, error_message: str, limit: int = 5) -> List[Dict]:
        """Find similar errors that have been successfully fixed."""
        category, key_info = self._categorize_error(error_message)
        
        # Find errors in same category that have been fixed
        similar_errors = []
        for error in self.error_db['errors']:
            if (error['category'] == category and 
                error['fixed'] and 
                error.get('key_info') == key_info):
                # Get the fix
                fix = next((f for f in self.error_db['fixes'] 
                          if str(f['id']) == str(error['fix_id'])), None)
                if fix:
                    similar_errors.append({
                        'error': error,
                        'fix': fix
                    })
        
        # Sort by occurrence count (most common first)
        similar_errors.sort(key=lambda x: x['error'].get('occurrences', 1), reverse=True)
        
        return similar_errors[:limit]
    
    def get_error_patterns(self) -> Dict[str, Any]:
        """Analyze and return common error patterns."""
        patterns = defaultdict(lambda: {
            'count': 0,
            'fixed_count': 0,
            'common_fixes': [],
            'key_items': Counter()
        })
        
        # Analyze errors
        for error in self.error_db['errors']:
            cat = error['category']
            patterns[cat]['count'] += error.get('occurrences', 1)
            if error['fixed']:
                patterns[cat]['fixed_count'] += 1
            if error.get('key_info'):
                patterns[cat]['key_items'][error['key_info']] += 1
        
        # Analyze fixes
        for fix in self.error_db['fixes']:
            if fix['success']:
                cat = fix['error_category']
                patterns[cat]['common_fixes'].append({
                    'description': fix['description'],
                    'type': fix['fix_type']
                })
        
        # Convert to regular dict and add success rates
        result = {}
        for cat, data in patterns.items():
            result[cat] = dict(data)
            result[cat]['success_rate'] = (
                data['fixed_count'] / data['count'] * 100 
                if data['count'] > 0 else 0
            )
            # Get most common key items
            result[cat]['most_common_items'] = [
                item for item, count in data['key_items'].most_common(5)
            ]
        
        return result
    
    def generate_error_summary(self) -> str:
        """Generate a human-readable summary of error patterns."""
        patterns = self.get_error_patterns()
        
        summary = "# Conversion Error Summary\n\n"
        summary += f"Total errors collected: {self.error_db['statistics']['total_errors']}\n"
        summary += f"Total fix attempts: {self.error_db['statistics']['total_fixes']}\n\n"
        
        summary += "## Error Categories\n\n"
        for category, data in sorted(patterns.items(), 
                                   key=lambda x: x[1]['count'], 
                                   reverse=True):
            summary += f"### {category.replace('_', ' ').title()}\n"
            summary += f"- Count: {data['count']}\n"
            summary += f"- Fixed: {data['fixed_count']} ({data['success_rate']:.1f}%)\n"
            
            if data['most_common_items']:
                summary += f"- Most common: {', '.join(data['most_common_items'][:3])}\n"
            
            if data['common_fixes']:
                summary += "- Common fixes:\n"
                # Get unique fix descriptions
                unique_fixes = list({f['description'] for f in data['common_fixes']})[:3]
                for fix in unique_fixes:
                    summary += f"  - {fix}\n"
            
            summary += "\n"
        
        return summary
    
    def get_fix_suggestions(self, error_message: str, code_context: str = "") -> List[Dict]:
        """Get fix suggestions based on historical data."""
        similar_errors = self.get_similar_errors(error_message, limit=10)
        category, key_info = self._categorize_error(error_message)
        
        suggestions = []
        
        # Add suggestions from similar errors
        for item in similar_errors:
            suggestions.append({
                'source': 'similar_error',
                'confidence': 0.9,
                'description': item['fix']['description'],
                'code_snippet': item['fix'].get('fixed_code_snippet', ''),
                'fix_type': item['fix']['fix_type']
            })
        
        # Add category-specific suggestions
        if category == 'import_error' and key_info:
            if key_info in ['ShowCreation', 'ShowCreationThenDestruction']:
                suggestions.append({
                    'source': 'known_pattern',
                    'confidence': 0.95,
                    'description': f"Replace {key_info} with Create",
                    'code_snippet': "from manim import Create",
                    'fix_type': 'automated'
                })
            elif key_info == 'TextMobject':
                suggestions.append({
                    'source': 'known_pattern',
                    'confidence': 0.95,
                    'description': "Replace TextMobject with Text",
                    'code_snippet': "from manim import Text",
                    'fix_type': 'automated'
                })
        
        elif category == 'name_error' and key_info:
            if key_info in ['COLOR_MAP', 'LIGHT_GRAY', 'DARK_GRAY']:
                suggestions.append({
                    'source': 'known_pattern',
                    'confidence': 0.9,
                    'description': f"Update color constant {key_info}",
                    'code_snippet': self._get_color_fix(key_info),
                    'fix_type': 'automated'
                })
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        
        return suggestions[:5]
    
    def _get_color_fix(self, color_name: str) -> str:
        """Get the fix for a color constant."""
        color_fixes = {
            'COLOR_MAP': 'MANIM_COLORS',
            'LIGHT_GRAY': 'LIGHT_GREY',
            'DARK_GRAY': 'DARK_GREY',
            'GRAY': 'GREY'
        }
        return color_fixes.get(color_name, color_name)


# Convenience functions for use in conversion scripts
_collector = None

def get_error_collector() -> ConversionErrorCollector:
    """Get the global error collector instance."""
    global _collector
    if _collector is None:
        _collector = ConversionErrorCollector()
    return _collector


def collect_conversion_error(file_path: str, 
                           error_message: str,
                           error_type: str = "render_error",
                           **kwargs) -> str:
    """Convenience function to collect an error."""
    collector = get_error_collector()
    return collector.collect_error(file_path, error_message, error_type, **kwargs)


def collect_conversion_fix(error_id: str,
                         fix_description: str,
                         fixed_code: str,
                         success: bool,
                         **kwargs) -> str:
    """Convenience function to collect a fix."""
    collector = get_error_collector()
    return collector.collect_fix(error_id, fix_description, fixed_code, success, **kwargs)


def get_fix_suggestions_for_error(error_message: str, 
                                code_context: str = "") -> List[Dict]:
    """Get fix suggestions for an error."""
    collector = get_error_collector()
    return collector.get_fix_suggestions(error_message, code_context)


if __name__ == "__main__":
    # Test the error collector
    collector = ConversionErrorCollector()
    
    # Test collecting an error
    error_id = collector.collect_error(
        file_path="test.py",
        error_message="NameError: name 'ShowCreation' is not defined",
        error_type="NameError",
        line_number=42,
        code_context="self.play(ShowCreation(circle))"
    )
    
    print(f"Collected error with ID: {error_id}")
    
    # Test collecting a fix
    fix_id = collector.collect_fix(
        error_id=error_id,
        fix_description="Replace ShowCreation with Create",
        fixed_code="self.play(Create(circle))",
        success=True,
        fix_type="automated"
    )
    
    print(f"Collected fix with ID: {fix_id}")
    
    # Get suggestions
    suggestions = collector.get_fix_suggestions("NameError: name 'ShowCreation' is not defined")
    print(f"\nFix suggestions:")
    for s in suggestions:
        print(f"- {s['description']} (confidence: {s['confidence']})")
    
    # Print summary
    print("\n" + collector.generate_error_summary())