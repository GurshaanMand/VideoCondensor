const config = window.VIDEO_CONDENSER_CONFIG || {};
const apiBase = String(config.API_BASE_URL || "").replace(/\/$/, "");

const videoFrame = document.querySelector("#video-frame");
const video = document.querySelector("#result-video");
const videoState = document.querySelector("#video-state");
const downloadLink = document.querySelector("#download-link");
const resultStorageKey = "video-condenser-result";

const queryJobId = new URLSearchParams(window.location.search).get("job");
const storedResult = readStoredResult();
const jobId = validJobId(queryJobId) ? queryJobId : storedResult?.jobId;

if (!jobId) {
  showVideoError("No condensed video was selected. Return to the form and create one first.");
} else {
  const storedUrlMatches = storedResult?.jobId === jobId && storedResult?.resultUrl;
  const resultUrl = storedUrlMatches ? storedResult.resultUrl : absoluteApiUrl(`/results/${jobId}`);
  video.src = resultUrl;
  downloadLink.href = resultUrl;
}

video.addEventListener("loadedmetadata", () => {
  videoFrame.classList.remove("is-error");
  videoFrame.classList.add("is-ready");
  downloadLink.hidden = false;
});

video.addEventListener("error", () => {
  showVideoError("The condensed video could not be loaded. It may have expired or the backend may be unavailable.");
});

function readStoredResult() {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(resultStorageKey));
    return validJobId(parsed?.jobId) ? parsed : undefined;
  } catch {
    return undefined;
  }
}

function validJobId(value) {
  return typeof value === "string" && /^[a-f0-9]{32}$/i.test(value);
}

function absoluteApiUrl(value) {
  if (/^https?:\/\//i.test(value)) return value;
  return `${apiBase}/${String(value).replace(/^\//, "")}`;
}

function showVideoError(message) {
  video.removeAttribute("src");
  videoFrame.classList.remove("is-ready");
  videoFrame.classList.add("is-error");
  videoState.textContent = message;
  downloadLink.hidden = true;
}
