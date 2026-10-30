(function () {
  const md = navigator.mediaDevices;
  if (!md || !md.getUserMedia || md.__focusPatched) return;
  md.__focusPatched = true;

  const ZOOM = 1.0;    // 1.0 = ไม่ซูม ถ้าอยากถือห่างขึ้นให้ลอง 1.3 - 1.5
  const DEBUG = false; // true = แสดงแจ้งเตือนข้อมูลกล้อง (ใช้ตอนทดสอบเครื่องใหม่)
  const original = md.getUserMedia.bind(md);
  let currentTrack = null;

  // กล้องตัวนี้รองรับโฟกัสอัตโนมัติต่อเนื่องหรือไม่
  function hasContinuous(track) {
    try {
      const c = track.getCapabilities();
      return !!(c.focusMode && c.focusMode.includes("continuous"));
    } catch (e) {
      return false;
    }
  }

  // เบราว์เซอร์รายงานข้อมูลโหมดโฟกัสมาหรือไม่ (Firefox/Safari มักไม่รายงาน)
  function exposesFocus(track) {
    try {
      return !!track.getCapabilities().focusMode;
    } catch (e) {
      return false;
    }
  }

  function buildConstraints(constraints, deviceId) {
    const v = constraints.video === true ? {} : Object.assign({}, constraints.video);
    v.width = v.width || { ideal: 1920 };
    v.height = v.height || { ideal: 1080 };
    if (deviceId) {
      delete v.facingMode;
      v.deviceId = { exact: deviceId };
    }
    return Object.assign({}, constraints, { video: v });
  }

  // ลองกล้องหลังทีละตัว จนเจอตัวที่โฟกัสอัตโนมัติได้
  async function findAutofocusCamera(constraints) {
    const devices = (await md.enumerateDevices()).filter(function (d) {
      return d.kind === "videoinput" && /back|environment/i.test(d.label);
    });
    for (const d of devices) {
      try {
        const s = await original(buildConstraints(constraints, d.deviceId));
        if (hasContinuous(s.getVideoTracks()[0])) return s;
        s.getTracks().forEach(function (t) { t.stop(); });
      } catch (e) {}
    }
    return null;
  }

  md.getUserMedia = async function (constraints) {
    if (!constraints || !constraints.video) return original(constraints);

    let stream = await original(buildConstraints(constraints));
    let track = stream.getVideoTracks()[0];
    let switched = false;

    // สลับกล้องเฉพาะเมื่อเบราว์เซอร์บอกข้อมูลโฟกัส และกล้องตัวนี้ไม่มี continuous
    if (exposesFocus(track) && !hasContinuous(track)) {
      stream.getTracks().forEach(function (t) { t.stop(); });
      const better = await findAutofocusCamera(constraints);
      if (better) {
        stream = better;
        switched = true;
      } else {
        stream = await original(buildConstraints(constraints)); // ไม่เจอตัวที่ดีกว่า ใช้ตัวเดิม
      }
      track = stream.getVideoTracks()[0];
    }

    currentTrack = track;
    const caps = track.getCapabilities ? track.getCapabilities() : {};
    const advanced = {};
    if (caps.focusMode && caps.focusMode.includes("continuous")) {
      advanced.focusMode = "continuous";
    }
    if (caps.zoom && ZOOM > 1) {
      advanced.zoom = Math.min(caps.zoom.max, Math.max(caps.zoom.min, ZOOM));
    }
    if (Object.keys(advanced).length) {
      try { await track.applyConstraints({ advanced: [advanced] }); } catch (e) {}
    }

    if (DEBUG && window.frappe && frappe.show_alert) {
      const s = track.getSettings();
      frappe.show_alert({
        message: (switched ? "[สลับกล้องแล้ว] " : "") +
          "cam: " + track.label + " | " + s.width + "x" + s.height +
          " | focus: " + JSON.stringify(caps.focusMode),
        indicator: switched ? "green" : "orange",
      }, 15);
    }
    return stream;
  };

  // แตะที่ภาพกล้องเพื่อโฟกัสใหม่ (ถ้ารองรับ single-shot)
  document.addEventListener("click", async function (e) {
    if (!currentTrack || e.target.tagName !== "VIDEO") return;
    const caps = currentTrack.getCapabilities();
    if (!caps.focusMode || !caps.focusMode.includes("single-shot")) return;
    try {
      await currentTrack.applyConstraints({ advanced: [{ focusMode: "single-shot" }] });
      setTimeout(function () {
        if (caps.focusMode.includes("continuous")) {
          currentTrack.applyConstraints({ advanced: [{ focusMode: "continuous" }] }).catch(function () {});
        }
      }, 1000);
    } catch (err) {}
  });
})();