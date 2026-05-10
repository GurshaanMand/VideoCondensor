# AI Video Condenser

Video Condenser is a Python-based prototype that condenses long YouTube videos by analyzing transcript segments, scoring their usefulness, and filtering out lower value parts.

## What It Does

The project takes a YouTube video transcript, breaks it into time based segments, scores each segment, and decides which parts should be kept or removed.

The current system uses:

- Objective relevance
- Topic coherence
- Novelty / redundancy detection
- Density
- Informativeness
- Duration-aware filtering

## Current Status

This is a working MVP/prototype. It produces useful filtering output, but it is not yet a polished production system.

## How It Works

1. Fetches the transcript from a YouTube video.
2. Splits the transcript into segments.
3. Generates embeddings for each segment using Sentence Transformers.
4. Groups related segments into topics.
5. Scores each segment based on relevance and usefulness.
6. Filters lower-value segments while protecting important content.

## Tech Stack

- Python
- Sentence Transformers
- scikit-learn
- YouTube Transcript API
- FFmpeg

## Limitations

- Filtering quality depends heavily on transcript quality.
- Objective relevance can be weaker for very broad user objectives.
- Redundancy detection is still basic.
- Some useful or low-value segments may be misclassified.
- Current version is focused on transcript based filtering.

## Future Improvements

- Improve objective rewriting
- Tune redundancy detection
- Add better debug summaries
- Improve final video stitching
- Add AWS/cloud deployment
- Build a simple UI

## Example Objective

- implementation steps and important reasoning