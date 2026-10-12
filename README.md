# Video Condenser

Video Condenser is an end-to-end web application that turns long-form YouTube videos into shorter, objective-focused cuts. A user provides a public YouTube URL and describes what they care about; the application analyzes the transcript, selects the most useful sections, and renders a condensed MP4 with the original video and audio.

## Project Status

Video Condenser is a working MVP. The complete workflow has been tested locally, containerized with Docker, and deployed to AWS ECS.

The local application works end to end. The AWS deployment currently has an external ingestion limitation: YouTube may block transcript and media requests originating from cloud-provider IP addresses. Production URL ingestion therefore requires a residential proxy, a user-upload workflow, or a residential/self-hosted ingestion worker. This limitation affects how source videos enter the system; it does not affect the transcript analysis or video-rendering pipeline.

In one end-to-end test, the application condensed a 1 hour 44 minute podcast to approximately 52 minutes while preserving continuous video and natural audio across most transitions.

## Features

- Objective-driven transcript analysis
- Semantic embeddings with Sentence Transformers
- Topic grouping and coherence scoring
- Novelty and redundancy detection
- Density and informativeness scoring
- Duration-aware segment selection
- Background job processing with live status updates
- Responsive web interface with progress and result views
- In-browser playback and MP4 download
- Docker and Docker Compose support
- Health checks, input validation, queue limits, storage checks, and automatic job cleanup
- AWS ECS-compatible container deployment

## How It Works

1. The user submits a YouTube URL and a condensation objective.
2. The API validates the request and creates a background job.
3. The application verifies that a usable transcript is available.
4. Transcript entries are grouped into time-based segments.
5. Sentence Transformers generates an embedding for each segment.
6. Related segments are grouped into topics.
7. Each segment is scored for objective relevance, coherence, novelty, density, and informativeness.
8. Lower-value or repetitive segments are removed while important context is protected.
9. The source video is downloaded with `yt-dlp`.
10. FFmpeg renders the selected ranges and joins them into a final MP4.
11. The frontend displays the completed video and provides a download link.

## Scoring and Filtering

The analysis runs on the transcript only; video frames are never inspected.

**Segmentation.** Caption snippets are bucketed into 20-second windows. A snippet that straddles a boundary goes to the window that holds more of it.

**Embeddings.** Each segment's text is embedded with `all-MiniLM-L6-v2` (384 dimensions). The model is downloaded at image build time and loaded offline at runtime.

**Topic grouping.** Segments are walked in order. A segment joins the current topic when its cosine similarity to the topic's running centroid is above 0.37. Before closing a topic, the grouper looks ahead up to two segments, so a short aside does not split one discussion into two topics.

**Signals.** Every segment gets five scores between 0 and 1:

| Signal | How it is computed |
| --- | --- |
| Objective relevance | Cosine similarity to the embedded objective, blended with its percentile rank within the video and keyword overlap with the objective |
| Informativeness | Word count, vocabulary diversity, and whether the text contains specifics such as numbers or step/reason words |
| Novelty | One minus the highest similarity to the previous six segments in the same topic |
| Coherence | Similarity to the topic centroid |
| Density | Words per second |

**Final score.** A weighted sum (`0.58` relevance, `0.16` informativeness, `0.10` novelty, `0.10` coherence, `0.06` density), with penalties for off-objective, low-information, and redundant segments. Scores are then rescaled between the video's 10th and 90th percentiles, and segments with weak objective relevance are capped so rescaling cannot push them to the top.

**Filtering.** Removal happens in three passes: clear rejects first, then the lowest-scoring segments until about 40% of the duration is gone, then a cleanup of very weak leftovers. No more than 60% is ever removed. High-value segments are protected, and so are decent neighbours within three seconds of them, which keeps the lead-in and follow-up to an important moment.

**Rendering.** Kept ranges less than 0.35 seconds apart are merged. Each range is re-encoded with FFmpeg (`libx264`, AAC) and the clips are joined with the concat demuxer.

The weights and thresholds were tuned by hand against a small number of videos. They are not learned and there is no labelled evaluation set.

## Architecture

```text
Browser
  -> FastAPI job API
  -> Transcript analysis and semantic filtering
  -> yt-dlp source download
  -> FFmpeg section rendering and stitching
  -> Local job storage
  -> Browser playback/download
```

The MVP uses one application process and local storage. Job metadata and rendered videos are not shared between multiple application instances.

## Tech Stack

