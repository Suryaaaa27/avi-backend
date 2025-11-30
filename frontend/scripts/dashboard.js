(function () {
  const qs = (s) => document.querySelector(s);

  // -----------------------------
  // Helpers
  // -----------------------------

  function scoreToStars(raw) {
    let s = Number(raw || 0);
    if (s <= 1.01) s = s * 100;
    if (s < 20) return 1;
    if (s < 40) return 2;
    if (s < 60) return 3;
    if (s < 80) return 4;
    return 5;
  }

  function makeStars(stars) {
    const full = "★★★★★".slice(0, stars);
    const empty = "☆☆☆☆☆".slice(stars);
    return full + empty;
  }

  // -----------------------------
  // Feedback Formatter (NEW)
  // -----------------------------

  function formatFeedback(fb) {
    if (!fb || typeof fb !== "object") return "No feedback available.";

    const toArray = (x) =>
      Array.isArray(x) ? x : x ? [x] : [];

    const strengths = toArray(fb.strengths);
    const improvements = toArray(fb.improvements);
    const actionPlan = toArray(fb.action_plan);

    let out = "";

    if (fb.summary) {
      out += `📌 Summary:\n${fb.summary}\n\n`;
    }

    if (strengths.length) {
      out += `💪 Strengths:\n`;
      strengths.forEach((s) => (out += `• ${s}\n`));
      out += `\n`;
    }

    if (improvements.length) {
      out += `🔧 Improvements:\n`;
      improvements.forEach((s) => (out += `• ${s}\n`));
      out += `\n`;
    }

    if (actionPlan.length) {
      out += `📝 Action Plan:\n`;
      actionPlan.forEach((s) => (out += `• ${s}\n`));
      out += `\n`;
    }

    return out.trim();
  }

  // -----------------------------
  // Interpreters
  // -----------------------------

  function interpretNLP(nlpResult) {
    if (!nlpResult || typeof nlpResult !== "object") {
      return {
        icon: "🧠",
        stars: 2,
        color: "var(--yellow)",
        lines: ["No NLP evaluation available for this answer."],
      };
    }

    const sim = nlpResult.similarity_score ?? 0;
    const stars = scoreToStars(sim);
    const feedback = (nlpResult.feedback || "").trim();

    let extra;
    if (sim <= 5) {
      extra = "Your answer was too short. Speak at least 2–3 full sentences.";
    } else if (sim < 50) {
      extra = "You touched a few ideas, but expand with examples.";
    } else if (sim < 80) {
      extra = "Good attempt — refine clarity and detail.";
    } else {
      extra = "Strong answer with clear coverage of key points.";
    }

    return {
      icon: "🧠",
      stars,
      color:
        stars >= 4 ? "var(--green)" : stars >= 3 ? "var(--yellow)" : "var(--red)",
      lines: [feedback || "Your answer was analyzed for clarity and correctness.", extra],
    };
  }

  function interpretEmotion(res) {
    if (!res || res.success === false) {
      return {
        icon: "🙂",
        stars: 2,
        color: "var(--yellow)",
        lines: [
          "Emotion could not be detected reliably.",
          "Ensure your face is visible and well lit.",
        ],
      };
    }

    const dom = (res.dominant_emotion || "").toLowerCase();
    let icon = "🙂",
      stars = 4,
      color = "var(--green)",
      lines = [];

    if (dom.includes("hap")) {
      icon = "😊";
      lines.push("You appeared positive and engaged.");
    } else if (dom.includes("neu")) {
      icon = "😐";
      lines.push("You maintained a calm, neutral expression.");
    } else if (dom.includes("sad") || dom.includes("ang") || dom.includes("fear")) {
      icon = "😟";
      stars = 2;
      color = "var(--red)";
      lines.push("Your expression leaned negative. Try to look more positive.");
    } else {
      lines.push("Your emotional state appeared reasonably stable.");
    }

    lines.push("Tip: keep a friendly, open expression.");

    return { icon, stars, color, lines };
  }

  function interpretTone(res) {
    if (!res || res.success === false) {
      return {
        icon: "🔊",
        stars: 2,
        color: "var(--yellow)",
        lines: ["Tone could not be analyzed. Check your microphone input."],
      };
    }

    const energy = Number(res.energy || 0);
    const dom = (res.detected_emotion || "").toLowerCase();

    let stars = 4,
      color = "var(--green)",
      lines = [];

    if (energy < 0.03) {
      stars = 2;
      color = "var(--yellow)";
      lines.push("Your voice sounded very flat or low-energy.");
      lines.push("Add confidence and variation.");
    } else if (energy < 0.1) {
      stars = 3;
      color = "var(--yellow)";
      lines.push("Your tone was reasonably balanced.");
    } else {
      lines.push("Good energy — engaging and clear.");
    }

    if (dom.includes("sad") || dom.includes("ang") || dom.includes("fear")) {
      stars = Math.min(stars, 2);
      color = "var(--red)";
      lines.push("Tone sounded tense at times. Aim for confident delivery.");
    }

    return { icon: "🔊", stars, color, lines };
  }

  function interpretPosture(res) {
    if (!res || res.success === false) {
      return {
        icon: "🪑",
        stars: 2,
        color: "var(--yellow)",
        lines: [
          "Posture couldn’t be analyzed.",
          "Sit upright, stay centered, look at the camera.",
        ],
      };
    }

    const summary = (res.summary || "").toLowerCase();
    let stars = 4,
      color = "var(--green)",
      lines = [];

    if (summary.includes("excellent")) {
      lines.push("Your posture looked very professional.");
    } else if (summary.includes("good")) {
      lines.push("Your posture was generally good.");
    } else if (summary.includes("poor") || summary.includes("bad")) {
      stars = 2;
      color = "var(--red)";
      lines.push("Avoid slouching or drifting out of frame.");
    } else {
      stars = 3;
      color = "var(--yellow)";
      lines.push("Posture was okay — try to stay more engaged.");
    }

    lines.push("Tip: keep shoulders relaxed and sit upright.");

    return { icon: "🪑", stars, color, lines };
  }

  // Render card
  function renderPanel(el, interpreted) {
    const stars = makeStars(interpreted.stars);
    el.innerHTML = `
      <div class="mini-panel-header">
        <span class="panel-icon">${interpreted.icon}</span>
        <span class="panel-stars" style="color:${interpreted.color};">${stars}</span>
      </div>
      <ul class="panel-lines">
        ${interpreted.lines.map((l) => `<li>${l}</li>`).join("")}
      </ul>
    `;
  }

  // -----------------------------
  // Load Final Report
  // -----------------------------

  async function loadFinal() {
    const params = new URLSearchParams(location.search);
    let email = params.get("email");
    let interview_id = params.get("interview_id");

    const LS = JSON.parse(localStorage.getItem("avi_last_result") || "null");
    if (!email && LS) email = LS.email;
    if (!interview_id && LS) interview_id = LS.interview_id;

    if (!email || !interview_id) {
      qs("#feedbackText").textContent = "No result found.";
      return;
    }

    const URL = `http://localhost:5000/final_feedback?email=${encodeURIComponent(
      email
    )}&interview_id=${encodeURIComponent(interview_id)}`;

    let data;
    try {
      data = await fetch(URL).then((r) => r.json());
    } catch (e) {
      qs("#feedbackText").textContent = "Failed fetching feedback.";
      return;
    }

    if (!data.success) {
      qs("#feedbackText").textContent = data.error || "No data.";
      return;
    }

    // Final score
    const raw = data.final_score || 0;
    const percent = raw <= 1 ? Math.round(raw * 100) : raw;
    const stars = scoreToStars(percent);
    qs("#finalScore").innerHTML = `
      <div class="score-main">${percent}</div>
      <div class="score-stars">${makeStars(stars)}</div>
    `;

    // Rating pill
    const rating = (data.qualitative_rating || "—").toLowerCase();
    const pill = qs("#qualRating");
    pill.textContent = rating[0].toUpperCase() + rating.slice(1);
    pill.className = `pill rating-${rating}`;

    // Meta
    qs("#meta").textContent = `Email: ${email} • Interview: ${interview_id}`;

    // Panels
    renderPanel(qs("#nlpBox"), interpretNLP(data.nlp_result));
    renderPanel(qs("#toneBox"), interpretTone(data.tone_result));
    renderPanel(qs("#emotionBox"), interpretEmotion(data.emotion_result));
    renderPanel(qs("#postureBox"), interpretPosture(data.posture_result));

    // Main feedback
    qs("#feedbackText").textContent = formatFeedback(data.feedback);

    qs("#btnNew").onclick = () => {
      localStorage.removeItem("avi_last_result");
      location.href = "./interview.html";
    };
  }

  window.addEventListener("DOMContentLoaded", loadFinal);
})();
