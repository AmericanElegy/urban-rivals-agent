import { allowedURL, validateAction, validateTarget } from "./policy.js";

const ENDPOINT = "http://127.0.0.1:8876";
const VALID_MODES = new Set(["training", "efc", "tourney"]);
let run = null;
let status = "Not started";
let calibrationToken = null;

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const bounded = async (promise, label, ms = 4000) => {
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error(label + " timed out; stopped")), ms);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
};

async function injectOverlay(tabId) {
  await chrome.scripting.executeScript({ target: { tabId }, files: ["overlay.js"] });
}

async function updateHud(tabId, recommendation) {
  if (!recommendation) return;
  try {
    await injectOverlay(tabId);
    await chrome.scripting.executeScript({
      target: { tabId },
      func: (rec) => window.__urAgentOverlay?.showRecommendation(rec),
      args: [recommendation],
    });
  } catch {}
}

async function clearHud(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: () => window.__urAgentOverlay?.hideRecommendation(),
    });
  } catch {}
}

async function stop(reason = "Stopped") {
  const old = run;
  run = null;
  status = reason;
  if (old) {
    await clearHud(old.tabId);
    if (old.execute) {
      try {
        await chrome.debugger.detach({ tabId: old.tabId });
      } catch {}
    }
    try {
      await fetch(ENDPOINT + "/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + old.token },
        body: JSON.stringify({ run_id: old.id }),
        signal: AbortSignal.timeout(2000),
      });
    } catch {}
  }
}

async function geometry(tabId) {
  const results = await bounded(
    chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const canvas = document.getElementById("unity-canvas");
        if (!canvas || document.visibilityState !== "visible") return null;
        let r = canvas.getBoundingClientRect();
        if (r.y < 0 || r.y + r.height > innerHeight + 1 || r.x < 0 || r.x + r.width > innerWidth + 1) {
          canvas.scrollIntoView({ block: "center", inline: "center", behavior: "instant" });
          r = canvas.getBoundingClientRect();
        }
        return {
          x: r.x,
          y: r.y,
          width: r.width,
          height: r.height,
          pageX: r.x + scrollX,
          pageY: r.y + scrollY,
          viewportWidth: innerWidth,
          viewportHeight: innerHeight,
        };
      },
    }),
    "Canvas geometry"
  );
  const g = results[0]?.result;
  if (
    !g ||
    g.width < 640 ||
    g.height < 320 ||
    g.x < 0 ||
    g.y < 0 ||
    g.x + g.width > g.viewportWidth + 1 ||
    g.y + g.height > g.viewportHeight + 1
  ) {
    throw new Error(`The full Unity canvas must be visible (${g ? `${Math.round(g.width)}x${Math.round(g.height)} at (${Math.round(g.x)},${Math.round(g.y)}) in ${g.viewportWidth}x${g.viewportHeight}` : "not found"})`);
  }
  return g;
}

async function currentTab(activeRun, allowFocusPause = false) {
  const tab = await chrome.tabs.get(activeRun.tabId);
  const window = await chrome.windows.get(tab.windowId);
  validateTarget(tab, window, false);
  if (allowFocusPause && activeRun.execute && !window.focused) return null;
  return validateTarget(tab, window, activeRun.execute);
}

