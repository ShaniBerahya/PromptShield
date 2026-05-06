console.log("PromptShield background service worker loaded!");

const BACKEND_URL = "http://localhost:8000/analyze";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== "ANALYZE_PROMPT") {
    return;
  }

  fetch(BACKEND_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      text: message.text
    })
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`);
      }

      return response.json();
    })
    .then((data) => {
      sendResponse({
        ok: true,
        result: data
      });
    })
    .catch((error) => {
      sendResponse({
        ok: false,
        error: error.message
      });
    });

  return true;
});