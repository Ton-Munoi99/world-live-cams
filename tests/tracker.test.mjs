// เทสต์ตรรกะติดตาม+นับข้ามเส้น — รัน: node tests/tracker.test.mjs
import assert from "node:assert";
import { createTracker } from "../public/tracker.js";

const W = 1000, H = 1000, LINE = 0.5;          // เส้นที่ y = 500
const person = (x, footY) => ({ bbox: [x - 20, footY - 100, 40, 100] });

// เดินจาก footY a ไป b เป็น n ก้าว (จำลองคนเดินจริงที่ขยับทีละน้อย)
function walk(from, to, n = 8, x = 500) {
  const out = [];
  for (let i = 0; i <= n; i++) out.push([person(x, from + (to - from) * i / n)]);
  return out;
}

function run(frames) {
  const t = createTracker();
  for (const f of frames) t.update(f, W, H, LINE);
  return t;
}

// เดินขึ้นข้ามเส้น = เข้า 1
let t = run(walk(650, 350));
assert.equal(t.in, 1, "เดินขึ้นควรนับเข้า 1 ได้ " + t.in);
assert.equal(t.out, 0);

// เดินลงข้ามเส้น = ออก 1
t = run(walk(350, 650));
assert.equal(t.out, 1, "เดินลงควรนับออก 1 ได้ " + t.out);
assert.equal(t.in, 0);

// เดินอยู่ใต้เส้นตลอด ไม่นับ
t = run(walk(800, 600));
assert.equal(t.in + t.out, 0, "ไม่ข้ามเส้นต้องไม่นับ");

// สองคนเดินขึ้นพร้อมกัน = เข้า 2 และต้องแยกเป็น 2 id
t = run(walk(650, 350, 8, 250).map((f, i) => [...f, person(750, 650 + (350 - 650) * i / 8)]));
assert.equal(t.in, 2, "สองคนขึ้นควรนับ 2 ได้ " + t.in);
assert.equal(t.idsUsed, 2, "ควรสร้าง 2 id ได้ " + t.idsUsed);

// ขึ้นแล้วเดินกลับลง = เข้า 1 ออก 1
t = run([...walk(650, 350), ...walk(350, 650)]);
assert.equal(t.in, 1, "in ควร 1 ได้ " + t.in);
assert.equal(t.out, 1, "out ควร 1 ได้ " + t.out);

// เฟรมไม่มีคน ต้องไม่พังและไม่นับ
t = run([[], [], []]);
assert.equal(t.in + t.out, 0);
assert.equal(t.tracks.length, 0);

// คนหายไปหลายเฟรมแล้วกลับมา ต้องถูกลบทิ้งไม่ค้าง
t = createTracker();
t.update([person(500, 600)], W, H, LINE);
for (let i = 0; i < 20; i++) t.update([], W, H, LINE);
assert.equal(t.tracks.length, 0, "คนหายนานต้องถูกลบ");

// ยืนนิ่งคร่อมเส้นพอดี ต้องไม่นับซ้ำรัวๆ
t = createTracker();
for (let i = 0; i < 30; i++) t.update([person(500, 500)], W, H, LINE);
assert.ok(t.in + t.out <= 1, "ยืนนิ่งต้องไม่นับซ้ำ ได้ " + (t.in + t.out));

// reset ล้างค่าจริง
t.reset();
assert.equal(t.in, 0);
assert.equal(t.tracks.length, 0);

console.log("[tracker.test OK] ผ่านทั้ง 8 กลุ่มเคส");
