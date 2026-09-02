/**
 * ตัวติดตามคนแบบ centroid + นับข้ามเส้น
 *
 * ponytail: coco-ssd ให้แค่กล่อง ไม่มี id — เขียนตัวจับคู่สั้นๆ พอสำหรับนับข้ามเส้น
 * ไม่ต้องลงไลบรารี tracking เต็มตัว
 *
 * ทำนายตำแหน่งถัดไปจากความเร็ว ทำให้ตามคนที่เดินเร็ว (หรือเฟรมเรตต่ำ) ได้ดีขึ้น
 * ตรวจตรรกะ: node tests/tracker.test.mjs
 */

const DIST = 0.18;    // ระยะจับคู่สูงสุด (สัดส่วนความกว้างภาพ)
const MAX_MISS = 12;  // หายกี่เฟรมถึงลบทิ้ง

export function createTracker() {
  let tracks = [];
  let nextId = 1;
  let inCount = 0;
  let outCount = 0;

  function update(dets, W, H, lineFrac) {
    const thr = DIST * W;

    for (const t of tracks) {
      t.seen = false;
      t.px = t.cx + t.vx;   // ตำแหน่งที่คาดว่าจะไปอยู่เฟรมนี้
      t.py = t.cy + t.vy;
    }

    for (const d of dets) {
      const cx = d.bbox[0] + d.bbox[2] / 2;
      const cy = d.bbox[1] + d.bbox[3];   // จุดเท้า — ยึดพื้นได้นิ่งกว่ากลางกล่อง
      let best = null, bd = thr;
      for (const t of tracks) {
        if (t.seen) continue;
        const gap = Math.hypot(t.px - cx, t.py - cy);
        if (gap < bd) { bd = gap; best = t; }
      }
      if (best) {
        best.vx = cx - best.cx;
        best.vy = cy - best.cy;
        best.prevY = best.cy;
        best.cx = cx; best.cy = cy;
        best.miss = 0; best.seen = true; best.box = d.bbox;
      } else {
        tracks.push({ id: nextId++, cx, cy, prevY: cy, vx: 0, vy: 0, miss: 0, seen: true, box: d.bbox });
      }
    }

    const lineY = lineFrac * H;
    for (const t of tracks) {
      if (!t.seen) { t.miss++; continue; }
      if (t.prevY > lineY && t.cy <= lineY) inCount++;        // ข้ามขึ้น = เข้า
      else if (t.prevY < lineY && t.cy >= lineY) outCount++;  // ข้ามลง = ออก
    }
    tracks = tracks.filter(t => t.miss < MAX_MISS);
  }

  return {
    update,
    get in() { return inCount; },
    get out() { return outCount; },
    get tracks() { return tracks; },
    get idsUsed() { return nextId - 1; },
    reset() { tracks = []; nextId = 1; inCount = 0; outCount = 0; },
  };
}
