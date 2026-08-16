// Keep this empty when FastAPI serves the frontend from the same address.
// Before deploying the frontend separately, replace the empty string with the
// public FastAPI address, for example: "https://api.example.com".
const deployedApiBaseUrl = "";

const localHosts = new Set(["127.0.0.1", "localhost"]);
const isSeparateLocalPreview =
  localHosts.has(window.location.hostname) &&
  Boolean(window.location.port) &&
  window.location.port !== "8000";

window.VIDEO_CONDENSER_CONFIG = {
  API_BASE_URL:
    deployedApiBaseUrl ||
    (isSeparateLocalPreview
      ? `${window.location.protocol}//${window.location.hostname}:8000`
      : ""),
};
