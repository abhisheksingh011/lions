// Backend URL. When opened locally we talk to the local FastAPI server;
// otherwise (GitHub Pages) we talk to the Hugging Face Space.
// Space URL format: https://<username>-<space-name>.hf.space
const PROD_BACKEND = "https://voice4varun-cricket.hf.space";
const LOCAL_BACKEND = "http://127.0.0.1:8000";

const host = location.hostname;
const isLocal = host === "localhost" || host === "127.0.0.1" || host === "";
window.BACKEND_URL = isLocal ? LOCAL_BACKEND : PROD_BACKEND;
