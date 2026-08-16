const config = window.VIDEO_CONDENSER_CONFIG || {};
const apiBase = String(config.API_BASE_URL || "").replace(/\/$/, "");

const form = document.querySelector("#condense-form");
const urlInput = document.querySelector("#video-url");
const objectiveInput = document.querySelector("#objective");
const objectiveCount = document.querySelector("#objective-count");
const submitButton = document.querySelector("#submit-button");
const buttonLabel = submitButton.querySelector(".button-label");
const errorPanel = document.querySelector("#error-panel");
const errorMessage = document.querySelector("#error-message");
const progressZone = document.querySelector("#progress-zone");
const progressContent = document.querySelector("#progress-content");
const progressTrack = document.querySelector(".progress-track");
const progressBar = document.querySelector("#progress-bar");
const processTitle = document.querySelector("#process-title");
const processTime = document.querySelector("#process-time");
const viewButton = document.querySelector("#view-button");
const stageLabels = [...document.querySelectorAll("[data-stage]")];

const resultStorageKey = "video-condenser-result";
const stageThresholds = [0, 10, 75, 85];
const stageCopy = [
  "Fetching the source video",
  "Analyzing speech and meaning",
  "Condensing around your objective",
  "Stitching the selected moments",
];

let activeJobId;
let fakeProgress = 0;
let actualTailProgress = 0;
let progressTimer;
let startedAt;

objectiveInput.addEventListener("input", () => {
  objectiveCount.textContent = `${objectiveInput.value.length} / 300`;
  clearError(objectiveInput, "objective-error");
});

urlInput.addEventListener("input", () => clearError(urlInput, "url-error"));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!validate()) return;

  beginProcessing();

  try {
    const response = await fetch(`${apiBase}/condense`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        url: urlInput.value.trim(),
        objective: objectiveInput.value.trim(),
      }),
    });

    if (!response.ok) throw new Error(await responseError(response));

    const job = await response.json();
    if (!job.job_id) throw new Error("The server did not create a processing job.");

    activeJobId = job.job_id;
    const completedJob = await waitForJob(job);
    await finishProgress(completedJob);
  } catch (error) {
    failProgress(friendlyError(error));
  } finally {
    setFormDisabled(false);
  }
});

document.querySelector("#retry-button").addEventListener("click", () => form.requestSubmit());

function validate() {
  let valid = true;
  const rawUrl = urlInput.value.trim();

  try {
    const parsed = new URL(rawUrl);
    const host = parsed.hostname.replace(/^www\./, "");
    if (!["youtube.com", "m.youtube.com", "youtu.be"].includes(host)) throw new Error();
  } catch {
    setFieldError(urlInput, "url-error", "Enter a valid YouTube URL.");
    valid = false;
  }

  if (objectiveInput.value.trim().length < 8) {
    setFieldError(objectiveInput, "objective-error", "Describe what the final cut should focus on.");
    valid = false;
  }

  return valid;
}

function setFieldError(input, id, message) {
  input.setAttribute("aria-invalid", "true");
  document.querySelector(`#${id}`).textContent = message;
}

function clearError(input, id) {
  input.removeAttribute("aria-invalid");
  document.querySelector(`#${id}`).textContent = "";
}

function setFormDisabled(disabled) {
  submitButton.disabled = disabled;
  form.querySelectorAll("input, textarea").forEach((field) => {
    field.disabled = disabled;
  });
  buttonLabel.textContent = disabled ? "Condensing…" : "Condense Video";
}

function beginProcessing() {
  clearInterval(progressTimer);
  sessionStorage.removeItem(resultStorageKey);
  errorPanel.hidden = true;
  progressZone.hidden = false;
  viewButton.hidden = true;
  progressContent.hidden = false;
  progressZone.className = "progress-zone is-running";
  setFormDisabled(true);

  activeJobId = undefined;
  fakeProgress = 2;
  actualTailProgress = 0;
  startedAt = Date.now();
  renderProgress(fakeProgress);
  updateElapsedTime();

  progressTimer = window.setInterval(() => {
    const elapsedSeconds = (Date.now() - startedAt) / 1000;
    fakeProgress = Math.max(progressForElapsed(elapsedSeconds), actualTailProgress);
    renderProgress(fakeProgress);
    updateElapsedTime();
  }, 1000);
}

