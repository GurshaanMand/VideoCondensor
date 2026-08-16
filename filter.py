"""
Filtering and scoring logic for AI Video Condenser.

Scores each segment using objective relevance, novelty, topic coherence,
density, and informativeness. Then removes low-value segments with
duration-aware filtering while protecting high-value and bridge segments.
"""

# ============================================================
# Imports and model
# ============================================================

from sklearn.metrics.pairwise import cosine_similarity as cs
import numpy as np
import math
import re

from embedding_model import getEmbeddingModel


# ============================================================
# Constants
# ============================================================

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "how", "i", "in", "is", "it", "its", "of", "on", "or",
    "that", "the", "this", "to", "was", "what", "when", "where", "who", "why",
    "with", "you", "your", "about", "into", "focus", "video", "clip", "segment",
    "only", "parts", "keep", "remove", "removed", "low", "value", "content"
}

IMPLEMENTATION_CUES = {
    "install", "configure", "configuration", "setup", "set", "create", "run", "start",
    "restart", "build", "compile", "connect", "deploy", "deployment", "host", "server",
    "database", "postgres", "postgresql", "mysql", "node", "npm", "bun", "ssh", "scp",
    "rsync", "ec2", "aws", "instance", "ubuntu", "linux", "terminal", "command",
    "environment", "variable", "env", "migration", "migrate", "systemd", "service",
    "caddy", "nginx", "proxy", "reverse", "route", "domain", "ssl", "https", "http",
    "port", "firewall", "security", "group", "key", "permissions", "package",
    "dependency", "dependencies", "runtime", "production", "logs", "localhost"
}

REASONING_CUES = {
    "because", "reason", "why", "so", "therefore", "means", "issue", "problem",
    "fix", "solution", "instead", "important", "need", "want", "should", "would"
}

BROAD_OBJECTIVE_CUES = {
    "implementation", "steps", "reasoning", "important", "explain", "explaining",
    "tutorial", "walkthrough", "actual", "concrete", "setup", "process"
}


# ============================================================
# Generic helpers
# ============================================================
# clamp
# smoothstep
# sigmoid
# flatten
# robust_minmax
# ============================================================

def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, float(value)))


def smoothstep(value, low, high):
    if high <= low:
        return 0.0

    x = clamp((float(value) - low) / (high - low))
    return x * x * (3 - 2 * x)


def sigmoid(value, steepness=5.0, midpoint=0.45):
    return 1.0 / (1.0 + math.exp(-steepness * (float(value) - midpoint)))


def flatten(topics):
    return [seg for topic in topics for seg in topic]


def robust_minmax(values, low_pct=10, high_pct=90):
    if not values:
        return []

    arr = np.array(values, dtype=float)
    low = float(np.percentile(arr, low_pct))
    high = float(np.percentile(arr, high_pct))

    if abs(high - low) < 1e-9:
        return [0.5 for _ in values]

    return [clamp((float(v) - low) / (high - low)) for v in values]


# ============================================================
# Text helpers
# ============================================================
# tokenize
# objectiveKeywords
# cueScore
# ============================================================

def tokenize(text):
    return [
        w for w in re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
        if w not in STOPWORDS
    ]


def objectiveKeywords(obj):
    return set(tokenize(obj))


def cueScore(text, cue_words):
    words = set(tokenize(text))
    if not words:
        return 0.0

    hits = len(words & cue_words)
    return smoothstep(hits, 1, 4)


def implementationCueScore(text):
    return cueScore(text, IMPLEMENTATION_CUES)


def reasoningCueScore(text):
    return cueScore(text, REASONING_CUES)


# ============================================================
# Objective relevance scoring
# ============================================================
# embedObj
# isBroadObjective
# computeRawObjectiveSimilarities
# computeKeywordScore
# computeBroadCueScore
# objectRelevance
# ============================================================

def embedObj(obj):
    objEmbedding = getEmbeddingModel().encode([obj])
    return objEmbedding[0]


def isBroadObjective(objKeywords):
    if not objKeywords:
        return False

    return len(objKeywords & BROAD_OBJECTIVE_CUES) >= 2


def computeRawObjectiveSimilarities(flat, objEmbedding):
    raw_sims = []

    for seg in flat:
        similarity = cs(
            seg.embedding.reshape(1, -1),
            objEmbedding.reshape(1, -1)
        )[0][0]

        similarity = max(0.0, float(similarity))
        seg.rawObjSimilarity = similarity
        raw_sims.append(similarity)

    return raw_sims


