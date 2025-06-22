#!/usr/bin/env python3
"""
Example integration of quality checks into the extraction pipeline
This shows how to modify your existing extraction process to include quality validation
"""

import json
import shutil
from pathlib import Path
from quality_checker import ManimCodeQualityChecker


class ExtractionPipelineWithQualityChecks:
    """Enhanced extraction pipeline with integrated quality checks"""
    
    def __init__(self, output_dir="output_v5"):
        self.output_dir = Path(output_dir)
        self.quality_checker = ManimCodeQualityChecker()
        self.extraction_stats = {
            "total_processed": 0,
            "passed_quality": 0,
            "failed_quality": 0,
            "excluded": 0
        }
    
    def process_video(self, year, video_name, source_files, metadata):
        """Process a single video with quality checks"""
        
        # Create output directory
        video_dir = self.output_dir / str(year) / video_name
        video_dir.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Inline the code (your existing inlining process)
        inlined_code = self.inline_code(source_files)  # Your existing method
        
        # Step 2: Run quality checks
        quality_report = self.quality_checker.check_code(
            inlined_code, 
            f"{year}/{video_name}/code.py",
            metadata
        )
        
        # Step 3: Decide whether to include based on quality
        if quality_report.quality_score == "FAIL":
            print(f"⚠️  {video_name}: FAILED quality checks")
            
            # Save failed file to a separate directory for manual review
            failed_dir = self.output_dir / "failed_quality" / str(year) / video_name
            failed_dir.mkdir(parents=True, exist_ok=True)
            
            # Save the problematic code
            with open(failed_dir / "code.py", 'w') as f:
                f.write(inlined_code)
            
            # Save quality report
            with open(failed_dir / "quality_report.json", 'w') as f:
                json.dump(quality_report.to_dict(), f, indent=2)
            
            # Update metadata to mark as excluded
            metadata["excluded"] = True
            metadata["exclusion_reason"] = "failed_quality_checks"
            metadata["quality_issues"] = quality_report.checks
            
            self.extraction_stats["failed_quality"] += 1
            
        else:
            # File passed or has only warnings
            print(f"✅ {video_name}: {quality_report.quality_score}")
            
            # Save the code
            with open(video_dir / "code.py", 'w') as f:
                f.write(inlined_code)
            
            # Add quality info to metadata
            metadata["quality_score"] = quality_report.quality_score
            metadata["quality_warnings"] = quality_report.warnings
            
            self.extraction_stats["passed_quality"] += 1
        
        # Save metadata
        with open(video_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save quality report for all files
        with open(video_dir / "quality_report.json", 'w') as f:
            json.dump(quality_report.to_dict(), f, indent=2)
        
        self.extraction_stats["total_processed"] += 1
        
        return quality_report
    
    def inline_code(self, source_files):
        """
        Placeholder for your existing inlining logic
        This should be replaced with your actual implementation
        """
        # Your existing inlining logic here
        return "# Inlined code would go here"
    
    def post_extraction_fixes(self):
        """Apply automated fixes to common issues"""
        
        print("\nApplying automated fixes...")
        
        fixed_count = 0
        for code_file in self.output_dir.rglob("code.py"):
            if "failed_quality" in str(code_file):
                continue
                
            with open(code_file, 'r') as f:
                original_code = f.read()
            
            fixed_code = self.apply_common_fixes(original_code)
            
            if fixed_code != original_code:
                # Re-run quality check
                quality_report = self.quality_checker.check_code(
                    fixed_code,
                    str(code_file),
                    {}
                )
                
                if quality_report.quality_score != "FAIL":
                    # Save the fixed version
                    with open(code_file, 'w') as f:
                        f.write(fixed_code)
                    
                    print(f"  Fixed: {code_file}")
                    fixed_count += 1
        
        print(f"Fixed {fixed_count} files automatically")
    
    def apply_common_fixes(self, code):
        """Apply common automated fixes"""
        
        # Fix 1: Add missing manim imports if we see manim classes being used
        if ("Scene" in code or "Mobject" in code) and "from manim" not in code:
            # Add import at the beginning after the source file header
            lines = code.split('\n')
            insert_pos = 0
            
            # Find position after header comments
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith('#'):
                    insert_pos = i
                    break
            
            lines.insert(insert_pos, "from manim_imports_ext import *")
            code = '\n'.join(lines)
        
        # Fix 2: Remove self-referential imports
        lines = code.split('\n')
        fixed_lines = []
        for line in lines:
            # Skip self-referential imports
            if "from ." in line and "import" in line and "# Inlined above" in line:
                fixed_lines.append(f"# {line.strip()}  # Removed self-referential import")
            else:
                fixed_lines.append(line)
        
        code = '\n'.join(fixed_lines)
        
        # Fix 3: Uncomment critical imports that were commented out
        code = code.replace("# from animation import", "from animation import")
        code = code.replace("# from mobject import", "from mobject import")
        code = code.replace("# from constants import", "from constants import")
        code = code.replace("# from scene import", "from scene import")
        
        return code
    
    def generate_final_report(self):
        """Generate a comprehensive final report"""
        
        report = {
            "extraction_stats": self.extraction_stats,
            "quality_summary": {},
            "recommendations": []
        }
        
        # Analyze all quality reports
        all_issues = {}
        for quality_file in self.output_dir.rglob("quality_report.json"):
            with open(quality_file, 'r') as f:
                q_report = json.load(f)
            
            for check_type, issues in q_report.get("checks", {}).items():
                if issues:
                    all_issues[check_type] = all_issues.get(check_type, 0) + len(issues)
        
        report["quality_summary"]["common_issues"] = all_issues
        
        # Add recommendations
        if self.extraction_stats["failed_quality"] > 0:
            report["recommendations"].append(
                f"Review and fix {self.extraction_stats['failed_quality']} files that failed quality checks"
            )
        
        if "imports" in all_issues:
            report["recommendations"].append(
                "Review the inlining process - import issues are common"
            )
        
        # Save report
        with open(self.output_dir / "extraction_report.json", 'w') as f:
            json.dump(report, f, indent=2)
        
        print("\n" + "="*60)
        print("EXTRACTION COMPLETE")
        print("="*60)
        print(f"Total processed: {self.extraction_stats['total_processed']}")
        print(f"Passed quality: {self.extraction_stats['passed_quality']}")
        print(f"Failed quality: {self.extraction_stats['failed_quality']}")
        print(f"\nFull report saved to: {self.output_dir / 'extraction_report.json'}")


def example_usage():
    """Example of how to use the enhanced pipeline"""
    
    pipeline = ExtractionPipelineWithQualityChecks()
    
    # Example: Process a video
    metadata = {
        "video_id": "example123",
        "year": 2015,
        "title": "Example Video"
    }
    
    # Your extraction loop would look something like:
    # for year, video_name, source_files in get_videos_to_process():
    #     pipeline.process_video(year, video_name, source_files, metadata)
    
    # After extraction, apply fixes
    pipeline.post_extraction_fixes()
    
    # Generate final report
    pipeline.generate_final_report()


if __name__ == "__main__":
    print("This is an example integration script.")
    print("Adapt the methods to your existing extraction pipeline.")
    print("\nKey integration points:")
    print("1. After inlining, before saving: Run quality checks")
    print("2. Based on quality score: Decide to include/exclude")
    print("3. After extraction: Apply automated fixes")
    print("4. Finally: Generate comprehensive report")