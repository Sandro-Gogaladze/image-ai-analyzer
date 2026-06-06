// ← Update this after serverless deploy
const API_URL = "https://9uzn20a7qa.execute-api.us-east-1.amazonaws.com/dev/analyze";

const dropZone    = document.getElementById("dropZone");
const imageInput  = document.getElementById("imageInput");
const dropContent = document.getElementById("dropContent");
const preview     = document.getElementById("preview");
const submitBtn   = document.getElementById("submitBtn");
const btnText     = document.getElementById("btnText");
const btnLoader   = document.getElementById("btnLoader");
const resultCard  = document.getElementById("resultCard");
const resultMeta  = document.getElementById("resultMeta");
const resultJson  = document.getElementById("resultJson");
const errorCard   = document.getElementById("errorCard");
const errorMsg    = document.getElementById("errorMsg");

let selectedFile = null;

// --- Model card selection ---
document.querySelectorAll(".model-card").forEach(card => {
  card.addEventListener("click", () => {
    document.querySelectorAll(".model-card").forEach(c => c.classList.remove("selected"));
    card.classList.add("selected");
  });
});

// --- Drop zone click ---
dropZone.addEventListener("click", () => imageInput.click());

// --- Drag & drop ---
dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) setFile(file);
});

// --- File input change ---
imageInput.addEventListener("change", () => {
  if (imageInput.files[0]) setFile(imageInput.files[0]);
});

function setFile(file) {
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = e => {
    preview.src = e.target.result;
    preview.hidden = false;
    dropContent.hidden = true;
  };
  reader.readAsDataURL(file);
  submitBtn.disabled = false;
}

// --- Form submit ---
document.getElementById("uploadForm").addEventListener("submit", async e => {
  e.preventDefault();
  if (!selectedFile) return;

  const model = document.querySelector('input[name="model"]:checked').value;

  // Show loader
  btnText.hidden = true;
  btnLoader.hidden = false;
  submitBtn.disabled = true;
  resultCard.hidden = true;
  errorCard.hidden = true;

  try {
    // Convert image to base64
    const base64 = await toBase64(selectedFile);
    const base64Data = base64.split(",")[1]; // strip "data:image/...;base64,"

    const payload = {
      image: base64Data,
      model: model,
      filename: selectedFile.name,
    };

    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (response.ok) {
      resultMeta.innerHTML = `
        <strong>Model:</strong> ${data.model} &nbsp;|&nbsp;
        <strong>File:</strong> ${data.filename} &nbsp;|&nbsp;
        <strong>S3:</strong> ${data.s3_url}
      `;
      resultJson.textContent = JSON.stringify(data.result, null, 2);
      resultCard.hidden = false;
    } else {
      throw new Error(data.error || "Unknown error");
    }

  } catch (err) {
    errorMsg.textContent = err.message;
    errorCard.hidden = false;
  } finally {
    btnText.hidden = false;
    btnLoader.hidden = true;
    submitBtn.disabled = false;
  }
});

function toBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
