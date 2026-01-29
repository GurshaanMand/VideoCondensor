import re
import math
from collections import defaultdict
from youtube_transcript_api import YouTubeTranscriptApi as yt
from sentence_transformers import SentenceTransformer as st
from sklearn.metrics.pairwise import cosine_similarity as cs



def is_valid_youtube_url(s: str) -> bool:
    pattern = r"^https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}(&.*)?$"
    return re.fullmatch(pattern, s) is not None



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

    # CONVERT dict[int, list[str]] → list[str]
    segments = [
        " ".join(windows[i])
        for i in sorted(windows.keys())
    ]

    return segments

def embeddingSentence(segments):
    # Loading a pretrained model
    model = st("all-MiniLM-L6-v2")

    # Embedding the segements variable which is a list of strings
    embeddings = model.encode(segments)

    return embeddings

def cosineSimilarity(embeddingMatrix):
    # The embedding vector is 2D matrix of N X 384 size
    # Each row is a embedding of the segment, row 0 -> segment 1, row 1 -> segment 2 and so on
    # Start with centroid just being the first segement

    centroid = embeddingMatrix[0] # Initially the centroid is just the first embedding vector
    low = 0.5 # I would need to get a more accurate cut off
    terms = 1
    i = 0
    length = len(embeddingMatrix)

    #Comapare seg 1 and 2

    while i < length:
        i += 1
        similarity = cs(centroid, embeddingMatrix[i]) #!!!!!!!! this gives a 2d matrix not a float, i need to index this 2d matrix

        if similarity > low: # Add the seg to centroid
            centroid = (centroid * terms + embeddingMatrix[i]) / (terms + 1)
            terms += 1
            # Also add this segment to the topic
            continue
        else: # Similarity drops for some reason, it can be a promo, joke or something random
            # Therefore I want to check whether it drops for just one segment or for all the following

            if i + 1 < length:
                similarity = cs(centroid, embeddingMatrix[i + 1])
            else: # Meaning no further segments exist, so there is only 1 segment (last one) where similarity drops
                # Do not add the segment 'i' to the topic, it is its own topic
                print()

            if similarity > low: # Implies the drop before was a one time thing
                # Add 5 and 6 to topic
                centroid = (centroid * terms + embeddingMatrix[i + 1]) / (terms + 1) # Add 6 to centroid
                terms += 1 
                i += 1
            else: # If similarity is still down, we make sure one last time

                if i + 2 < length: 
                    similarity = cs(centroid, embeddingMatrix[i + 2])
                else: # Meaning no further segments exist, so there is only 2 segment (last and second last) where similarity drops
                    # Do not add the segment 'i' and 'i+1' to the topic,  they are there own topic
                    print()

                if similarity > low: # Implies the drop before was a short time thing
                    # Add 5 6 7 to topic
                    centroid = (centroid * terms + embeddingMatrix[i + 2]) / (terms + 1) # Add 6 7 to centroid
                    terms += 1
                    i += 2

                else: # Implies the drop before was NOT  a one time thing
                    print()
                    #Topic ends and we do not add any segments from this iteration of the loop

                    #Now the centroid is 'i' or 5
                    centroid = embeddingMatrix[i]
                    terms = 1
                    #We need to to have the prev 2 and this curr segment be part of the new topic and recreate the centroid with the new segment






def userInput():
    url = input("Enter the youtube video url: ").strip()

    if is_valid_youtube_url(url):
        print("Valid URL.")
        segments = segmentation(url)

        embedding = embeddingSentence(segments)

    else:
        print("Invalid URL.")
        return None
    
print(userInput())