### Backend and analysis

- Python 3.11
- FastAPI
- Sentence Transformers
- PyTorch
- scikit-learn
- YouTube Transcript API
- yt-dlp
- FFmpeg

### Frontend

- HTML
- CSS
- Vanilla JavaScript
- Canvas-based animated background

### Infrastructure

- Docker and Docker Compose
- Amazon ECS
- Amazon ECR
- Amazon CloudWatch Logs

## API

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/` | Serve the frontend |
| `GET` | `/health` | Application health check |
| `POST` | `/condense` | Create a condensation job |
| `GET` | `/jobs/{job_id}` | Read job status and progress |
| `GET` | `/results/{job_id}` | Stream the completed MP4 |
| `GET` | `/docs` | OpenAPI documentation |

Example request:

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "objective": "Keep the implementation steps, practical advice, and important reasoning."
}
```

`POST /condense` returns a job identifier. The frontend polls the job-specific status endpoint until the result is ready.

## Run Locally with Docker

### Requirements

- Docker Desktop
- At least 16 GB of system memory recommended for local development
- Sufficient free disk space for the source video, temporary clips, model cache, and final output

Start the application:

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000
```

Stop the application:

```bash
docker compose down
```

## Run Locally without Docker

The project also requires FFmpeg to be installed on the host system.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn api:app --host 127.0.0.1 --port 8000
```

## Tests

Run the backend and FFmpeg integration tests with:

```bash
python -m unittest discover -s tests -v
```

The test suite covers request validation, URL validation, queue admission, job-state persistence, successful and failed jobs, transcript processing, range merging, and a synthetic FFmpeg render-and-stitch workflow.

## Configuration

The main runtime limits can be configured with environment variables:

| Variable | Default | Description |
| --- | ---: | --- |
| `MAX_CONCURRENT_JOBS` | `1` | Jobs processed simultaneously |
| `MAX_PENDING_JOBS` | `2` | Maximum queued and active jobs |
| `MAX_VIDEO_DURATION_SECONDS` | `10800` | Maximum accepted source duration |
| `JOB_RETENTION_HOURS` | `24` | Retention period for finished jobs |
| `JOB_CLEANUP_INTERVAL_SECONDS` | `900` | Cleanup interval |
| `MIN_FREE_SPACE_GB` | `5` | Required free working space |

## Deployment Notes

The current MVP must run with exactly one Uvicorn worker and one ECS task, with autoscaling disabled. Multiple tasks can return inconsistent job status because state and results are stored locally. A deployment or task replacement can interrupt an active job.

Allocate at least 30 GB of ephemeral storage for the container image, model cache, source video, temporary clips, and final MP4.

YouTube can block requests from AWS and other datacenter IP ranges even when the same video works locally. Reliable public URL ingestion requires one of the following:

- A residential proxy used by both the transcript and media download clients
- Direct MP4/transcript upload support
- A residential or user-side ingestion worker

Do not commit proxy credentials, cookies, AWS keys, downloaded videos, runtime job data, or model caches to the repository.

## Current Limitations

- Filtering quality depends on transcript quality.
- Broad or ambiguous objectives can produce weaker relevance scores.
- Some useful segments may be removed or low-value segments retained.
- Cuts occur near transcript boundaries, so occasional trailing words or examples may be clipped.
- Only public videos with usable transcripts are supported by the URL workflow.
- YouTube may block transcript or media access from cloud-provider IP addresses.
- Processing is CPU-, memory-, storage-, and time-intensive for long videos.
- Job state and results are local to one application instance.
- The current MVP does not include authentication, shared cloud storage, or distributed workers.

## Future Improvements

- Add direct video and transcript uploads
- Support residential-proxy configuration for hosted URL ingestion
- Store generated videos in Amazon S3
- Store job state in a shared database
- Move processing to a durable queue and worker architecture
- Improve objective rewriting and redundancy detection
- Add configurable boundary padding to reduce abrupt semantic cuts
- Add authentication, rate limiting, and per-user quotas
- Add automated deployment and monitoring

## Example Objectives

- Keep the implementation steps, practical advice, and important reasoning.
- Extract the main arguments and strongest supporting examples; remove introductions, promotions, repetition, and unrelated stories.
- Focus on negotiation techniques, strategic questions, identifying manipulation, and responding under pressure.

## Responsible Use

Only process videos you are permitted to download and transform. Users are responsible for respecting copyright, platform terms, privacy, and applicable laws.