def computeKeywordScore(text, objKeywords):
    if not objKeywords:
        return 0.0

    seg_words = set(tokenize(text))
    overlap = len(seg_words & objKeywords) / max(1, len(objKeywords))

    return smoothstep(overlap, 0.04, 0.28)


def computeBroadCueScore(text, broadObjective):
    impl_score = implementationCueScore(text)
    reason_score = reasoningCueScore(text)

    if not broadObjective:
        return 0.0, impl_score, reason_score

    broad_cue_score = clamp((0.75 * impl_score) + (0.25 * reason_score))
    return broad_cue_score, impl_score, reason_score


def objectRelevance(topics, obj):
    flat = flatten(topics)
    objEmbedding = embedObj(obj)
    objKeywords = objectiveKeywords(obj)
    broadObjective = isBroadObjective(objKeywords)

    raw_sims = computeRawObjectiveSimilarities(flat, objEmbedding)
    relative_scores = robust_minmax(raw_sims, low_pct=10, high_pct=90)

    for seg, relative_score in zip(flat, relative_scores):
        absolute_semantic = smoothstep(seg.rawObjSimilarity, 0.18, 0.55)
        relative_semantic = sigmoid(relative_score, steepness=7.0, midpoint=0.45)
        keyword_score = computeKeywordScore(seg.text, objKeywords)

        broad_cue_score, impl_score, reason_score = computeBroadCueScore(
            seg.text,
            broadObjective
        )

        if broadObjective:
            seg.objRelevance = clamp(
                (0.48 * absolute_semantic) +
                (0.27 * relative_semantic) +
                (0.10 * keyword_score) +
                (0.15 * broad_cue_score)
            )
        else:
            seg.objRelevance = clamp(
                (0.62 * absolute_semantic) +
                (0.23 * relative_semantic) +
                (0.15 * keyword_score)
            )

        seg.keywordRelevance = keyword_score
        seg.implementationCue = impl_score
        seg.reasoningCue = reason_score


# ============================================================
# Segment scoring components
# ============================================================
# noveltyScore
# topicCoherence
# densityScore
# informativenessScore
# ============================================================

def noveltyScore(topics, lookback=6):
    for topic in topics:
        for i, seg in enumerate(topic):
            if i == 0:
                seg.novelty = 0.55
                seg.redundancy = 0.0
                continue

            previous = topic[max(0, i - lookback):i]

            max_sim = max(
                cs(seg.embedding.reshape(1, -1), prev.embedding.reshape(1, -1))[0][0]
                for prev in previous
            )

            max_sim = float(max_sim)
            redundancy = smoothstep(max_sim, 0.72, 0.92)

            seg.redundancy = redundancy
            seg.novelty = clamp(1.0 - redundancy)


def topicCoherence(topics):
    raw_values = []
    segment_order = []

    for topic in topics:
        if len(topic) == 0:
            continue

        if len(topic) == 1:
            segment_order.append(topic[0])
            raw_values.append(0.25)
            topic[0].rawCoherenceSimilarity = 0.25
            continue

        centroid = np.mean([seg.embedding for seg in topic], axis=0)

        for seg in topic:
            similarity = cs(
                seg.embedding.reshape(1, -1),
                centroid.reshape(1, -1)
            )[0][0]

            similarity = max(0.0, float(similarity))

            seg.rawCoherenceSimilarity = similarity
            segment_order.append(seg)
            raw_values.append(similarity)

    scaled = robust_minmax(raw_values, low_pct=10, high_pct=90)
    calibrated = [sigmoid(v, steepness=5.0, midpoint=0.45) for v in scaled]

    for seg, score in zip(segment_order, calibrated):
        seg.coherence = clamp(score)


def densityScore(topics):
    for topic in topics:
        for seg in topic:
            words = tokenize(seg.text)
            wordCount = len(words)

            if seg.dur > 0:
                words_per_second = wordCount / seg.dur
                seg.density = smoothstep(words_per_second, 0.55, 2.60)
            else:
                words_per_second = 0.0
                seg.density = 0.0

            seg.wordsPerSecond = words_per_second