function progressForElapsed(elapsedSeconds) {
  // The first 10% preserves the old pace. The middle uses the requested
  // accelerating x^1.5 curve, then a short transition leads into a cubic
  // ease-out. The curve stops at 95%; only a completed backend job reaches 100.
  const openingDuration = 20;
  const accelerationDuration = 150;
  const transitionDuration = 60;
  const slowdownDuration = 180;

  if (elapsedSeconds <= openingDuration) {
    return 2 + 8 * (elapsedSeconds / openingDuration);
  }

  let phaseTime = elapsedSeconds - openingDuration;
  if (phaseTime <= accelerationDuration) {
    const x = phaseTime / accelerationDuration;
    return 10 + 65 * Math.pow(x, 1.5);
  }

  phaseTime -= accelerationDuration;
  if (phaseTime <= transitionDuration) {
    const x = phaseTime / transitionDuration;
    return 75 + 10 * (1 - Math.pow(1 - x, 2));
  }

  phaseTime -= transitionDuration;
  const x = Math.min(1, phaseTime / slowdownDuration);
  return 85 + 10 * (1 - Math.pow(1 - x, 3));
}

function renderProgress(progress) {
  const safeProgress = Math.max(0, Math.min(100, progress));
  const stageIndex = getStageIndex(safeProgress);

  progressBar.style.width = `${safeProgress}%`;
  progressTrack.setAttribute("aria-valuenow", String(Math.round(safeProgress)));
  processTitle.textContent = safeProgress >= 100 ? "Your condensed video is ready" : stageCopy[stageIndex];

  stageLabels.forEach((label, index) => {
    label.classList.toggle("is-complete", safeProgress >= 100 || index < stageIndex);
    label.classList.toggle("is-active", safeProgress < 100 && index === stageIndex);
  });
}

function getStageIndex(progress) {
  if (progress >= stageThresholds[3]) return 3;
  if (progress >= stageThresholds[2]) return 2;
  if (progress >= stageThresholds[1]) return 1;
  return 0;
}

function updateElapsedTime() {
  if (!startedAt) return;
  const elapsed = Math.floor((Date.now() - startedAt) / 1000);
  processTime.textContent = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`;
}

async function waitForJob(job) {
  const statusUrl = absoluteApiUrl(job.status_url || `/jobs/${job.job_id}`);

  while (activeJobId === job.job_id) {
    const response = await fetch(statusUrl, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(await responseError(response));

    const current = await response.json();
    if (current.status === "completed") return current;
    if (current.status === "failed") {
      throw new Error(current.error || "The video could not be processed.");
    }

    if (Number.isFinite(Number(current.progress)) && Number(current.progress) >= 95) {
      actualTailProgress = Math.min(99, Number(current.progress));
      fakeProgress = Math.max(fakeProgress, actualTailProgress);
      renderProgress(fakeProgress);
    }

    await delay(1500);
  }

  throw new Error("Processing was cancelled.");
}

async function finishProgress(job) {
  clearInterval(progressTimer);
  fakeProgress = 100;
  renderProgress(100);
  updateElapsedTime();

  const resultUrl = absoluteApiUrl(job.result_url || `/results/${job.job_id}`);
  const result = {
    jobId: job.job_id,
    resultUrl,
    title: job.title || "Condensed Video",
  };

  sessionStorage.setItem(resultStorageKey, JSON.stringify(result));
  viewButton.href = `result.html?job=${encodeURIComponent(job.job_id)}`;

  await delay(550);
  progressContent.hidden = true;
  viewButton.hidden = false;
  progressZone.className = "progress-zone is-ready";
}

function failProgress(message) {
  clearInterval(progressTimer);
  activeJobId = undefined;
  progressZone.className = "progress-zone is-error";
  processTitle.textContent = "Processing stopped";
  showError(message);
}

function absoluteApiUrl(value) {
  if (/^https?:\/\//i.test(value)) return value;
  return `${apiBase}/${String(value).replace(/^\//, "")}`;
}

function delay(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function showError(message) {
  errorMessage.textContent = message;
  errorPanel.hidden = false;
  errorPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function responseError(response) {
  try {
    const data = await response.clone().json();
    if (typeof data.detail === "string") return data.detail;
    if (typeof data.message === "string") return data.message;
  } catch {
    // The generic status message below covers non-JSON server responses.
  }
  return `The server returned ${response.status}. Please try again.`;
}

function friendlyError(error) {
  if (!navigator.onLine) return "You appear to be offline. Reconnect and try again.";
  if (error instanceof TypeError) return "The backend could not be reached. Check the API address and try again.";
  return error.message || "Something unexpected happened. Please try again.";
}
