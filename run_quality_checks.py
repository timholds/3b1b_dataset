#!/usr/bin/env python3
"""
Integration script for running quality checks on extracted 3b1b dataset
"""

import json
import sys
from pathlib import Path
from quality_checker import check_directory, check_file


def main():
    """Run quality checks on the extracted dataset"""
    
    # Check output_v4 directory
    output_dir = Path("output_v4")
    
    if not output_dir.exists():
        print(f"Error: {output_dir} directory not found!")
        sys.exit(1)
    
    print("Running quality checks on extracted 3b1b dataset...")
    print("=" * 60)
    
    # Run checks and save results
    results = check_directory(str(output_dir), "quality_report_v4.json")
    
    # Print summary statistics
    total = len(results)
    passed = sum(1 for r in results.values() if r.quality_score == "PASS")
    warnings = sum(1 for r in results.values() if r.quality_score == "WARN")
    failed = sum(1 for r in results.values() if r.quality_score == "FAIL")
    
    print("\n" + "=" * 60)
    print("QUALITY CHECK SUMMARY")
    print("=" * 60)
    print(f"Total files checked: {total}")
    print(f"Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"Warnings: {warnings} ({warnings/total*100:.1f}%)")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)")
    
    # List failed files
    if failed > 0:
        print("\n" + "-" * 60)
        print("FAILED FILES (require immediate attention):")
        for path, report in results.items():
            if report.quality_score == "FAIL":
                print(f"\n{path}:")
                for check_name, issues in report.checks.items():
                    if issues and not check_name.endswith("_warnings"):
                        for issue in issues:
                            print(f"  - {issue}")
    
    # Suggest next steps
    print("\n" + "=" * 60)
    print("RECOMMENDED ACTIONS:")
    print("=" * 60)
    
    if failed > 0:
        print("1. Fix critical issues in failed files before using dataset")
        print("2. Review the inlining process for files with import issues")
        print("3. Consider manually reviewing files with multiple source files merged")
    
    if warnings > 0:
        print(f"\n{warnings} files have warnings that should be reviewed")
        print("Check quality_report_v4.json for detailed warnings")
    
    if passed == total:
        print("All files passed quality checks! Dataset is ready for use.")
    else:
        print(f"\nOnly {passed}/{total} files are production-ready.")
        print("Fix issues before using this dataset for training or analysis.")


if __name__ == "__main__":
    main()