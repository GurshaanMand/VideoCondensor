import math
from requests import RequestException, Session
from youtube_transcript_api import YouTubeTranscriptApi as yt, YouTubeTranscriptApiException
from sklearn.metrics.pairwise import cosine_similarity as cs

from embedding_model import getEmbeddingModel
from segment import Segment
from stitch import stitchVideo
from video_urls import extractYoutubeVideoId, isValidYoutubeUrl, is_valid_youtube_url


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


def fetchTranscript(url: str):
    videoId = extractYoutubeVideoId(url)
    if not videoId:
        raise ValueError("Invalid YouTube URL.")

    class TimeoutSession(Session):
        def request(self, method, request_url, **kwargs):
            kwargs.setdefault("timeout", (10, 30))
            return super().request(method, request_url, **kwargs)

    session = TimeoutSession()
    try:
        return yt(http_client=session).fetch(videoId)
    except YouTubeTranscriptApiException as exc:
        raise RuntimeError(
            "This video does not have an accessible English transcript. "
            "Choose a public video with captions and try again."
        ) from exc
    except RequestException as exc:
        raise RuntimeError(
            "The YouTube transcript service could not be reached. Please retry shortly."
        ) from exc
    finally:
        session.close()


def segmentation(url: str, windowSize: int = 20, transcript=None):
    youtubeTranscript = transcript if transcript is not None else fetchTranscript(url)

    windows = {}
    for snippet in youtubeTranscript:
        start = round(float(snippet.start), 2)
        end = round(start + float(snippet.duration), 2)
        duration = snippet.duration
        text = snippet.text

        targetWindow = getTargetWindow(start, end, windowSize)
        addSnippetToWindow(windows, targetWindow, start, end, duration, text)

    for segment in windows.values():
        segment.text = " ".join(segment.pieces)
        segment.dur = max(0.0, segment.end - segment.start)

    segments = [windows[index] for index in sorted(windows.keys())]
    return segments


def embeddingSentence(segments):
    texts = [segment.text for segment in segments]

    model = getEmbeddingModel()
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
        if similarity > low:
            currentTopic.append(embeddingMatrix[index])
            currentTopic.append(embeddingMatrix[index + 1])
            currentTopic.append(embeddingMatrix[index + 2])

            centroid = (centroid * terms + embeddingMatrix[index + 2].embedding) / (terms + 1)
            terms += 1
            index += 2
            continue

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

def serializeTopics(topics):
    serializedTopics = []

    for topicIndex, topic in enumerate(topics):
        serializedTopic = {
            "topicIndex": topicIndex,
            "segments": []
        }

        for seg in topic:
            serializedTopic["segments"].append({
                "start": seg.start,
                "end": seg.end,
                "duration": seg.dur,
                "text": seg.text,
                "score": seg.score,
                "keep": seg.keep,
                "reason": seg.filterReason,
                "objectiveRelevance": seg.objRelevance,
                "informativeness": seg.informativeness,
                "novelty": seg.novelty,
                "redundancy": seg.redundancy,
                "coherence": seg.coherence,
                "density": seg.density
            })

        serializedTopics.append(serializedTopic)

    return serializedTopics

def condenseVideo(
    url,
    obj,
    source_path=None,
    output_path=None,
    progress_callback=None,
    transcript=None,
):
    def report(progress, stage, message):
        if progress_callback:
            progress_callback(progress, stage, message)

    if not isValidYoutubeUrl(url):
        return {
            "success": False,
            "error": "Invalid URL."
        }

    report(30, "Reading transcript", "Fetching captions")
    segments = segmentation(url, transcript=transcript)
    if not segments:
        raise ValueError("No transcript segments were found for this video.")

    report(42, "Understanding the video", "Creating semantic embeddings")
    segments = embeddingSentence(segments)
    report(60, "Finding the useful moments", "Grouping related sections")
    topics = cosineSimilarity(segments)
    report(68, "Ranking the useful moments", "Scoring sections against your objective")
    from filter import getInfo

    filteredTopics = getInfo(topics, obj)

    response = {
        "success": True,
        "topics": serializeTopics(filteredTopics)
    }

    if source_path and output_path:
        report(72, "Building your focused cut", "Preparing selected sections")

        def stitch_progress(current, total):
            fraction = current / total if total else 0
            report(
                72 + round(fraction * 24),
                "Building your focused cut",
                f"Rendered section {current} of {total}"
            )

        statistics = stitchVideo(
            filteredTopics,
            source_path,
            output_path,
            progress_callback=stitch_progress
        )
        response["output_path"] = str(output_path)
        response["statistics"] = statistics

    report(98, "Finishing your video", "Finalizing the result")
    return response

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
    from filter import getInfo

    filteredTopics = getInfo(topics, obj)

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


# userInput()