def informativenessScore(topics):
    specifics_pattern = (
        r"\d|%|\$|\b(step|reason|example|because|therefore|means|fix|problem|"
        r"solution|install|configure|connect|run|build|deploy|create|setup|set up)\b"
    )

    for topic in topics:
        for seg in topic:
            words = tokenize(seg.text)
            word_count = len(words)
            unique_ratio = len(set(words)) / max(1, word_count)

            length_score = smoothstep(word_count, 8, 45)
            diversity_score = smoothstep(unique_ratio, 0.35, 0.75)

            has_specifics = 1.0 if re.search(
                specifics_pattern,
                (seg.text or "").lower()
            ) else 0.0

            seg.informativeness = clamp(
                (0.52 * length_score) +
                (0.28 * diversity_score) +
                (0.20 * has_specifics)
            )


# ============================================================
# Final score and calibration
# ============================================================
# finalScore
# applyObjectiveCaps
# ============================================================

def finalScore(topics):
    raw_scores = []

    for topic in topics:
        for seg in topic:
            base = (
                0.58 * seg.objRelevance +
                0.16 * seg.informativeness +
                0.10 * seg.novelty +
                0.10 * seg.coherence +
                0.06 * seg.density
            )

            penalty = 1.0

            # Objective mismatch should strongly reduce final quality.
            if seg.objRelevance < 0.12:
                penalty *= 0.45
            elif seg.objRelevance < 0.25:
                penalty *= 0.72

            if seg.informativeness < 0.20:
                penalty *= 0.60

            if seg.redundancy > 0.75 and seg.objRelevance < 0.75:
                penalty *= 0.60

            seg.rawScore = clamp(base * penalty)
            raw_scores.append(seg.rawScore)

    if not raw_scores:
        return

    p10 = float(np.percentile(raw_scores, 10))
    p90 = float(np.percentile(raw_scores, 90))

    for topic in topics:
        for seg in topic:
            if p90 - p10 < 1e-6:
                calibrated = seg.rawScore
            else:
                calibrated = clamp((seg.rawScore - p10) / (p90 - p10))

            seg.score = clamp(calibrated ** 1.25)


def applyObjectiveCaps(topics):
    for topic in topics:
        for seg in topic:
            # Prevent weak objective matches from becoming top-scoring after calibration.
            if seg.objRelevance < 0.05:
                seg.score = min(seg.score, 0.20)
            elif seg.objRelevance < 0.15:
                seg.score = min(seg.score, 0.40)
            elif seg.objRelevance < 0.25:
                seg.score = min(seg.score, 0.65)


# ============================================================
# Filtering / protection policy
# ============================================================
# addContinuityProtection
# canRemove
# markRemoved
# filterSegments
# ============================================================

def addContinuityProtection(topics):
    flat = flatten(topics)
    flat.sort(key=lambda s: s.start)

    for seg in flat:
        seg.bridge = False

        high_value = (
            seg.score >= 0.78 and seg.objRelevance >= 0.30
        ) or (
            seg.objRelevance >= 0.70 and seg.informativeness >= 0.35
        )

        implementation_step = (
            seg.objRelevance >= 0.18 and
            seg.informativeness >= 0.80 and
            getattr(seg, "implementationCue", implementationCueScore(seg.text)) >= 0.35 and
            seg.redundancy < 0.80
        )

        seg.protected = bool(high_value or implementation_step)

        if implementation_step and not high_value:
            seg.filterReason = "protected_implementation_step"

    for i, seg in enumerate(flat):
        if not seg.protected:
            continue

        for j in (i - 1, i + 1):
            if 0 <= j < len(flat):
                neighbor = flat[j]
                gap = abs(neighbor.start - seg.end) if j > i else abs(seg.start - neighbor.end)

                if (
                    gap <= 3.0 and
                    neighbor.score >= 0.30 and
                    neighbor.objRelevance >= 0.15 and
                    neighbor.informativeness >= 0.60
                ):
                    neighbor.bridge = True


def canRemove(seg):
    if seg.protected:
        return False

    if seg.bridge and seg.score >= 0.30:
        return False

    return True


def markRemoved(seg):
    seg.keep = False

    if seg.objRelevance < 0.15:
        seg.filterReason = "removed_off_objective"
    elif seg.informativeness < 0.25:
        seg.filterReason = "removed_low_information"
    elif seg.redundancy > 0.75:
        seg.filterReason = "removed_redundant"
    else:
        seg.filterReason = "removed_lowest_value"


