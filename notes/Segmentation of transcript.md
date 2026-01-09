I feel like I want to segment based on topic, for explain in a Minecraft lets play video the user may talk about exploring, mining, building, these then become 3 topic. That's my idea.

How do I differentiate between topic from just text?

  

Here is my first thought add up all the text send it to a AI recipe timestamps for different topic

  

Seems simple but in efficient cuz u are sending large chunks  of text

  

But how can u other than that automatically determine different topic from plain text?


Step or approach 1 and 2, I think you are basically saying I determine topics by splitting the transcript into let's say 30-second window and determining the difference in the vocabulary in each window and when it drops below a certain percentage and conclude that the person has shifted to a different topic. It depends on their vocabulary use. I think this method is cosine similarity but I can do something similar but I would assume it's harder with vector using a local model or an API. I guess that would give me a more accurate response or a more accurate probability.


**Approach 1**: vocabulary changes, measured by similarity between consecutive windows.
    
**Approach 2**: meaning changes, measured by similarity between consecutive windows, but using embeddings instead of word counts.

You detect where the topic likely changes
Embeddings do not give you a “probability” by default. They give you a vector. Similarity is still a number like cosine similarity. You can treat low similarity as a confidence signal, but it is not a calibrated probability unless you build calibration logic.




## **2. Approach ranking (recruiter / evaluator signal)**

  

**Approach 1. Vocabulary-based similarity (TF-IDF + cosine similarity)**

**Score: 6.5 / 10**

  

**Approach 2. Semantic similarity (embeddings + cosine similarity)**

**Score: 8.5 / 10**

  

Why the difference:

- Approach 1 shows solid fundamentals and explainability.
    
- Approach 2 shows modern NLP understanding and better real-world robustness.
    
- Neither is “bad.” Approach 2 just survives tougher interview questions.
    

---

## **3. The two approaches explained, cleanly and factually**

### **Approach 1. Vocabulary-based topic segmentation

**What it does**

It detects topic changes by measuring how much the _words being used_ change over time.
**Mechanism**

- Split the transcript into fixed time windows (example: 20–40 seconds).
    
- Convert each window’s text into a vector based on word frequency.
    
- Compare consecutive vectors using cosine similarity.
    
- A large drop in similarity indicates a likely topic boundary.
    

**What it captures well**

- Clear shifts in subject matter
    
- Structured content
    
- Videos where vocabulary changes with topic
    
**What it struggles with**

- Conversational speech
    
- Repetitive phrasing across topics
    
- Paraphrasing that uses similar words for different ideas
    

**Key property**

- Deterministic
    
- Fully explainable
    
- No AI inference involved
    
### **Approach 2. Semantic (meaning-based) topic segmentation**

**What it does**
It detects topic changes by measuring how much the _meaning_ of the text changes, even if vocabulary stays similar.
**Mechanism**

- Split the transcript into fixed time windows.
    
- Convert each window into a dense semantic vector (embedding).
    
- Compare consecutive embeddings using cosine similarity.
    
- A large drop in similarity indicates a likely topic boundary.
**What it captures well**

- Meaning shifts with similar wording
    
- Conversational and narrative content
    
- Implicit topic changes
    
**What it struggles with**

- Requires a model or API
    
- Less transparent than word counts
    
- Still needs threshold tuning
    
**Key property*

- More robust to real speech
    
- Still efficient if done window-by-window
    
- Common in modern NLP systems
    
## **4. Learning hooks. What to search and study yourself**
### **For Approach 1**
Official concepts to search:

- **“TF-IDF text similarity”**
    
- **“Cosine similarity NLP”**
    
- **“Topic segmentation lexical cohesion”**
    
What level to learn:

- Beginner to intermediate is enough.
    
- Focus on intuition and cosine similarity behavior.
    
### **For Approach 2**

Official concepts to search:

- **“Sentence embeddings semantic similarity”**
    
- **“Text embeddings cosine similarity”**
    
- **“Topic segmentation using embeddings”**


Optional deeper topics (later):

- **“Change point detection time series”**
    
- **“Text segmentation NLP”**

What level to learn:

- Conceptual understanding first.
    
- You do not need to train models.
### **One clarification to avoid a misconception**

Approach 2 is **not harder conceptually** than Approach 1.

It is harder operationally. The logic is the same, only the representation changes.





I will go with approach 2

Yes, so only do the deterministic rule when, or don't do, or do the deterministic rule when the start time and end time of a snippet are in different, are different multiples of 25, I guess. So start time is 74, that would, you would do 75, or no, you would do, you would do 74 divided by 25, you would get, with integer division, you would get 2.9 or something, and you basically do the, I think, the floor function to basically remove the 9, and you would get a 2, and with the 90, you would do 90 divided by 25, you would get a 3.8 or whatever, and top of the 8, you are stuck with the 3. Now these are different, so you would do the deterministic rule, but in the case of the interval being 60 to 70, both 60 divided by 25 and 70 divided by 25 would, after chopping up the decimal, would give you a 2 as the answer, so there would be no need to look at a different interval. And now, basically, I want you to map this idea in words.

