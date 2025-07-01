 Cleaning is about structural organization (dependency resolution, code organization)
  - Conversion is about API translation (mapping old calls to new equivalents)
  - These require different types of analysis and would compete for attention in a single prompt


----
I've got a new idea for how we can construct a dataset!

Instead of matching up code to videos, what if we just create a dataset based on all the scenes that are in the 3b1b repo? My original thought is that by matching the code to the videos, we could use the transcript to help generate the input and then fine tune the model to output the code. 

If we just use the scenes, we can generate the input from the scene description or by summarizing the code. This will save us the trouble of matching the code to the videos, and we can still fine-tune the model to output the code based on the scene descriptions.

One thing I'm worried about is that the scene descriptions might not be detailed enough to generate the code accurately. However, we can try to summarize the code in a way that captures the essential parts needed for generating the code.

I'm also concerned about the amount of code in that repo that is not actually used in the videos. 

After we are done processing, each scene should be fully standalone and complete so that it can be rendered into a video. This should  so we can ensure that the code we generate is relevant to the scene description.

---
The cleaning stage is the bottleneck because it's not producing truly self-contained files that can be converted to ManimCE. take a look at the outputs from my most recent run of python scripts/build_dataset_pipeline.py --year 2015 --video inventing-math --force-clean --force-convert  --verbose (which is only through cleaning 16/49 scenes and counting currently) and do a deep dive on what  the biggest problems in our pipeline are currently. its crucial that we fix this since its holding up the rest of the project. when you do find exactly what the problem is, i want you to say exactly why you think its happening and provide examples and concrete suggestions of how we can fix it. start with the most common 2-3 problems for now  


We have a single goal this session: analyze the output from our latest pipeline run, and figure out why its not working and how we can make it better. 

Remember, we are trying to create self-contained ManimCE scenes that can be rendered into videos without any manual intervention. These snippets should pretty much correspond 1:1 to the scenes in the 3b1b repo, and we can render out our work into a video to validate everything is working.


We will focus on the cleaning and conversion process, since this is the current bottleneck the success of the project hinges upon. You can look at the existing outputs from the command `python scripts/build_dataset_pipeline.py --year 2015  --force-clean --force-convert --force-render --render --parallel-render 4 --timeout-multiplier 5.0 --verbose`. Once you understand exactly what the problem is, provide evidence this problem exists, why it exists, and then propose a concrete fix to the problem. Your fix will end up being applied to all the videos in the dataset, so make sure it actually works on a couple different videos. You can use the argument --video with the @build_dataset_pipeline.py script to validate. Other claude instances might be working on other issues, so be careful that if you are running the pipeline in parallel, you don't overwrite their outputs in a way that would break their work.

Update the @scripts/KNOWN_ISSUES.md file as you progress with anything that would be helpful to other claude / LLM instances picking up the work in the future. 

----

python scripts/build_dataset_pipeline.py --year 2016 --force-clean --force-convert --force-render --render --parallel-render 4 --timeout-multiplier 5.0 --verbose | claude --dangerously-skip-permissions "look at the output of our most recent run of the command `python scripts/build_dataset_pipeline.py --year 2016 --force-clean --force-convert --force-render --render --parallel-render 4 --timeout-multiplier 5.0 --verbose` and analyze how the run went. pay close attention to our cleaning and conversion process, since this is the current bottleneck the success of the project hinges upon. once you understand how each part of the process went, tell me exactly which 2-3 things ar holding us up still and why you think so as well as concrete solutions to these problems. if you understand the issues all the way and are confident in your solution, go ahead and implement the fix as well "

----
we have a single goal this session: fix the main bug that is currently preventing any given video from being cleaned, converted, and rendered correctly. check out my latest run of @scripts/build_dataset_pipeline.py `python scripts/build_dataset_pipeline.py --year 2015 --video inventing-math --force-clean --force-convert --force-render --render --parallel-render 4 --timeout-multiplier 5.0 --verbose`