async function loop(activeRun) {
  try {
    while (run === activeRun) {
      if (Date.now() - activeRun.started > 15 * 60 * 1000) {
        throw new Error("15-minute session limit reached");
      }
      status = "Checking the active game tab…";
      const tab = await bounded(currentTab(activeRun, true), "Active game tab");
      if (!tab) {
        activeRun.pausedAt ??= Date.now();
        if (Date.now() - activeRun.pausedAt >= 60000) {
          throw new Error("Game focus did not return within 60 seconds; stopped");
        }
        activeRun.focusResumed = true;
        status = "PAUSED: game window is unfocused; no input. Return to Chrome within 60 seconds.";
        await delay(650);
        continue;
      }
      activeRun.pausedAt = null;
      const g = await geometry(tab.id);
      const captured_at = Date.now() / 1000;
      status = "Capturing visible game pixels…";
      const screenshot = await bounded(
        chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" }),
        "Visible-tab capture"
      );
      if (run !== activeRun) return;
      await currentTab(activeRun);
      if (JSON.stringify(await geometry(tab.id)) !== JSON.stringify(g)) {
        throw new Error("Canvas moved during capture");
      }
      const frame = {
        schema: "urban-rivals/frame/v1",
        url: tab.url,
        mode: activeRun.mode,
        execute: activeRun.execute,
        advisor: activeRun.advisor,
        run_id: activeRun.id,
        sequence: ++activeRun.sequence,
        captured_at,
        png: screenshot.replace(/^data:image\/png;base64,/, ""),
        geometry: g,
        focus_resumed: activeRun.focusResumed === true,
      };
      activeRun.focusResumed = false;
      status = "Reading the captured board locally…";
      const response = await fetch(ENDPOINT + "/step", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + activeRun.token },
        body: JSON.stringify(frame),
        signal: AbortSignal.timeout(25000),
      });
      const result = await response.json();
      if (run !== activeRun) return;
      if (!response.ok || result.stop) {
        throw new Error(
          result.error ||
            (!activeRun.execute && !activeRun.advisor && result.stop
              ? "INSPECT complete: canvas captured locally; automatic play is OFF. No clicks."
              : result.status) ||
            "Bridge stopped"
        );
      }
      const prefix = activeRun.execute ? "AUTO: " : activeRun.advisor ? "ADVISOR: " : "INSPECT: ";
      status = prefix + (result.status || "Reading canvas");
      if (result.recommendation) {
        await updateHud(tab.id, result.recommendation);
      }
      const action = validateAction(result, frame);
      if (action) {
        if (!activeRun.execute) throw new Error("Non-execute mode received a click");
        await currentTab(activeRun);
        const now = await geometry(tab.id);
        if (JSON.stringify(now) !== JSON.stringify(g)) {
          throw new Error("Canvas moved during recognition");
        }
        if (run !== activeRun) return;
        const px = Math.round(g.x + action.x * g.width);
        const py = Math.round(g.y + action.y * g.height);
        try {
          await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => document.getElementById("unity-canvas")?.focus(),
          });
        } catch {}
        const point = { x: px, y: py, button: "left", clickCount: 1, pointerType: "mouse" };
        await chrome.debugger.sendCommand({ tabId: tab.id }, "Input.dispatchMouseEvent", { type: "mouseMoved", x: Math.max(0, px - 4), y: Math.max(0, py - 4), pointerType: "mouse" });
        await delay(30);
        await chrome.debugger.sendCommand({ tabId: tab.id }, "Input.dispatchMouseEvent", { type: "mouseMoved", x: px, y: py, pointerType: "mouse" });
        await delay(80);
        await chrome.debugger.sendCommand({ tabId: tab.id }, "Input.dispatchMouseEvent", { type: "mousePressed", ...point, buttons: 1 });
        await delay(80);
        await chrome.debugger.sendCommand({ tabId: tab.id }, "Input.dispatchMouseEvent", { type: "mouseReleased", ...point, buttons: 0 });
      }
      await delay(250);
    }
  } catch (error) {
    if (run === activeRun) await stop(error.message);
  }
}