A. Frequency-based embeddings (TF-IDF)

What they are
	•	Vectors based on word counts and rarity.
	•	Each dimension corresponds to a word.
	•	Meaning comes from frequency patterns, not semantics.

Key property
	•	Same word always maps to the same dimension.
	•	No understanding of context.

Example
“mine” in Minecraft vs “mine” in English language
→ treated as the same word.

This is not really an embedding in the modern sense, but it is often grouped here historically.

⸻

B. Prediction-based embeddings (Word2Vec)

These learn vectors by predicting words from context or context from words.

CBOW (Continuous Bag of Words)
	•	Predicts a word given surrounding words.

Skip-gram
	•	Predicts surrounding words given a word.

Key property
	•	Words with similar contexts get similar vectors.
	•	Still one vector per word, regardless of context.

Limitation
“bank” (river bank vs money bank) still has one vector.

⸻

C. GloVe (Global Vectors)

What it is
	•	Uses global word co-occurrence statistics.
	•	Combines count-based ideas with prediction ideas.

Key property
	•	Still static embeddings.
	•	Often more stable than Word2Vec.

⸻

D. Contextual embeddings (Transformer-based)

This is the major shift.

What they do
	•	A word’s vector depends on the sentence it appears in.
	•	“mine” in “mining diamonds” ≠ “mine” in “that is mine”.

Key property
	•	Vectors represent meaning, not just word identity.
	•	Usually operate at sentence or paragraph level.

This is what people usually mean today by “embeddings”.



okay so I didn't know that I thought you could only put two segments for the sim in the similarity model or is that true true right you can only put two segments for the sim in the similarity model or wait no no no no wait I'm kind of confused here because the original thing that you encoded the sentences it was a list of three strings then it gave you a vector based on the fact there were three strings in the list and then the similarity model said basically the first segment 0 and segment 0 are basically 100% similar obviously segment 0 and segment 1 are 0.666 similar segment 0 and segment 2 are 0.1046 similar I don't care about segment 0 and segment 2 comparison I only care about segment 0 and segment 1 and I care about what segment 1 and segment 2 since there are only three segments there would only be two comparisons 1 and 2, 2 and 3 or in more in these terms 0 and 1, 1 and 2, 0, 1, 1, and 2 but if there were more I would do it it would be 2 and 3, 3 and 4, 4 and 5, and so on right and I would have a percentage or I can turn each number between 0 and 1 into a percentage so in this case 0 and 1 can turn into 66.6 percent and segment 1 and 2 can turn into 14.11 percent and so on I can basically get the percent similarity of adjacent segments from just one line of code in the format of a 2d list and I can reach those numbers starting at index 0 and 1 and incrementing both indices by plus 1 and saving those results so basically I may be getting ahead of myself but probably not but once I get the tensor which is going to be a n by n matrix and then I basically check n and n plus 1 index so 0 and 0 plus 1, 1 and 1 plus 2 and I basically increase n every time I basically add 1 to n and n plus 1 each iteration of the I guess the for loop how do I work with these results let's make up or let's have a theoretical percentages just for the sake of testing Let's say first percentage is 90, 80, 60, 55. Wait, wait, wait, wait, wait, wait, wait. This is interesting. No, no, no. Yeah, yeah. And then 30 percent. And let's say my percentage or constant percent I want to check whether it's above or below is 50 or 0.5. So then I would say the 90 percent segment, zero and one, are a pass or are part of one topic. One and two are part of one topic. Two and three are part of one topic. Three and four, which is 55 percent. But segment four and five are 30 percent. That would not be a topic since it's below the 50 percent mark. But this is kind of a risky problem. I would say if you then compare top segment zero and segment four, it is going to be far below 50 percent. Is that not something you should worry about? Because if a video is really good and a transition, so they slowly transition from, let's say, speed running, which consists of five segments. To building. Consisting of three segments and then redstone consisting of just one segment. Then theoretically, or or a lot of the times, if the transitions are between topics are good, I will get percentages above 50 percent. So what I'm thinking or what I'm proposing is I compare the first segment to the next and the segments until I get a percent similarity of less than 50 percent. So in practicality, I compare zero with one. It's 90 percent. Zero and two, it's 80 percent. Zero and three, it's 55 percent. Zero and four, it's 20 percent. So my topic would only consist of zero, one, two and three. And then I start with the next topic and its first segment being four. I compare four with five, four with six and so on. That is what I'm proposing.