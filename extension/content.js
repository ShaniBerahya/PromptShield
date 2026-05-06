console.log("PromptShield content script loaded!");

let scanTimeout = null;
let lastScannedText = "";
let latestResult = null;
let allowNextSubmit = false;

function findPromptBox() {
  const selectors = [
    "#prompt-textarea",
    "textarea",
    "div[contenteditable='true']",
    "[role='textbox']"
  ];

  for (const selector of selectors) {
    const element = document.querySelector(selector);
    if (element) {
      return element;
    }
  }

  return null;
}

function getPromptText(promptBox) {
  if (!promptBox) return "";

  if (promptBox.tagName === "TEXTAREA" || promptBox.tagName === "INPUT") {
    return promptBox.value.trim();
  }

  return promptBox.innerText.trim();
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getScorePercent(result) {
  const rawScore = result?.score ?? 0;

  // Your backend returns score between 0 and 1.
  // This converts it to 0-100 for the UI.
  if (rawScore <= 1) {
    return Math.round(rawScore * 100);
  }

  return Math.round(rawScore);
}

function getRiskLevel(result) {
  return result?.risk_level || "unknown";
}

function createOrUpdateScoreBadge(result) {
  let badge = document.getElementById("promptshield-score-badge");

  if (!badge) {
    badge = document.createElement("div");
    badge.id = "promptshield-score-badge";
    document.body.appendChild(badge);
  }

  const risk = getRiskLevel(result);
  const scorePercent = getScorePercent(result);
  const matchedPatterns = result?.matched_patterns || [];
  const matchesCount = result?.matches_count ?? matchedPatterns.length;

  badge.innerHTML = `
    <strong>PromptShield</strong><br>
    Risk: ${escapeHtml(String(risk).toUpperCase())}<br>
    Score: ${scorePercent}/100<br>
    Matches: ${matchesCount}
  `;

  badge.className = "";

  if (scorePercent >= 70 || risk === "high") {
    badge.classList.add("promptshield-high");
  } else if (scorePercent >= 40 || risk === "medium") {
    badge.classList.add("promptshield-medium");
  } else {
    badge.classList.add("promptshield-low");
  }
}

function hideScoreBadge() {
  const badge = document.getElementById("promptshield-score-badge");
  if (badge) {
    badge.remove();
  }
}

function showPromptShieldModal(result, onContinue, onCancel) {
  const existing = document.getElementById("promptshield-modal");
  if (existing) {
    existing.remove();
  }

  const modal = document.createElement("div");
  modal.id = "promptshield-modal";

  const risk = getRiskLevel(result);
  const scorePercent = getScorePercent(result);
  const matchedPatterns = result?.matched_patterns || [];
  const matchesCount = result?.matches_count ?? matchedPatterns.length;

  modal.innerHTML = `
    <div class="promptshield-backdrop"></div>
    <div class="promptshield-box">
      <h2>PromptShield Warning</h2>
      <p class="promptshield-risk">
        Risk: <strong>${escapeHtml(String(risk).toUpperCase())}</strong> (${scorePercent}/100)
      </p>

      <p>This prompt may contain prompt injection patterns.</p>

      <h3>Matched patterns:</h3>
      <p>Matches found: ${matchesCount}</p>
      <ul>
        ${matchedPatterns.map(pattern => `<li>${escapeHtml(pattern)}</li>`).join("")}
      </ul>

      <div class="promptshield-actions">
        <button id="promptshield-cancel">Cancel</button>
        <button id="promptshield-continue">Send Anyway</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  document.getElementById("promptshield-cancel").onclick = () => {
    modal.remove();
    onCancel();
  };

  document.getElementById("promptshield-continue").onclick = () => {
    modal.remove();
    onContinue();
  };
}

async function analyzePrompt(text) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(
      {
        type: "ANALYZE_PROMPT",
        text
      },
      (response) => {
        resolve(response);
      }
    );
  });
}

async function scanCurrentPrompt() {
  const promptBox = findPromptBox();
  const text = getPromptText(promptBox);

  console.log("PromptShield current text:", text);

  if (!text) {
    hideScoreBadge();
    latestResult = null;
    lastScannedText = "";
    return;
  }

  if (text === lastScannedText) {
    return;
  }

  lastScannedText = text;

  const response = await analyzePrompt(text);

  if (!response || !response.ok) {
    console.warn("PromptShield backend error:", response?.error);
    return;
  }

  latestResult = response.result;

  console.log("PromptShield analysis result:", latestResult);

  createOrUpdateScoreBadge(latestResult);
}

function scheduleLiveScan() {
  clearTimeout(scanTimeout);

  scanTimeout = setTimeout(() => {
    scanCurrentPrompt();
  }, 500);
}

document.addEventListener(
  "input",
  (event) => {
    const promptBox = findPromptBox();

    if (!promptBox) return;

    if (event.target === promptBox || promptBox.contains(event.target)) {
      scheduleLiveScan();
    }
  },
  true
);

document.addEventListener(
  "keyup",
  (event) => {
    const promptBox = findPromptBox();

    if (!promptBox) return;

    if (
      document.activeElement === promptBox ||
      promptBox.contains(document.activeElement)
    ) {
      scheduleLiveScan();
    }
  },
  true
);

document.addEventListener(
  "keydown",
  async (event) => {
    console.log("Key pressed:", event.key);
    console.log("Active element:", document.activeElement);

    const promptBox = findPromptBox();

    if (!promptBox) return;

    const isEnterSend =
      event.key === "Enter" &&
      !event.shiftKey &&
      (
        document.activeElement === promptBox ||
        promptBox.contains(document.activeElement)
      );

    if (!isEnterSend) return;

    if (allowNextSubmit) {
      allowNextSubmit = false;
      return;
    }

    const text = getPromptText(promptBox);
    console.log("PromptShield captured text before send:", text);

    if (!text) return;

    event.preventDefault();
    event.stopPropagation();

    const response = await analyzePrompt(text);

    if (!response || !response.ok) {
      alert("PromptShield could not reach the backend.");
      return;
    }

    const result = response.result;
    latestResult = result;

    const risk = getRiskLevel(result);
    const scorePercent = getScorePercent(result);

    createOrUpdateScoreBadge(result);

    if (scorePercent < 50 && risk !== "high" && risk !== "medium") {
      allowNextSubmit = true;

      promptBox.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Enter",
          bubbles: true,
          cancelable: true
        })
      );

      return;
    }

    showPromptShieldModal(
      result,
      () => {
        allowNextSubmit = true;

        promptBox.dispatchEvent(
          new KeyboardEvent("keydown", {
            key: "Enter",
            bubbles: true,
            cancelable: true
          })
        );
      },
      () => {
        console.log("PromptShield blocked sending by user choice.");
      }
    );
  },
  true
);