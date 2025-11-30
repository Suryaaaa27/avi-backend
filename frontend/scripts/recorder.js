class AudioRecorder {
  constructor(levelCallback) {
    this.mediaStream = null;
    this.mediaRecorder = null;
    this.chunks = [];
    this.levelCallback = levelCallback;
    this.audioCtx = null;
    this.analyser = null;
    this.raf = null;
  }

  async start() {
    this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.mediaRecorder = new MediaRecorder(this.mediaStream, { mimeType: "audio/webm" });
    this.chunks = [];

    this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = this.audioCtx.createMediaStreamSource(this.mediaStream);
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 256;
    source.connect(this.analyser);

    const loop = () => {
      const data = new Uint8Array(this.analyser.frequencyBinCount);
      this.analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        const v = (data[i] - 128) / 128;
        sum += Math.abs(v);
      }
      const level = Math.min(1, (sum / data.length) * 4);
      if (this.levelCallback) this.levelCallback(level);
      this.raf = requestAnimationFrame(loop);
    };
    loop();

    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };
    this.mediaRecorder.start();
  }

  async stop() {
    if (!this.mediaRecorder) return null;
    return new Promise((resolve) => {
      this.mediaRecorder.onstop = () => {
        cancelAnimationFrame(this.raf);
        this.audioCtx && this.audioCtx.close();
        const blob = new Blob(this.chunks, { type: "audio/webm" });
        this.cleanup();
        resolve(blob);
      };
      this.mediaRecorder.stop();
    });
  }

  cleanup() {
    this.mediaStream && this.mediaStream.getTracks().forEach((t) => t.stop());
    this.mediaStream = null;
    this.mediaRecorder = null;
    this.chunks = [];
  }
}

/* ===========================================
          FIXED VIDEO RECORDER
   ===========================================*/

class VideoRecorder {
  constructor(videoEl) {
    this.videoEl = videoEl;
    this.mediaStream = null;
    this.recorder = null;

    // NEW: buffers to hold continuous recording
    this.buffers = [];
  }

  async start() {
    // Start camera once and never shut it down
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: false,
    });

    this.videoEl.srcObject = this.mediaStream;

    // Start continuous recording for posture chunks
    this.recorder = new MediaRecorder(this.mediaStream, {
      mimeType: "video/webm",
    });

    this.buffers = [];

    this.recorder.ondataavailable = (e) => {
      if (e.data.size) this.buffers.push(e.data);
    };

    this.recorder.start(300); // collect chunks every 300ms
  }

  // Get latest buffered video segment
  async getBufferedVideo() {
    if (!this.buffers.length) return null;
    const copy = [...this.buffers]; // clone
    this.buffers = []; // reset for the next question
    return new Blob(copy, { type: "video/webm" });
  }

  // ❌ DO NOT STOP CAMERA — keep for entire interview
  async stop() {
    return null;
  }

  takeSnapshot(canvas) {
    if (!this.videoEl.srcObject) return null;

    const trackSettings = this.videoEl.srcObject.getVideoTracks()[0].getSettings() || {};
    const w = trackSettings.width || this.videoEl.videoWidth || 640;
    const h = trackSettings.height || this.videoEl.videoHeight || 360;

    canvas.width = w;
    canvas.height = h;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(this.videoEl, 0, 0, w, h);

    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
  }

  // Only call at END of entire interview
  cleanup() {
    this.mediaStream && this.mediaStream.getTracks().forEach((t) => t.stop());
    this.videoEl.srcObject = null;
    this.mediaStream = null;
    this.recorder = null;
    this.buffers = [];
  }
}

window.AVIRecorders = { AudioRecorder, VideoRecorder };
