User give you a video url.
	-Verify that it is a youtube video.
Get transcription of said video using youtube-transcript-api
	-Return timestamps + text
	-Downside: dependent on captions, english, and some video block transcription
Get transcription from yt-dlp (more coverage)
Generate transcript from audio using whisper + yt-dlp

I want to start with the first option as it is the simplest, and consider upgrading in the future

==>> Now I have text of the video and start and end of video