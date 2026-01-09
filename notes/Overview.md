Long-form videos contain a mixture of high-value content and low-value filler, but “filler” is context-dependent. Naively removing content often breaks narrative flow and makes the video unpleasant to watch.

This project explores the problem of condensing long-form YouTube videos into shorter, watchable versions by selectively removing low-value content while preserving narrative flow, speaker coherence, and audio continuity.

  

The system takes a YouTube video URL as input and produces a condensed version of the video that retains the most relevant segments according to a defined objective, such as maximizing informational density or reducing redundancy. Unlike traditional summarization approaches that generate text summaries, this project focuses on **selecting and preserving original video segments**, maintaining the speaker’s voice, pacing, and delivery.

  

A core challenge of this problem is that “filler” content is highly context-dependent. Content such as jokes, anecdotes, or repetitions may be essential in entertainment videos but considered low-value in educational or tutorial-style content. As a result, the system cannot rely on a single global definition of filler and must instead balance multiple signals when deciding which segments to retain.

  

Another key constraint is maintaining perceptual smoothness in the final output. Abrupt cuts, unnatural pauses, or fragmented speech significantly degrade the viewing experience, even if the retained content is technically relevant. Therefore, segment selection must account not only for content value but also for temporal continuity and audio flow.

  

The goal of this project is not to fully automate subjective judgment, but to design a controllable and explainable pipeline that selects video segments under defined constraints, produces a coherent condensed video, and exposes the reasoning behind its decisions.