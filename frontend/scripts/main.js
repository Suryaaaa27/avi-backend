// ====================================
// main.js — AVI Frontend (Patched)
// ====================================

// ---- Config ----
const API_BASE = "http://localhost:5000";

// ---- Helpers ----
const qs = (s) => document.querySelector(s);
const $on = (el, ev, cb) => el && el.addEventListener(ev, cb);

function fadeInPage() {
  document.body.classList.add("page-fade");
}

/* THEME */
function applyTheme(theme) {
  const btn = qs("#toggleTheme");
  const t = theme === "light" ? "light" : "dark";

  if (t === "light") {
    document.body.classList.add("light");
    document.body.classList.remove("dark");
    if (btn) btn.textContent = "Light";
  } else {
    document.body.classList.add("dark");
    document.body.classList.remove("light");
    if (btn) btn.textContent = "Dark";
  }
  try {
    localStorage.setItem("avi_theme", t);
  } catch (e) {}
}

function initThemeToggle() {
  const btn = qs("#toggleTheme");
  const saved =
    (typeof localStorage !== "undefined"
      ? localStorage.getItem("avi_theme")
      : null) || "dark";

  applyTheme(saved);

  if (!btn) return;
  btn.addEventListener("click", () => {
    const current = document.body.classList.contains("light")
      ? "light"
      : "dark";
    const next = current === "light" ? "dark" : "light";
    applyTheme(next);
  });
}

