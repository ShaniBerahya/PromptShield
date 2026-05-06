console.log("PromptShield content script loaded!");

let allowNextSubmit = false;

function findPromptBox() {
  const selectors = [
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

function showPromptShieldModal(result, onContinue, onCancel) {
  const existing = document.getElementById("promptshield-modal");
  if (existing) {
    existing.remove();
  }

  const modal = document.createElement("div");
  modal.id = "promptshield-modal";

  const risk = result.risk || "unknown";
  const score = result.score ?? "N/A";
  const reasons = result.reasons || [];

  modal.innerHTML = `
    <div class="promptshield-backdrop"></div>
    <div class="promptshield-box">
      <h2>PromptShield Warning</h2>
      <p class="promptshield-risk">Risk: <strong>${risk.toUpperCase()}</strong> (${score}/100)</p>

      <p>This prompt may contain prompt injection patterns.</p>

      <h3>Why it was flagged:</h3>
      <ul>
        ${reasons.map(reason => `<li>${escapeHtml(reason)}</li>`).join("")}
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

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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
      document.activeElement === promptBox;

    if (!isEnterSend) return;

    if (allowNextSubmit) {
      allowNextSubmit = false;
      return;
    }

    const text = getPromptText(promptBox);

    if (!text) return;

    event.preventDefault();
    event.stopPropagation();

    const response = await analyzePrompt(text);

    if (!response || !response.ok) {
      alert("PromptShield could not reach the backend.");
      return;
    }

    const result = response.result;

    if (result.score < 50) {
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