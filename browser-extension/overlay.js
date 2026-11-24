(() => {
  if (window.__urAgentOverlay) return;

  const HUD_ID = "ur-agent-advisor-hud";
  const CAL_ID = "ur-agent-calibration-overlay";
  const STEPS = [
    ["hand_0", "Click the center of Your Hand Card 1 (leftmost)"],
    ["hand_1", "Click the center of Your Hand Card 2"],
    ["hand_2", "Click the center of Your Hand Card 3"],
    ["hand_3", "Click the center of Your Hand Card 4 (rightmost)"],
    ["opp_0", "Click the center of Opponent Card 1 (leftmost)"],
    ["opp_1", "Click the center of Opponent Card 2"],
    ["opp_2", "Click the center of Opponent Card 3"],
    ["opp_3", "Click the center of Opponent Card 4 (rightmost)"],
    ["pillz_plus", "Click the Pillz (+) button (press Space to click a card first if hidden)"],
    ["pillz_minus", "Click the Pillz (-) button"],
    ["fury_btn", "Click the Fury button"],
    ["confirm_btn", "Click the Confirm / Fight button"],
  ];

  function getCanvasRect() {
    const canvas = document.getElementById("unity-canvas");
    if (!canvas) return null;
    return canvas.getBoundingClientRect();
  }

  function showRecommendation(rec) {
    if (!rec) return;
    let hud = document.getElementById(HUD_ID);
    if (!hud) {
      hud = document.createElement("div");
      hud.id = HUD_ID;
      Object.assign(hud.style, {
        position: "fixed",
        bottom: "12px",
        left: "12px",
        zIndex: "2147483646",
        pointerEvents: "none",
        background: "rgba(18, 22, 32, 0.90)",
        color: "#edf0f6",
        border: "1px solid rgba(79, 140, 255, 0.7)",
        borderRadius: "10px",
        padding: "10px 14px",
        fontFamily: "system-ui, -apple-system, sans-serif",
        fontSize: "13px",
        lineHeight: "1.45",
        boxShadow: "0 6px 20px rgba(0,0,0,0.45)",
        minWidth: "230px",
      });
      document.body.appendChild(hud);
    }
    const winPct = Math.round((rec.win_prob ?? 0.5) * 100);
    const furyText = rec.fury ? "ON" : "OFF";
    hud.innerHTML = `
      <div style="font-weight:700;color:#8ab4f8;margin-bottom:4px;">
        UR Agent · ${(rec.mode || "training").toUpperCase()}
      </div>
      <div><strong>Card:</strong> ${rec.card_name} (${rec.stars}★ · ${rec.power}/${rec.damage})</div>
      <div><strong>Pillz:</strong> ${rec.pillz} &nbsp;|&nbsp; <strong>Fury:</strong> ${furyText}</div>
      <div style="color:#a7f3d0;margin-top:2px;"><strong>Est. Win:</strong> ${winPct}%</div>
    `;
  }

  function hideRecommendation() {
    document.getElementById(HUD_ID)?.remove();
  }

  function startCalibration() {
    document.getElementById(CAL_ID)?.remove();
    const rect = getCanvasRect();
    if (!rect || rect.width < 320) {
      chrome.runtime.sendMessage({
        type: "calibration_error",
        error: "Could not find #unity-canvas on this page.",
      });
      return;
    }

    let stepIndex = 0;
    let interactMode = false;
    const points = {};

    const overlay = document.createElement("div");
    overlay.id = CAL_ID;
    Object.assign(overlay.style, {
      position: "fixed",
      left: `${rect.left}px`,
      top: `${rect.top}px`,
      width: `${rect.width}px`,
      height: `${rect.height}px`,
      zIndex: "2147483647",
      background: "rgba(10, 14, 24, 0.35)",
      cursor: "crosshair",
      display: "flex",
      alignItems: "flex-start",
      justifyContent: "center",
      paddingTop: "14px",
      boxSizing: "border-box",
      border: "2px dashed #60a5fa",
      pointerEvents: "auto",
    });

    const banner = document.createElement("div");
    Object.assign(banner.style, {
      background: "rgba(15, 20, 30, 0.95)",
      color: "#f8fafc",
      padding: "10px 14px",
      borderRadius: "8px",
      fontFamily: "system-ui, sans-serif",
      fontSize: "13.5px",
      border: "1px solid #60a5fa",
      pointerEvents: "auto",
      display: "flex",
      alignItems: "center",
      gap: "10px",
    });

    const textSpan = document.createElement("span");
    const toggleBtn = document.createElement("button");
    Object.assign(toggleBtn.style, {
      padding: "5px 10px",
      borderRadius: "5px",
      border: "0",
      background: "#2563eb",
      color: "#fff",
      fontWeight: "600",
      cursor: "pointer",
      fontSize: "12px",
    });
    banner.appendChild(textSpan);
    banner.appendChild(toggleBtn);
    overlay.appendChild(banner);

    const updateBanner = () => {
      const [, label] = STEPS[stepIndex];
      if (interactMode) {
        overlay.style.pointerEvents = "none";
        overlay.style.background = "transparent";
        overlay.style.borderColor = "#34d399";
        textSpan.textContent = `Interact mode: click the game to reveal UI, then press Space to record Step ${stepIndex + 1}/${STEPS.length}`;
        toggleBtn.textContent = "Resume Recording (Space)";
        toggleBtn.style.background = "#059669";
      } else {
        overlay.style.pointerEvents = "auto";
        overlay.style.background = "rgba(10, 14, 24, 0.35)";
        overlay.style.borderColor = "#60a5fa";
        textSpan.textContent = `Step ${stepIndex + 1}/${STEPS.length}: ${label} (Esc to cancel)`;
        toggleBtn.textContent = "Click Game Instead (Space)";
        toggleBtn.style.background = "#2563eb";
      }
    };
    updateBanner();

    toggleBtn.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      interactMode = !interactMode;
      updateBanner();
    });

    const cleanup = () => {
      document.removeEventListener("keydown", onKey, true);
      overlay.remove();
    };

    const onKey = (ev) => {
      if (ev.key === "Escape") {
        cleanup();
        chrome.runtime.sendMessage({ type: "calibration_error", error: "Calibration cancelled." });
      } else if (ev.code === "Space" || ev.key === " ") {
        ev.preventDefault();
        ev.stopPropagation();
        interactMode = !interactMode;
        updateBanner();
      }
    };
    document.addEventListener("keydown", onKey, true);

    overlay.addEventListener("click", (ev) => {
      if (interactMode) return;
      if (banner.contains(ev.target)) return;
      ev.preventDefault();
      ev.stopPropagation();
      const r = getCanvasRect() || rect;
      const nx = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width));
      const ny = Math.max(0, Math.min(1, (ev.clientY - r.top) / r.height));
      const [key] = STEPS[stepIndex];
      points[key] = { x: Number(nx.toFixed(4)), y: Number(ny.toFixed(4)) };
      stepIndex += 1;
      if (stepIndex >= STEPS.length) {
        cleanup();
        chrome.runtime.sendMessage({ type: "calibration_done", points });
      } else {
        updateBanner();
      }
    });

    document.body.appendChild(overlay);
  }

  window.__urAgentOverlay = {
    showRecommendation,
    hideRecommendation,
    startCalibration,
  };
})();