async function postJSON(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function postFile(path, field, blob, filename) {
  const fd = new FormData();
  fd.append(field, blob, filename);
  const res = await fetch(API_BASE + path, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function saveToSession(finalPayload) {
  localStorage.setItem("avi_last_result", JSON.stringify(finalPayload));
  window.location.href = "./dashboard.html";
}

window.AVI = {
  initCommon() {
    fadeInPage();
    initThemeToggle();
  },

  // ====================================
  // INTERVIEW PAGE
  // ====================================
  initInterviewPage() {
    this.initCommon();

    console.log("✅ Interview page initialized");

    // Prevent double binding
    if (window.__AVI_INTERVIEW_INIT__) {
      console.warn("⚠ Prevented second initialization");
      return;
    }
    window.__AVI_INTERVIEW_INIT__ = true;

    // -------------------
    // UI Elements
    // -------------------
    const email = qs("#email");
    const interviewId = qs("#interviewId");
    const domain = qs("#domain");
    const typedAnswer = qs("#typedAnswer");

    const panel = qs("#panel");
    const recStatus = qs("#recStatus");
    const audioLevel = qs("#audioLevel");
    const timerEl = qs("#timer");
    const camPreview = qs("#camPreview");
    const videoCanvas = qs("#videoCanvas");
    const questionBox = qs("#questionBox");
    const answerText = qs("#answerText");
    const status = qs("#status");

    const btnGo = qs("#btnGo");
    const btnStartRec = qs("#btnStartRec");
    const btnStopRec = qs("#btnStopRec");
    const btnSnap = qs("#btnSnap");
    const btnAnalyze = qs("#btnAnalyze");

    // -------------------
    // State
    // -------------------
    let audioRec,
      videoRec,
      recordedAudio = null,
      recordedVideo = null,
      snapshotBlob = null;
    let tInt = null,
      seconds = 0;

    let currentQuestion = null;
    let interviewResults = [];

    // -------------------
    // Timer
    // -------------------
    function startTimer() {
      seconds = 0;
      timerEl.textContent = "00:00";
      tInt = setInterval(() => {
        seconds++;
        let m = String(Math.floor(seconds / 60)).padStart(2, "0");
        let s = String(seconds % 60).padStart(2, "0");
        timerEl.textContent = `${m}:${s}`;
      }, 1000);
    }
    function stopTimer() {
      clearInterval(tInt);
    }

    // -------------------
    // Fetch Question
    // -------------------
    async function loadQuestion() {
      const url = `${API_BASE}/question?email=${encodeURIComponent(
        email.value
      )}&interview_id=${encodeURIComponent(
        interviewId.value
      )}&domain=${encodeURIComponent(domain.value)}`;

      const res = await fetch(url);
      const q = await res.json();

      if (q.done) {
        saveToSession({
          success: true,
          email: email.value,
          interview_id: interviewId.value,
          domain: domain.value,
          results: interviewResults,
        });
        return;
      }

      currentQuestion = {
        id: q.id,
        text: q.text,
        index: q.index,
      };

      questionBox.textContent = q.text;
      answerText.value = typedAnswer.value || "";

      recordedAudio = null;
      recordedVideo = null;
      snapshotBlob = null;

      recStatus.textContent = "Idle";
      recStatus.style.color = "#9bb1ff";
      timerEl.textContent = "00:00";
      btnAnalyze.disabled = true;
      btnStartRec.disabled = false;
      btnStopRec.disabled = true;
    }

    // -------------------
    // ENTER INTERVIEW
    // -------------------
    $on(btnGo, "click", async () => {
      if (!email.value || !interviewId.value || !domain.value) {
        alert("Fill email, interviewID, domain");
        return;
      }

      // Reset progress
      try {
        await postJSON("/progress/reset", {
          email: email.value,
          interview_id: interviewId.value,
          domain: domain.value,
        });
      } catch (e) {
        console.warn("reset failed", e);
      }

      panel.classList.remove("hidden");

      try {
        videoRec = new AVIRecorders.VideoRecorder(camPreview);
        await videoRec.start();

        audioRec = new AVIRecorders.AudioRecorder((lvl) => {
          const v = Math.max(0.02, Number(lvl) || 0);
          const width = Math.max(8, v * 100);
          if (audioLevel) audioLevel.style.width = `${width}%`;
        });
      } catch (e) {
        console.warn("Camera/mic init error", e);
      }

      await loadQuestion();
    });

    // -------------------
    // RECORD CONTROLS
    // -------------------
    $on(btnStartRec, "click", async () => {
      await audioRec.start();
      recStatus.textContent = "Recording...";
      recStatus.style.color = "#33d69f";
      btnStartRec.disabled = true;
      btnStopRec.disabled = false;
      startTimer();
    });

    $on(btnStopRec, "click", async () => {
      btnStopRec.disabled = true;
      recordedAudio = await audioRec.stop();

      recordedVideo = await videoRec.getBufferedVideo();

      recStatus.textContent = "Stopped";
      recStatus.style.color = "#9bb1ff";
      stopTimer();
      btnAnalyze.disabled = false;
    });

    $on(btnSnap, "click", async () => {
      snapshotBlob = await videoRec.takeSnapshot(videoCanvas);
      videoCanvas.classList.remove("hidden");
      setTimeout(() => videoCanvas.classList.add("hidden"), 700);
    });

    // -------------------
    // ANALYZE HANDLER (SINGLE BIND)
    // -------------------
    if (!btnAnalyze._bound) {
      btnAnalyze._bound = true;

      btnAnalyze.addEventListener("click", async () => {
        btnAnalyze.disabled = true;
        status.textContent = "Analyzing...";

        try {
          // -------------------
          // 1) TRANSCRIPTION
          // -------------------
          let transcribed = { text: answerText.value };
          if (recordedAudio) {
            const t = await postFile("/transcribe", "audio", recordedAudio, "ans.webm");
            if (t?.text) transcribed.text = t.text;
          }

          // -------------------
          // 2) TONE
          // -------------------
          let tone_result = {};
          if (recordedAudio) {
            tone_result = await postFile(
              "/analyze-tone",
              "audio",
              recordedAudio,
              "voice.webm"
            );
          }

          // -------------------
          // 3) EMOTION
          // -------------------
          if (!snapshotBlob) {
            snapshotBlob = await videoRec.takeSnapshot(videoCanvas);
          }
          let emotion_result = {};
          if (snapshotBlob) {
            emotion_result = await postFile(
              "/detect-emotion",
              "image",
              snapshotBlob,
              "face.jpg"
            );
          }

          // -------------------
          // 4) POSTURE
          // -------------------
          let posture_result = {};
          if (recordedVideo) {
            posture_result = await postFile(
              "/analyze-posture",
              "video",
              recordedVideo,
              "posture.webm"
            );
          }

          // -------------------
          // 5) NLP
          // -------------------
          let nlp_result = {};
          const body = {
            domain: domain.value,
            user_response: transcribed.text,
            question_id: currentQuestion.id,
            question_text: currentQuestion.text,
          };

          await new Promise((res) => setTimeout(res, 1000)); // avoid rate limit
          const nres = await postJSON("/evaluate_domain", body);
          nlp_result = nres?.evaluation || nres || {};

          // -------------------
          // 6) FINAL FEEDBACK
          // -------------------
          const payload = {
            email: email.value,
            interview_id: interviewId.value,
            domain: domain.value,
            nlp_result,
            emotion_result,
            posture_result,
            tone_result,
            question_meta: currentQuestion,
          };

          const final = await postJSON("/generate-feedback", payload);

          interviewResults.push({
            question: currentQuestion,
            nlp_result,
            emotion_result,
            posture_result,
            tone_result,
            final,
          });

          // -------------------
          // 7) NEXT QUESTION
          // -------------------
          await loadQuestion();
        } catch (err) {
          console.error("❌ ANALYSIS FAILED:", err);
          alert("Analysis failed — check backend logs.");
        } finally {
          status.textContent = "";
          btnAnalyze.disabled = true;
          btnStartRec.disabled = false;
          btnStopRec.disabled = true;
        }
      });
    }
  },
};

// ====================================
// GLOBAL INIT (Prevent double)
// ====================================
window.addEventListener("DOMContentLoaded", () => {
  if (window.__AVI_INIT_GLOBAL__) {
    console.warn("⚠ Prevented duplicate global init");
    return;
  }
  window.__AVI_INIT_GLOBAL__ = true;

  const path = window.location.pathname.toLowerCase();

  if (path.includes("interview") && path.endsWith(".html")) {
    window.AVI.initInterviewPage();
  } else {
    window.AVI.initCommon();
  }
});
