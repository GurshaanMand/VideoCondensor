class Segment:
    def __init__(self, start: float, end: float, dur):
        self.start = start
        self.end = end
        self.dur = dur
        self.pieces = []
        self.text = None
        self.embedding = None

        # Scoring signals
        self.rawObjSimilarity = None
        self.keywordRelevance = None
        self.objRelevance = None
        self.novelty = None
        self.redundancy = None
        self.rawCoherenceSimilarity = None
        self.coherence = None
        self.density = None
        self.wordsPerSecond = None
        self.informativeness = None
        self.rawScore = None
        self.score = None

        # Filtering decisions
        self.keep = None
        self.protected = False
        self.bridge = False
        self.filterReason = None
        self.totalDuration = None
        self.removedDuration = None
        self.keptDuration = None
        self.removedFraction = None

    def __repr__(self):
        preview = (self.text or "").replace("\n", " ")
        return f"Segment(start={self.start}, end={self.end}, score={self.score}, keep={self.keep}, text='{preview}...')"
