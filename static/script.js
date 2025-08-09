// State: keep track if we're in Search or Submit mode
let isSearchMode = true;

const modeToggle = document.getElementById("modeToggle");
const mainActionBtn = document.getElementById("mainActionBtn");
const imageLabel = document.getElementById("imageLabel");
const imageInput = document.getElementById("imageInput");
const userInput = document.getElementById("userInput");
const resultBox = document.getElementById("resultBox");
const dropdown = document.getElementById("actionDropdown");

// Toggle between Search and Submit
modeToggle.addEventListener("click", () => {
  isSearchMode = !isSearchMode;
  modeToggle.textContent = isSearchMode ? "Search" : "Submit";
  mainActionBtn.textContent = isSearchMode ? "Search" : "Submit";
  imageLabel.style.display = isSearchMode ? "none" : "";
  modeToggle.classList.toggle("toggled", !isSearchMode);
  clearOutput();
});

// Main action button handler
mainActionBtn.addEventListener("click", () => {
  clearOutput();
  if (isSearchMode) {
    performSearch();
  } else {
    performSubmit();
  }
});

// Also submit on Enter key in text input
userInput.addEventListener("keyup", function (e) {
  if (e.key === "Enter") {
    mainActionBtn.click();
  }
});

function performSearch() {
  const query = userInput.value.trim();
  if (!query) {
    showStatus("Please enter a search term.", false);
    return;
  }
  // Fake search result generation (replace with your API logic)
  setTimeout(() => {
    resultBox.innerHTML = `
      <div class="result-item"><b>Result 1:</b> "${query}" related result (type: ${dropdown.value})</div>
      <div class="result-item"><b>Result 2:</b> Another ${dropdown.value} match for "${query}".</div>
      <div class="result-item"><b>Result 3:</b> More info for "${query}".</div>
    `;
  }, 400);
}

function performSubmit() {
  const inputVal = userInput.value.trim();
  if (!inputVal && !imageInput.files.length) {
    showStatus("Please provide text or select an image to submit.", false);
    return;
  }

  // Fake a success/failure response
  setTimeout(() => {
    if (Math.random() < 0.75) {
      let imgMsg = imageInput.files.length
        ? `<br>📷 Image attached: <b>${imageInput.files[0].name}</b>`
        : "";
      showStatus("Submitted successfully!" + imgMsg, true);
      userInput.value = "";
      imageInput.value = "";
    } else {
      showStatus("Submission failed. Please try again.", false);
    }
  }, 600);
}

function showStatus(message, success) {
  resultBox.innerHTML = `<span class="${
    success ? "status-success" : "status-fail"
  }">${message}</span>`;
}

function clearOutput() {
  resultBox.innerHTML = "";
}
