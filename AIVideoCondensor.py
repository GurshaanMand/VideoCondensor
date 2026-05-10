import re
import math
from youtube_transcript_api import YouTubeTranscriptApi as yt
from sentence_transformers import SentenceTransformer as st
from sklearn.metrics.pairwise import cosine_similarity as cs

from segment import Segment
from filter import getInfo
from stitch import stitchVideo


def isValidYoutubeUrl(url: str) -> bool:
    pattern = r"^https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}(&.*)?$"
    return re.fullmatch(pattern, url) is not None


# Backward-compatible alias in case another file uses the old name.
def is_valid_youtube_url(url: str) -> bool:
    return isValidYoutubeUrl(url)


def addSnippetToWindow(windows, windowIndex, start, end, duration, text):
    if windowIndex not in windows:
        segment = Segment(start=start, end=end, dur=duration)
        segment.pieces.append(text)
        windows[windowIndex] = segment
        return

    segment = windows[windowIndex]
    segment.end = max(segment.end, end)
    segment.dur += duration
    segment.pieces.append(text)


def getTargetWindow(start, end, windowSize):
    startWindow = math.floor(start / windowSize)
    endWindow = math.floor(end / windowSize)

    if startWindow == endWindow:
        return startWindow

    boundary = (startWindow + 1) * windowSize
    timeInStart = boundary - start
    timeInEnd = end - boundary

    if timeInEnd > timeInStart:
        return endWindow

    return startWindow


def segmentation(url: str, windowSize: int = 20):
    videoId = url.split("v=")[-1]

    youtubeApi = yt()
    youtubeTranscript = youtubeApi.fetch(videoId)

    windows = {}
    printedCount = 0

    for snippet in youtubeTranscript:
        start = round(float(snippet.start), 2)
        end = round(start + float(snippet.duration), 2)
        duration = snippet.duration
        text = snippet.text

        if printedCount < 20:
            print(start, " - ", duration, " - ", end, " :- ", text)
            printedCount += 1

        targetWindow = getTargetWindow(start, end, windowSize)
        addSnippetToWindow(windows, targetWindow, start, end, duration, text)

    for segment in windows.values():
        segment.text = " ".join(segment.pieces)

    segments = [windows[index] for index in sorted(windows.keys())]
    return segments


def embeddingSentence(segments):
    texts = [segment.text for segment in segments]

    model = st("all-MiniLM-L6-v2")
    embeddings = model.encode(texts)

    for index in range(len(segments)):
        segments[index].embedding = embeddings[index]

    return segments


def cosineSimilarity(embeddingMatrix):
    centroid = embeddingMatrix[0].embedding
    low = 0.37
    terms = 1
    index = 0
    length = len(embeddingMatrix)

    topics = []
    currentTopic = [embeddingMatrix[0]]

    while index < length - 1:
        index += 1

        similarity = cs(
            centroid.reshape(1, -1),
            embeddingMatrix[index].embedding.reshape(1, -1)
        )[0][0]

        if similarity > low:
            centroid = (centroid * terms + embeddingMatrix[index].embedding) / (terms + 1)
            terms += 1
            currentTopic.append(embeddingMatrix[index])
            continue

        if index + 1 < length:
            similarity = cs(
                centroid.reshape(1, -1),
                embeddingMatrix[index + 1].embedding.reshape(1, -1)
            )[0][0]
        else:
            print()

        if similarity > low:
            currentTopic.append(embeddingMatrix[index])
            currentTopic.append(embeddingMatrix[index + 1])

            centroid = (centroid * terms + embeddingMatrix[index + 1].embedding) / (terms + 1)
            terms += 1
            index += 1
            continue

        if index + 2 < length:
            similarity = cs(
                centroid.reshape(1, -1),
                embeddingMatrix[index + 2].embedding.reshape(1, -1)
            )[0][0]
        else:
            print()

        if similarity > low:
            currentTopic.append(embeddingMatrix[index])
            currentTopic.append(embeddingMatrix[index + 1])
            currentTopic.append(embeddingMatrix[index + 2])

            centroid = (centroid * terms + embeddingMatrix[index + 2].embedding) / (terms + 1)
            terms += 1
            index += 2
            continue

        print()

        topics.append(currentTopic)
        currentTopic = [embeddingMatrix[index]]

        centroid = embeddingMatrix[index].embedding
        terms = 1

    topics.append(currentTopic)
    return topics


def printFilteredTopics(filteredTopics):
    for topicIndex, topic in enumerate(filteredTopics):
        print(f"\n=== Topic {topicIndex} ===")

        for segment in topic:
            print({
                "text": segment.text[:80],
                "raw_obj_sim": round(segment.rawObjSimilarity, 3),
                "obj": round(segment.objRelevance, 3),
                "kw": round(segment.keywordRelevance, 3),
                "info": round(segment.informativeness, 3),
                "nov": round(segment.novelty, 3),
                "red": round(segment.redundancy, 3),
                "coh": round(segment.coherence, 3),
                "den": round(segment.density, 3),
                "wps": round(segment.wordsPerSecond, 3),
                "raw_score": round(segment.rawScore, 3),
                "score": round(segment.score, 3),
                "keep": segment.keep,
                "reason": segment.filterReason,
            })


def userInput():
    url = input("Enter the youtube video url: ").strip()
    obj = input("What is the object for the condensor, give key words: ").strip()

    if not isValidYoutubeUrl(url):
        print("Invalid URL.")
        return None

    print("Valid URL.")

    segments = segmentation(url)
    embeddedSegments = embeddingSentence(segments)
    topics = cosineSimilarity(embeddedSegments)
    filteredTopics = getInfo(topics, obj)

    # stitchVideo(filteredTopics, "input.mp4", "output.mp4")
    printFilteredTopics(filteredTopics)

    return filteredTopics


# def checkOverlap(segments, limit=10):
#     bad = 0
#
#     for index in range(1, len(segments)):
#         previousSegment = segments[index - 1]
#         currentSegment = segments[index]
#
#         if currentSegment.start < previousSegment.end:
#             print(
#                 f"OVERLAP i={index - 1}->{index} "
#                 f"a=({previousSegment.start:.3f},{previousSegment.end:.3f}) "
#                 f"b=({currentSegment.start:.3f},{currentSegment.end:.3f}) "
#                 f"delta={previousSegment.end - currentSegment.start:.3f}"
#             )
#             bad += 1
#
#             if bad >= limit:
#                 break
#
#     if bad == 0:
#         print("No overlaps found.")


userInput()