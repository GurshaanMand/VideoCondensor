from sentence_transformers import SentenceTransformer as st
from sklearn.metrics.pairwise import cosine_similarity as cs
import numpy as np
import math


MODEL = st("all-MiniLM-L6-v2")


def embedObj(obj):
    obj = [obj]
    objEmbedding = MODEL.encode(obj)
    return objEmbedding[0]


def objectRelevance(topics, objEmbedding):
    for topic in topics:
        for seg in topic:
            similarity = cs(
                seg.embedding.reshape(1, -1),
                objEmbedding.reshape(1, -1)
            )[0][0]
            similarity = max(0, similarity)
            seg.objRelevance = 1 - math.exp(-4 * similarity)


def noveltyScore(topics):
    for topic in topics:
        length = len(topic)

        if length == 1:
            topic[0].novelty = .2
            continue

        for i, seg in enumerate(topic):
            if i == 0:
                nextSim = cs(
                    seg.embedding.reshape(1, -1),
                    topic[i + 1].embedding.reshape(1, -1)
                )[0][0]

                seg.novelty = 1 - nextSim

            elif i == length - 1:
                prevSim = cs(
                    seg.embedding.reshape(1, -1),
                    topic[i - 1].embedding.reshape(1, -1)
                )[0][0]

                seg.novelty = 1 - prevSim

            else:
                prevSim = cs(
                    seg.embedding.reshape(1, -1),
                    topic[i - 1].embedding.reshape(1, -1)
                )[0][0]

                nextSim = cs(
                    seg.embedding.reshape(1, -1),
                    topic[i + 1].embedding.reshape(1, -1)
                )[0][0]

                avgSim = (prevSim + nextSim) / 2
                seg.novelty = 1 - avgSim

def topicCoherence(topics):
    for topic in topics:
        if len(topic) == 0:
            continue
        if len(topic) == 1:
            topic[0].coherence = 0.2
            continue

        # Loop 1 — compute centroid by averaging all embeddings in topic
        centroid = np.mean([seg.embedding for seg in topic], axis=0)

        # Loop 2 — score each segment against the centroid
        for seg in topic:
            similarity = cs(
                seg.embedding.reshape(1, -1),
                centroid.reshape(1, -1)
            )[0][0]

            seg.coherence = similarity  # Higher similarity = better fit within topic

def densityScore(topics):
    for topic in topics:
        for seg in topic:
            words = seg.text.split()
            wordCount = len(words)

            if seg.dur > 0:
                rawDensity = wordCount / seg.dur
                seg.density = normalizeDensity(rawDensity)
            else:
                seg.density = 0
    

def normalizeDensity(density, lam=0.1):
    return 1 - math.exp(-lam * density)

def finalScore(topics):
    weightObj = 0.45
    weightCoh = 0.25
    weightNov = 0.15
    weightDen = 0.15

    for topic in topics:
        for seg in topic:
            seg.score = (
                weightObj * seg.objRelevance +
                weightCoh * seg.coherence +
                weightNov * seg.novelty +
                weightDen * seg.density
            )
        

#def function
#create a variable named filtered topics to hold this format list[list[segment object]]
#loop throught all topics
#loop throught all segments of a topic
#look at the finalscore
#if score < cutoff (which is 0.3 for testing) change seg.keep = False, else seg.keep = True 
# and add all segments in the keep = true to the new variable

def filterSegments(topics, cutoff=0.3):
    for topic in topics:
        for seg in topic:
            seg.keep = seg.score >= cutoff

def getInfo(topics, obj):
    objEmbedding = embedObj(obj)
    objectRelevance(topics, objEmbedding)
    noveltyScore(topics)
    topicCoherence(topics)
    densityScore(topics)
    finalScore(topics)
    filterSegments(topics)
    

    return topics