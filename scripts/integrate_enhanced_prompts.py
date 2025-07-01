#!/usr/bin/env python3
"""
Integration module to seamlessly upgrade the existing pipeline to use enhanced prompts.
This can be imported at the beginning of build_dataset_pipeline.py to upgrade the components.
"""

import sys
from pathlib import Path
from typing import Any

# Import the enhanced versions
from claude_match_videos_enhanced import EnhancedClaudeVideoMatcher
from clean_matched_code_enhanced import EnhancedCodeCleaner

# Import optimization modules
from adaptive_prompt_optimizer import AdaptivePromptOptimizer
from prompt_feedback_system import PromptFeedbackSystem

def monkey_patch_pipeline_components():
    """
    Monkey patch the existing pipeline to use enhanced components.
    This allows us to upgrade without modifying the main pipeline code.
    """
    # Replace the imported classes in the main module
    if 'build_dataset_pipeline' in sys.modules:
        pipeline_module = sys.modules['build_dataset_pipeline']
        
        # Replace ClaudeVideoMatcher with EnhancedClaudeVideoMatcher
        if hasattr(pipeline_module, 'ClaudeVideoMatcher'):
            pipeline_module.ClaudeVideoMatcher = EnhancedClaudeVideoMatcher
            print("✅ Upgraded ClaudeVideoMatcher to enhanced version")
        
        # For hybrid cleaner, we need to patch the underlying CodeCleaner
        if 'clean_matched_code' in sys.modules:
            clean_module = sys.modules['clean_matched_code']
            clean_module.CodeCleaner = EnhancedCodeCleaner
            print("✅ Upgraded CodeCleaner to enhanced version")

def integrate_enhanced_pipeline(builder_instance):
    """
    Integrate enhanced components into an existing DatasetPipelineBuilder instance.
    This modifies the instance to use our enhanced components.
    """
    base_dir = builder_instance.base_dir
    verbose = builder_instance.verbose
    
    # Create shared optimization instances
    optimizer = AdaptivePromptOptimizer(
        cache_dir=str(builder_instance.output_dir / 'prompt_optimization')
    )
    feedback_system = PromptFeedbackSystem(
        feedback_dir=str(builder_instance.output_dir / 'prompt_feedback')
    )
    
    # Replace the matcher with enhanced version
    builder_instance.matcher = EnhancedClaudeVideoMatcher(base_dir, verbose)
    
    # For the cleaner, we need to replace the underlying CodeCleaner
    # if it's using HybridCleaner
    if hasattr(builder_instance.cleaner, 'code_cleaner'):
        # HybridCleaner has a code_cleaner attribute
        builder_instance.cleaner.code_cleaner = EnhancedCodeCleaner(
            base_dir, 
            verbose,
            timeout_multiplier=builder_instance.timeout_multiplier,
            max_retries=builder_instance.max_retries
        )
    else:
        # Direct replacement
        builder_instance.cleaner = EnhancedCodeCleaner(
            base_dir,
            verbose, 
            timeout_multiplier=builder_instance.timeout_multiplier,
            max_retries=builder_instance.max_retries
        )
    
    print("✅ Pipeline components upgraded to enhanced versions with prompt optimization")
    
    # Add method to generate consolidated optimization report
    def generate_optimization_report(self):
        """Generate a consolidated optimization report for all stages."""
        report_lines = [
            "# Pipeline Optimization Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        # Add matching optimization insights
        if hasattr(self.matcher, 'optimizer'):
            report_lines.append("## Matching Stage Optimization")
            report_lines.append(self.matcher.optimizer.generate_optimization_report())
            report_lines.append("")
        
        # Add cleaning optimization insights
        if hasattr(self.cleaner, 'optimizer'):
            report_lines.append("## Cleaning Stage Optimization")
            report_lines.append(self.cleaner.optimizer.generate_optimization_report())
            report_lines.append("")
        
        # Add feedback system reports
        if hasattr(self.matcher, 'feedback_system'):
            report_lines.append("## Matching Stage Performance")
            report_lines.append(self.matcher.feedback_system.generate_report())
            report_lines.append("")
        
        if hasattr(self.cleaner, 'feedback_system'):
            report_lines.append("## Cleaning Stage Performance")
            report_lines.append(self.cleaner.feedback_system.generate_report())
            report_lines.append("")
        
        return '\n'.join(report_lines)
    
    # Bind the method to the instance
    builder_instance.generate_optimization_report = generate_optimization_report.__get__(
        builder_instance, builder_instance.__class__
    )
    
    return builder_instance

def enhance_existing_pipeline():
    """
    Enhance the existing pipeline by patching the imports.
    Call this before creating DatasetPipelineBuilder instances.
    """
    # First, try monkey patching
    monkey_patch_pipeline_components()
    
    # Also provide a decorator for DatasetPipelineBuilder
    original_init = None
    
    if 'build_dataset_pipeline' in sys.modules:
        pipeline_module = sys.modules['build_dataset_pipeline']
        if hasattr(pipeline_module, 'DatasetPipelineBuilder'):
            DatasetPipelineBuilder = pipeline_module.DatasetPipelineBuilder
            original_init = DatasetPipelineBuilder.__init__
            
            def enhanced_init(self, *args, **kwargs):
                # Call original init
                original_init(self, *args, **kwargs)
                # Enhance the instance
                integrate_enhanced_pipeline(self)
            
            DatasetPipelineBuilder.__init__ = enhanced_init
            print("✅ DatasetPipelineBuilder enhanced with prompt optimization")

# Auto-enhance on import
enhance_existing_pipeline()

# Provide explicit integration function for manual use
def upgrade_pipeline_to_enhanced(base_dir: str = None):
    """
    Explicitly upgrade the pipeline to use enhanced components.
    
    Usage:
        from integrate_enhanced_prompts import upgrade_pipeline_to_enhanced
        upgrade_pipeline_to_enhanced()
        
        # Then use the pipeline normally
        from build_dataset_pipeline import DatasetPipelineBuilder
        builder = DatasetPipelineBuilder(...)
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent
    
    # Import and patch the modules
    import claude_match_videos
    import clean_matched_code
    
    # Replace the classes
    claude_match_videos.ClaudeVideoMatcher = EnhancedClaudeVideoMatcher
    clean_matched_code.CodeCleaner = EnhancedCodeCleaner
    
    # If modules are already loaded, patch them too
    enhance_existing_pipeline()
    
    print("✅ Pipeline upgraded to use enhanced prompt optimization")
    print("   - Adaptive learning enabled")
    print("   - Few-shot examples in prompts")
    print("   - Performance tracking enabled")
    print("   - Optimization reports will be generated")

if __name__ == "__main__":
    # Test the integration
    print("Testing enhanced prompt integration...")
    
    # Test importing and patching
    upgrade_pipeline_to_enhanced()
    
    # Verify classes are replaced
    import claude_match_videos
    import clean_matched_code
    
    assert claude_match_videos.ClaudeVideoMatcher == EnhancedClaudeVideoMatcher
    assert clean_matched_code.CodeCleaner == EnhancedCodeCleaner
    
    print("✅ Integration test passed!")