chrome.debugger.onDetach.addListener((source) => {
  if (run?.execute && run.tabId === source.tabId) void stop("Browser debugging connection ended");
});

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message.type === "escape" && sender.tab?.id === run?.tabId) {
    void stop("Stopped with Escape");
    return;
  }
  if (message.type === "calibration_done" && calibrationToken) {
    const token = calibrationToken;
    calibrationToken = null;
    chrome.storage?.local?.set({ calibrationPoints: message.points }).catch(() => {});
    fetch(ENDPOINT + "/calibrate", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
      body: JSON.stringify({ points: message.points }),
    })
      .then(() => {
        status = "Calibration saved locally.";
      })
      .catch((err) => {
        status = "Calibration save failed: " + err.message;
      });
    return;
  }
  if (message.type === "calibration_error") {
    calibrationToken = null;
    status = message.error || "Calibration cancelled.";
    return;
  }
  if (sender.url !== chrome.runtime.getURL("popup.html")) return false;
  if (message.type === "status") {
    reply({ status });
    return false;
  }
  if (message.type === "stop") {
    stop().then(() => reply({ status }));
    return true;
  }
  if (message.type === "calibrate") {
    (async () => {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tab = tabs[0];
      if (!tab?.id || !allowedURL(tab.url)) throw new Error("Open the Urban Rivals WebGL game tab");
      calibrationToken = message.token;
      await injectOverlay(tab.id);
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => window.__urAgentOverlay?.startCalibration(),
      });
      status = "Calibration started on game tab.";
      reply({ status });
    })().catch((error) => {
      status = error.message;
      reply({ error: status });
    });
    return true;
  }
  if (message.type !== "start") return false;
  (async () => {
    if (run) throw new Error("Stop the current run before starting again");
    if (typeof message.token !== "string" || !message.token) throw new Error("Paste the local pairing token first");
    if (!/^[A-Za-z0-9_-]{32,128}$/.test(message.token)) {
      throw new Error("Invalid token characters. Copy only the contents of local/pairing-token.txt.");
    }
    if (typeof message.execute !== "boolean") throw new Error("Automatic-play selection is invalid; reopen the popup.");
    const mode = VALID_MODES.has(message.mode) ? message.mode : "training";
    const advisor = Boolean(message.advisor) && !message.execute;
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs[0];
    if (!tab?.id || !allowedURL(tab.url)) throw new Error("Open the Urban Rivals WebGL game tab");
    status = "Checking local pairing and server mode…";
    let ping;
    try {
      ping = await fetch(ENDPOINT + "/ready", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + message.token },
        body: JSON.stringify({ execute: message.execute, advisor, mode }),
        signal: AbortSignal.timeout(10000),
      });
    } catch {
      throw new Error("Local bridge is unavailable. Start Start-TrainingAgent.ps1; use -Execute for Auto-Play and -ReusePairingToken to keep this token.");
    }
    const ready = await ping.json();
    if (!ping.ok) throw new Error(ready.error || "Pairing failed");
    if (message.execute && !ready.execute_enabled) {
      throw new Error("Server is inspect-only. Start with -Execute for Auto-Play, or use Advisor mode.");
    }
    if (message.execute && ready.engine_revision !== "persistent-suite-v2") {
      throw new Error("Restart the local bridge: its engine is older than this extension.");
    }
    const activeRun = {
      id: crypto.randomUUID(),
      tabId: tab.id,
      token: message.token,
      mode,
      execute: message.execute,
      advisor,
      sequence: 0,
      started: Date.now(),
    };
    if (activeRun.execute) {
      try {
        await bounded(chrome.debugger.attach({ tabId: tab.id }, "1.3"), "Input connection");
      } catch (error) {
        throw new Error("Cannot attach game input. Close any browser debugger on the game tab, then Start again. " + error.message);
      }
    }
    try {
      await geometry(tab.id);
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          if (document.documentElement.dataset.urbanRivalsEscape) return;
          document.documentElement.dataset.urbanRivalsEscape = "1";
          document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") chrome.runtime.sendMessage({ type: "escape" }).catch(() => {});
          }, true);
        },
      });
    } catch (error) {
      if (activeRun.execute) await chrome.debugger.detach({ tabId: tab.id });
      throw error;
    }
    run = activeRun;
    status = advisor ? "Connected; Advisor HUD active" : "Connected; waiting for the first capture";
    reply({ status });
    void loop(activeRun);
  })().catch((error) => {
    status = error.message;
    reply({ error: status });
  });
  return true;
});
