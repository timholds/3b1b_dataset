# Using Gemini CLI for 3Blue1Brown Dataset Pipeline

When analyzing large codebases, validating pipeline outputs, or debugging conversion issues that might exceed context limits, use the Gemini CLI with its massive context window. Use `gemini -p` to leverage Google Gemini's large context capacity for comprehensive analysis.

## File and Directory Inclusion Syntax

Use the `@` syntax to include files and directories in your Gemini prompts. The paths should be relative to WHERE you run the gemini command:

### Basic Examples:

**Single file analysis:**
```bash
gemini -p "@scripts/build_dataset_pipeline.py Explain the pipeline architecture and identify potential optimization points"
```

**Multiple conversion files:**
```bash
gemini -p "@scripts/systematic_pipeline_converter.py @scripts/enhanced_scene_converter.py Compare these two conversion approaches and identify their strengths"
```

**Entire scripts directory:**
```bash
gemini -p "@scripts/ Analyze the overall pipeline architecture and identify dependencies between components"
```

**Pipeline outputs for a specific year:**
```bash
gemini -p "@outputs/2015/ Summarize the conversion results and identify common failure patterns"
```

**Current directory analysis:**
```bash
gemini -p "@./ Give me an overview of this 3Blue1Brown dataset project structure"
# Or use --all_files flag:
gemini --all_files -p "Analyze the project structure and identify the main data flow"
```

## Pipeline Validation and Debugging Examples

### Conversion Quality Analysis
**Check conversion success patterns:**
```bash
gemini -p "@outputs/2015/ @outputs/2016/ Analyze conversion success rates across years and identify which types of scenes fail most often"
```

**Validate systematic converter effectiveness:**
```bash
gemini -p "@scripts/systematic_pipeline_converter.py @outputs/2015/*/conversion_results.json Analyze how well the systematic converter is performing and what patterns still require Claude API calls"
```

**Identify unfixable patterns:**
```bash
gemini -p "@scripts/unfixable_pattern_detector.py @outputs/2015/*/logs.json Are there new unfixable patterns we should add to the detector? Show examples from the logs"
```

### Code Quality and Validation
**Check cleaned code quality:**
```bash
gemini -p "@outputs/2015/*/cleaned_scenes/ Analyze the quality of cleaned ManimGL code. Are there common syntax errors or missing imports?"
```

**Validate ManimCE conversion accuracy:**
```bash
gemini -p "@outputs/2015/*/validated_snippets/ Review the converted ManimCE snippets. Are the conversions semantically correct? Check for common conversion errors"
```

**Analyze rendering failures:**
```bash
gemini -p "@outputs/2015/*/rendered_videos/ @scripts/render_videos.py What are the most common rendering failure patterns and how can we improve the renderer?"
```

### Pipeline Performance Analysis
**Check Claude API usage efficiency:**
```bash
gemini -p "@logs/ @outputs/2015/*/conversion_results.json Analyze Claude API usage patterns. Which videos require the most API calls and why?"
```

**Validate cost optimization:**
```bash
gemini -p "@scripts/unfixable_pattern_detector.py @logs/pipeline_*.log How much cost are we saving with unfixable pattern detection? Show statistics and examples"
```

**Analyze processing bottlenecks:**
```bash
gemini -p "@logs/cleaning_summary_*.json @logs/pipeline_report_*.json Where are the performance bottlenecks in our pipeline? Which stages take the most time?"
```

### Cross-File Dependency Analysis
**Check symbol resolution accuracy:**
```bash
gemini -p "@.symbol_cache/ @scripts/import_resolver.py Is our symbol index capturing all necessary dependencies? Are there missing imports in converted files?"
```

**Validate helper module usage:**
```bash
gemini -p "@scripts/manimce_constants_helpers.py @outputs/2015/*/validated_snippets/ Are we correctly importing helper functions in converted snippets? Check for undefined names"
```

### Year-over-Year Comparison
**Compare pipeline success across years:**
```bash
gemini -p "@outputs/2015/ @outputs/2016/ @outputs/2017/ Compare conversion success rates and failure patterns across different years. What changed in the 3b1b codebase over time?"
```

**Analyze complexity evolution:**
```bash
gemini -p "@outputs/ Which years have the most complex scenes? How has 3Blue1Brown's animation complexity evolved over time?"
```

### Error Pattern Analysis
**Identify common conversion errors:**
```bash
gemini -p "@logs/claude_fixes/ @outputs/*/conversion_results.json What are the most common patterns that Claude fixes? Can we add these to the systematic converter?"
```

**Check validation failures:**
```bash
gemini -p "@outputs/*/scene_validation_report.txt @scripts/scene_validator.py What validation errors occur most frequently? How can we improve the validator?"
```

**Analyze cleaning failures:**
```bash
gemini -p "@outputs/*/logs.json What causes cleaning failures? Are there patterns we can detect and fix programmatically?"
```

## When to Use Gemini CLI for This Project

Use `gemini -p` when:
- Analyzing entire year directories that would exceed Claude's context
- Comparing multiple pipeline runs or conversion results
- Debugging complex cross-file dependency issues
- Validating conversion quality across large numbers of files
- Analyzing logs to identify systematic patterns
- Checking for consistency in helper module usage
- Investigating performance bottlenecks across the entire pipeline
- Validating that unfixable pattern detection is working correctly
- Comparing before/after states of large refactoring efforts

## Specific Pipeline Integration Commands

**Pre-pipeline analysis:**
```bash
# Before running pipeline - check source code complexity
gemini -p "@data/captions/2015/ What types of animations and complexity levels should we expect for this year?"
```

**Mid-pipeline validation:**
```bash
# After cleaning stage - validate quality
gemini -p "@outputs/2015/*/cleaned_scenes/ Are there systematic issues with the cleaned code that need fixing?"

# After conversion - check ManimCE compatibility
gemini -p "@outputs/2015/*/validated_snippets/ Do these ManimCE snippets look correct? Any obvious conversion errors?"
```

**Post-pipeline analysis:**
```bash
# Full pipeline results analysis
gemini -p "@outputs/2015/ @logs/pipeline_report_2015_latest.json Provide a comprehensive analysis of the pipeline results for 2015"

# Cross-year comparison
gemini -p "@outputs/ Compare pipeline effectiveness across all processed years"
```

## Important Notes for This Project

- Paths in @ syntax are relative to your current working directory when invoking gemini
- The CLI will include file contents directly in the context
- Gemini's context window can handle entire year directories that would overflow Claude's context
- Use specific queries about conversion patterns, API usage, and validation results
- When checking pipeline outputs, be specific about what quality metrics you're looking for
- The unfixable pattern detection logs are particularly useful for cost optimization analysis
- Cross-reference conversion results with original 3b1b source complexity for accuracy validation