def filterSegments(topics, target_remove_duration=0.40, max_remove_duration=0.60, min_score=0.38):
    flat = flatten(topics)
    flat.sort(key=lambda s: s.start)

    total_duration = sum(max(0.0, float(seg.dur)) for seg in flat)
    target_remove = total_duration * target_remove_duration
    max_remove = total_duration * max_remove_duration

    for seg in flat:
        seg.keep = True

        if not getattr(seg, "filterReason", "") or not str(seg.filterReason).startswith("protected"):
            seg.filterReason = "kept"

    removed = 0.0

    # Pass 1: remove obvious low-value segments before ranked filtering.
    for seg in sorted(flat, key=lambda s: (s.objRelevance, s.score)):
        if removed >= max_remove:
            break

        if not canRemove(seg):
            if seg.protected:
                seg.filterReason = "protected_high_value"
            elif seg.bridge:
                seg.filterReason = "protected_bridge"
            continue

        clear_reject = (
            (seg.objRelevance < 0.05 and seg.score < 0.20) or
            (seg.objRelevance < 0.12 and seg.score < 0.18 and seg.informativeness < 0.90) or
            (seg.redundancy > 0.85 and seg.objRelevance < 0.45)
        )

        if clear_reject:
            markRemoved(seg)
            removed += max(0.0, float(seg.dur))

    # Pass 2: remove lowest-scoring segments until target duration is reached.
    for seg in sorted(flat, key=lambda s: s.score):
        if removed >= target_remove:
            break

        if not seg.keep:
            continue

        if not canRemove(seg):
            if seg.protected:
                seg.filterReason = "protected_high_value"
            elif seg.bridge:
                seg.filterReason = "protected_bridge"
            continue

        # Avoid cutting decent objective matches only to hit the duration target.
        if seg.score >= 0.72 and seg.objRelevance >= 0.30:
            continue

        markRemoved(seg)
        removed += max(0.0, float(seg.dur))

    # Pass 3: optional cleanup of very weak segments after the target.
    for seg in sorted(flat, key=lambda s: s.score):
        if removed >= max_remove:
            break

        if not seg.keep:
            continue

        if not canRemove(seg):
            if seg.protected:
                seg.filterReason = "protected_high_value"
            elif seg.bridge:
                seg.filterReason = "protected_bridge"
            continue

        very_weak = seg.score < 0.16 and seg.objRelevance < 0.20

        if very_weak:
            markRemoved(seg)
            removed += max(0.0, float(seg.dur))

    kept_duration = total_duration - removed

    for seg in flat:
        seg.totalDuration = total_duration
        seg.removedDuration = removed
        seg.keptDuration = kept_duration
        seg.removedFraction = removed / total_duration if total_duration > 0 else 0.0


# ============================================================
# Debug / public pipeline
# ============================================================
# printCompressionSummary
# getInfo
# ============================================================

def printCompressionSummary(topics):
    flat = flatten(topics)

    total_duration = sum(max(0.0, float(seg.dur)) for seg in flat)
    kept_duration = sum(max(0.0, float(seg.dur)) for seg in flat if seg.keep)
    removed_duration = total_duration - kept_duration

    total_segments = len(flat)
    kept_segments = sum(1 for seg in flat if seg.keep)
    removed_segments = total_segments - kept_segments

    print("\n=== Compression Summary ===")
    print(f"Total segments:   {total_segments}")

    if total_segments:
        print(f"Kept segments:    {kept_segments} ({kept_segments / total_segments * 100:.1f}%)")
        print(f"Removed segments: {removed_segments} ({removed_segments / total_segments * 100:.1f}%)")
    else:
        print("Kept segments:    0")
        print("Removed segments: 0")

    print(f"Total duration:   {total_duration:.2f}s")

    if total_duration > 0:
        print(f"Kept duration:    {kept_duration:.2f}s ({kept_duration / total_duration * 100:.1f}%)")
        print(f"Removed duration: {removed_duration:.2f}s ({removed_duration / total_duration * 100:.1f}%)")


def getInfo(topics, obj):
    objectRelevance(topics, obj)
    noveltyScore(topics)
    topicCoherence(topics)
    densityScore(topics)
    informativenessScore(topics)

    finalScore(topics)
    applyObjectiveCaps(topics)

    addContinuityProtection(topics)
    filterSegments(topics)

    # Uncomment while tuning.
    # printCompressionSummary(topics)

    return topics
