const status = document.getElementById("status");
const start = document.getElementById("start");
const stopBtn = document.getElementById("stop");
const calibrateBtn = document.getElementById("calibrate");
const tokenField = document.getElementById("token");
const modeField = document.getElementById("mode");
const runModeField = document.getElementById("runMode");

let starting = false;
let localError = false;

const sessionStore = chrome.storage?.session;
if (sessionStore) {
  sessionStore.get(["pairingToken", "matchMode", "runMode"]).then((saved) => {
    if (!tokenField.value && typeof saved.pairingToken === "string") tokenField.value = saved.pairingToken;
    if (modeField && typeof saved.matchMode === "string") modeField.value = saved.matchMode;
    if (runModeField && typeof saved.runMode === "string") runModeField.value = saved.runMode;
    updateStartLabel();
  }).catch(() => {});
}

function updateStartLabel() {
  const val = runModeField ? runModeField.value : (document.getElementById("execute")?.checked ? "execute" : "inspect");
  start.textContent = val === "execute" ? "Start automatic play" : val === "advisor" ? "Start Advisor" : "Capture one frame";
}

tokenField.addEventListener("change", () => {
  sessionStore?.set({ pairingToken: tokenField.value.trim() }).catch(() => {});
});
modeField?.addEventListener("change", () => {
  sessionStore?.set({ matchMode: modeField.value }).catch(() => {});
});
document.getElementById("execute")?.addEventListener("change", updateStartLabel);
runModeField?.addEventListener("change", () => {
  updateStartLabel();
  sessionStore?.set({ runMode: runModeField.value }).catch(() => {});
});
updateStartLabel();

function validTokenOrThrow() {
  const token = tokenField.value.trim();
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(token)) {
    throw new Error("Invalid token characters. Copy only the contents of local/pairing-token.txt.");
  }
  return token;
}

start.addEventListener("click", async () => {
  localError = false;
  starting = true;
  start.disabled = true;
  status.textContent = "Checking local bridge…";
  try {
    const token = validTokenOrThrow();
    if (sessionStore) await sessionStore.set({ pairingToken: token, matchMode: modeField?.value || "training", runMode: runModeField?.value || "advisor" });
    const execute = runModeField ? runModeField.value === "execute" : Boolean(document.getElementById("execute")?.checked);
    const advisor = runModeField ? runModeField.value === "advisor" : false;
    const result = await chrome.runtime.sendMessage({
      type: "start",
      token,
      mode: modeField?.value || "training",
      execute,
      advisor,
    });
    status.textContent = result.status || result.error;
    if ((execute || advisor) && result.status?.startsWith("Connected;")) window.close();
  } catch (error) {
    localError = true;
    status.textContent = error.message;
  } finally {
    starting = false;
    start.disabled = false;
  }
});

stopBtn.addEventListener("click", async () => {
  localError = false;
  const result = await chrome.runtime.sendMessage({ type: "stop" });
  status.textContent = result.status;
});

calibrateBtn?.addEventListener("click", async () => {
  localError = false;
  try {
    const token = validTokenOrThrow();
    const result = await chrome.runtime.sendMessage({ type: "calibrate", token });
    status.textContent = result.status || result.error;
    if (result.status?.startsWith("Calibration started")) window.close();
  } catch (error) {
    localError = true;
    status.textContent = error.message;
  }
});

chrome.runtime.sendMessage({ type: "status" }).then((result) => {
  if (!localError && result?.status) status.textContent = result.status;
}).catch(() => {});

setInterval(() => {
  if (!starting && !localError) {
    chrome.runtime.sendMessage({ type: "status" }).then((result) => {
      if (result?.status) status.textContent = result.status;
    }).catch(() => {});
  }
}, 500);
