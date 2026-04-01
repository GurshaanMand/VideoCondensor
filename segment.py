class Segment:
    def __init__(self, start: float, end: float, dur):
        self.start = start
        self.end = end
        self.dur = dur
        self.pieces = []       # list[str]
        self.text = None
        self.embedding = None
        self.objRelevance = None
        self.novelty = None
        self.coherence = None
        self.density = None
        self.score = None
        self.keep = None

    # def __repr__(self):
    #     return f"Segment(start={self.start}, end={self.end}, text='{self.text[:50]}...')"
    
    