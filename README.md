Title: 3b1b video matching

# Datasets
We have two GitHub repos that contain manim code for various videos, and another repo that has the transcripts for those repos. 
https://github.com/3b1b/captions
https://github.com/3b1b/videos

Our goal is to create a neat supervised fine tuning dataset by matching up the videos with the transcripts. Note that we are able to get the transcript directly from youtube, this does not actually help us match the code to the videos. We should plan what format the dataset needs to be in and implement the code to create this dataset.

Since we are using the 3b1b code and videos as our data source, we should log the progress of of how many videos we are able to match, how many we excluded, and how many we were unsure about and why. 


# STEPS

## Plan: 
read the whole document and understand the steps we need to take to create this dataset.

## Downloader: 
download 3b1b/videos repo for the code, 3b1b/captions for the transcripts, and YouTube videos with the transcript and metadata.

## Filter: (remove shorts and anything that is not actually a manim video)
We explicitly don’t want to include shorts or any videos that are not actually manim videos. See @excluded_videos.txt for the list of videos that we are excluding from the dataset.

## Match: 
We need to match the videos to the transcripts and the code. This is where most of the uncertainty lies. 

The manim code files are not neatly organized to correspond 1:1 to a video. sometimes, there is code for one video scattered amongst different files. The videos are in a directory structure that is organized by year, so we can use the year metadata from the video to determine which captions/code directories to look in, but we will probably need to be careful to create good heuristics to match the videos to the transcripts and code. 

### # Create single file out of the code
We want to have exactly one file per video, so if there are imports we should inline the code from those imports.

**✅ SIGNIFICANTLY IMPROVED**: The v4 matching script (`match_videos_to_code_v4.py`) automatically inlines local imports with much better success rates. Recent enhancements handle imports inside functions, CONFIG dictionaries, and complex variable assignments. Files achieve good self-containment with minimal manual cleanup needed. See `IMPORT_INLINING.md` for detailed documentation. 

We should ultra think about the best way to match up the code to the videos. We don’t want any false positives - its critical that if we are unsure of whether the code goes with a video, we should mark it as such and withhold it for human review

Stage 1: output structure 
```
youtube_video_title
- metadata.txt
    - length of video, date published, topics, keywords, etc
- scenes
    - one single manimGL file that contains all of the scenes in the video
```  

## Verify and Validate (strenuous):
Lets read over the matched videos, transcripts, and code to ensure that they make sense. are correctly matched. This will be a manual process, but we can use some heuristics to make it easier.

If nothing else, we could read each of the files and transcripts and use the text to match them up. 




# CODE INSTRUCTIONS:
Write code that is as simple and readable as possible. 

There are some reference scripts in generate_dataset/3b1b, but its a total mess right now and id like to use some of the scraping and infrastructure code as inspiration, but otherwise start with a clean slate

If you find yourself looking for exceptions and to catch errors gracefully, stop and reflect on what might be causing those errors and if there is something else we can do to actually fix the problem instead of just handling it. 



# Points of uncertainty
Are we able to accurately split the transcripts according to the scenes in the code
Are we able to match up the videos, transcripts, and code (ideal) or video and code?

We are able to get the transcripts from the youtube video, but i suspect it’s easier to link the videos to the captions using the transcripts, and then use the captions to the code than it is to link to the video directly to the code. Relatedly, the captions and the code are both in repos organized by year, so im thinking we can use the year metadata from the video to determine which captions/code directories to look in. 



STAGE 2 (STOP before we start this step and I will review the matches):
# Scene splitter: convert all of the videos into groups of standalone scenes

# ManimCE Conversion step: step where we split the videos into scenes, convert the manim code from ManimGL (3b1b’s proprietary manim package) to ManimCE (the open source, standard manim edition). This will also involve stripping out pi characters and other proprietary assets that prevent us from rendering the scene locally. 


**Gold Standard for Success**: If we have done all of the steps correctly, we will be able to render the video for each scene and it should look the same as the original youtube video scene (minus the pi creatures).

**✅ ENHANCED WITH PRE-COMPILE VALIDATION**: The conversion pipeline now includes static analysis that catches ~80% of errors before expensive render attempts. Automatic fixes handle common issues like deprecated APIs, missing imports, and incorrect method calls. See `docs/PRECOMPILE_VALIDATION.md` for details. 

# Desired final output structure:
The final product should look something like this (TODO update as we get a higher resolution image of what we need)
youtube_video_title
- metadata.txt
    - length of video, date published, topics, keywords, etc
- scenes
    - manim-scene1.py
    - manim-scene2.py
- transcripts/
    - scene1.txt
    - scene2.txt    
- videos/ (optional)
    - scene1.mp4
    - scene2.mp4


DATA NOTES and DETAILS:
- we only wan the english transcripts
- the captions/ have unknown content and are unreliable. the youtube transcripts are MUCH more reliable. however, using the captions might be helpful for matching the code to the video, so we should use them as a secondary source of information.