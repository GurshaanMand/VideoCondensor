import re
import math
from collections import defaultdict
from youtube_transcript_api import YouTubeTranscriptApi as yt
from sentence_transformers import SentenceTransformer as st
from sklearn.metrics.pairwise import cosine_similarity as cs
from segment import Segment
from filter import getInfo
from stitch import stitchVideo



def is_valid_youtube_url(s: str) -> bool:
    pattern = r"^https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}(&.*)?$"
    return re.fullmatch(pattern, s) is not None



def segmentation(url: str, window_size: int = 20):

    videoId = url.split("v=")[-1]

    ytt_api = yt()
    YTranscript = ytt_api.fetch(videoId) 

    # windows[index] = list of snippet texts assigned to that window
    windows = {}
    i = 0

    for snippet in YTranscript:
        
        s = round(float(snippet.start), 2)
        e = round(s + float(snippet.duration), 2)
        if i < 20:
            print(s, " - ", snippet.duration, " - ", e, " :- ", snippet.text)
            i += 1

        #s is the start and e is the end

        start_window = math.floor(s / window_size)
        end_window = math.floor(e / window_size)

        # Snippet fits entirely in one window
        if start_window == end_window:

            if start_window not in windows:

                seg = Segment(start = s, end = e, dur = snippet.duration)
                seg.pieces.append(snippet.text)
                windows[start_window] = seg
            else:
                seg = windows[start_window]
                seg.end = max(seg.end, e)
                seg.pieces.append(snippet.text)

            continue

        # Snippet crosses boundary: deterministic majority-overlap rule
        boundary = (start_window + 1) * window_size
        time_in_start = boundary - s
        time_in_end = e - boundary

        if time_in_end > time_in_start:
            target_window = end_window
        else:
            target_window = start_window

        # same logic again, just writing into Segment object
        if target_window not in windows:
            seg = Segment(start=s, end=e, dur = snippet.duration)
            seg.pieces.append(snippet.text)
            windows[target_window] = seg
        else:
            seg = windows[target_window]
            seg.pieces.append(snippet.text)
            seg.dur += snippet.duration
            seg.end = max(seg.end, e)

    # windows: dict[int → Segment]
    # seg.pieces: list[str]
    # " ".join(seg.pieces): str
    # seg.text: str

    for seg in windows.values():
        seg.text = " ".join(seg.pieces)

    # windows: dict[int → Segment]
    # sorted(windows.keys()): list[int]
    # segments: list[Segment]

    segments = [windows[i] for i in sorted(windows.keys())]


    # return type: list[Segment]
    return segments

def embeddingSentence(segments):

    #Convert list[obj] -> list[str]
    texts = [seg.text for seg in segments]

    # Loading a pretrained model
    model = st("all-MiniLM-L6-v2")

    # Embedding the segements variable which is a list of strings
    embeddings = model.encode(texts)

    for i in range(len(segments)):
        segments[i].embedding = embeddings[i]

    return segments 

def cosineSimilarity(embeddingMatrix):
    # The embedding vector is 2D matrix of N X 384 size
    # Each row is a embedding of the segment, row 0 -> segment 1, row 1 -> segment 2 and so on
    # Start with centroid just being the first segement

    centroid = embeddingMatrix[0].embedding # Initially the centroid is just the first embedding vector
    low = 0.37 # I would need to get a more accurate cut off
    terms = 1
    i = 0
    length = len(embeddingMatrix)

    topics = []
    current_topic = [embeddingMatrix[0]]

    #Comapare seg 1 and 2 

    while i < length - 1:
        i += 1
        similarity = cs(centroid.reshape(1, -1), embeddingMatrix[i].embedding.reshape(1, -1))[0][0]

        if similarity > low: # Add the seg to centroid
            centroid = (centroid * terms + embeddingMatrix[i].embedding) / (terms + 1)
            terms += 1
            # Also add this segment to the topic
            current_topic.append(embeddingMatrix[i])
            continue
        else: # Similarity drops for some reason, it can be a promo, joke or something random
            # Therefore I want to check whether it drops for just one segment or for all the following

            if i + 1 < length:
                similarity = cs(centroid.reshape(1, -1), embeddingMatrix[i + 1].embedding.reshape(1, -1))[0][0]
            else: # Meaning no further segments exist, so there is only 1 segment (last one) where similarity drops
                # Do not add the segment 'i' to the topic, it is its own topic
                print()

            if similarity > low: # Implies the drop before was a one time thing
                # Add 5 and 6 to topic
                current_topic.append(embeddingMatrix[i])
                current_topic.append(embeddingMatrix[i + 1])
                centroid = (centroid * terms + embeddingMatrix[i + 1].embedding) / (terms + 1) # Add 6 to centroid
                terms += 1 
                i += 1
            else: # If similarity is still down, we make sure one last time

                if i + 2 < length: 
                    similarity = cs(centroid.reshape(1, -1), embeddingMatrix[i + 2].embedding.reshape(1, -1))[0][0]
                else: # Meaning no further segments exist, so there is only 2 segment (last and second last) where similarity drops
                    # Do not add the segment 'i' and 'i+1' to the topic,  they are there own topic
                    print()

                if similarity > low: # Implies the drop before was a çrt time thing
                    # Add 5 6 7 to topic
                    current_topic.append(embeddingMatrix[i])
                    current_topic.append(embeddingMatrix[i + 1])
                    current_topic.append(embeddingMatrix[i + 2])
                    centroid = (centroid * terms + embeddingMatrix[i + 2].embedding) / (terms + 1) # Add 6 7 to centroid
                    terms += 1
                    i += 2

                else: # Implies the drop before was NOT  a one time thing
                    print()
                    #Topic ends and we do not add any segments from this iteration of the loop

                    topics.append(current_topic)
                    current_topic = [embeddingMatrix[i]]

                    #Now the centroid is 'i' or 5
                    centroid = embeddingMatrix[i].embedding
                    terms = 1
                    #We need to to have the prev 2 and this curr segment be part of the new topic and recreate the centroid with the new segment

    topics.append(current_topic)
    return topics


def userInput():
    url = input("Enter the youtube video url: ").strip()
    obj = input("What is the object for the condensor, give key words: ").strip()

    if is_valid_youtube_url(url):
        print("Valid URL.")
        segments = segmentation(url)

        s = embeddingSentence(segments)

        # check_overlap(s, 10)

        topics = cosineSimilarity(s)

        filteredTopics = getInfo(topics, obj)
        # stitchVideo(filteredTopics, "input.mp4", "output.mp4")

        for topic_idx, topic in enumerate(filteredTopics):
            print(f"\n=== Topic {topic_idx} ===")
            for seg in topic:
                print({
                    "text": seg.text[:60],
                    "obj": round(seg.objRelevance, 3),
                    "nov": round(seg.novelty, 3),
                    "coh": round(seg.coherence, 3),
                    "den": round(seg.density, 3),
                    "score": round(seg.score, 3)
                })

    else:
        print("Invalid URL.")
        return None
    
# def check_overlap(segments, limit=10):
#     bad = 0
#     for i in range(1, len(segments)):
#         a = segments[i-1]
#         b = segments[i]
#         if b.start < a.end:
#             print(f"OVERLAP i={i-1}->{i}  a=({a.start:.3f},{a.end:.3f})  b=({b.start:.3f},{b.end:.3f})  delta={a.end-b.start:.3f}")
#             bad += 1
#             if bad >= limit:
#                 break
#     if bad == 0:
#         print("No overlaps found.")

userInput()

