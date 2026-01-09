import re
import math
from collections import defaultdict
from youtube_transcript_api import YouTubeTranscriptApi as yt
# from sentence_transformers import SentenceTransformer as st



def is_valid_youtube_url(s: str) -> bool:
    pattern = r"^https://www\.youtube\.com/watch\?v=[A-Za-z0-9]{11}$"
    return re.fullmatch(pattern, s) is not None

def userInput():
    url = input("Enter the youtube video url: ").strip()

    if is_valid_youtube_url(url):
        print("Valid URL.")
        segments = segmentation(url)
        return segments
    else:
        print("Invalid URL.")
        return None
    
print(userInput())

def segmentation(url: str, window_size: int = 20):
    videoId = url.split("v=")[-1]

    ytt_api = yt()
    YTranscript = ytt_api.fetch(videoId)

    # windows[index] = list of snippet texts assigned to that window
    windows = defaultdict(list)

    for snippet in YTranscript:
        s = float(snippet.start)
        e = s + float(snippet.duration)

        #s is the start and e is the end

        start_window = math.floor(s / window_size)
        end_window = math.floor(e / window_size)

        # Snippet fits entirely in one window
        if start_window == end_window:
            windows[start_window].append(snippet.text)
            continue

        # Snippet crosses boundary: deterministic majority-overlap rule
        boundary = (start_window + 1) * window_size
        time_in_start = boundary - s
        time_in_end = e - boundary

        if time_in_end > time_in_start:
            windows[end_window].append(snippet.text)
        else:
            windows[start_window].append(snippet.text)

    return windows