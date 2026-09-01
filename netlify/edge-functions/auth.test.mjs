// เทสต์ตรรกะรหัสผ่าน — รัน: node netlify/edge-functions/auth.test.mjs
import assert from "node:assert";
import { isAllowed, parseBasic } from "./auth.js";

const b64 = (s) => Buffer.from(s, "utf8").toString("base64");
const hdr = (u, p) => "Basic " + b64(`${u}:${p}`);

// แกะ header ถูกต้อง
assert.deepEqual(parseBasic(hdr("bob", "s3cret")), { user: "bob", pass: "s3cret" });
assert.equal(parseBasic("Bearer xyz"), null, "ต้องรับเฉพาะ Basic");
assert.equal(parseBasic("Basic !!!ไม่ใช่base64"), null, "base64 พังต้องไม่ throw");
assert.equal(parseBasic(null), null);
// รหัสที่มี ":" ต้องไม่ถูกตัด
assert.deepEqual(parseBasic(hdr("a", "pa:ss:word")), { user: "a", pass: "pa:ss:word" });

// ไม่ตั้ง SITE_USER = ใส่ชื่ออะไรก็ผ่าน ขอแค่รหัสถูก
assert.equal(isAllowed(hdr("ใครก็ได้", "hunter2"), "", "hunter2"), true);
assert.equal(isAllowed(hdr("x", "ผิด"), "", "hunter2"), false);

// ตั้ง SITE_USER = ต้องตรงทั้งคู่
assert.equal(isAllowed(hdr("bob", "hunter2"), "bob", "hunter2"), true);
assert.equal(isAllowed(hdr("eve", "hunter2"), "bob", "hunter2"), false, "ชื่อผิดต้องไม่ผ่าน");

// ไม่มี header / ไม่ได้ตั้งรหัสฝั่งเซิร์ฟเวอร์ = ไม่ผ่าน (ห้ามเปิดเว็บทิ้ง)
assert.equal(isAllowed(null, "", "hunter2"), false);
assert.equal(isAllowed(hdr("a", ""), "", ""), false, "ไม่ตั้งรหัส ต้องไม่ปล่อยผ่าน");

// รหัสยาวไม่เท่ากันต้องไม่ผ่าน (กันหลุดผ่าน prefix)
assert.equal(isAllowed(hdr("a", "hunter"), "", "hunter2"), false);

// ภาษาไทยและอักขระพิเศษต้องใช้ได้
assert.equal(isAllowed(hdr("a", "รหัส@123"), "", "รหัส@123"), true);

console.log("[auth.test OK] ผ่านทั้ง 12 เคส");
