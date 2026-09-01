/**
 * กันเว็บด้วยรหัสผ่าน — ทำงานที่ edge ก่อนส่งไฟล์ออกไป
 * ถ้ารหัสไม่ถูก เบราว์เซอร์จะไม่ได้ HTML เลย (ต่างจากการเช็คด้วย JS ในหน้าเว็บ)
 *
 * ตั้งรหัสที่: Netlify → Site configuration → Environment variables
 *   SITE_PASSWORD = รหัสที่ต้องการ   (จำเป็น)
 *   SITE_USER     = ชื่อผู้ใช้        (ไม่ใส่ก็ได้ = ใส่ชื่ออะไรก็ผ่าน)
 * รหัสไม่เคยอยู่ในโค้ด จึงไม่หลุดขึ้น GitHub
 */

// เทียบแบบเวลาคงที่ กัน timing attack
function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// แยก user/pass จาก header "Basic base64(user:pass)"
export function parseBasic(header) {
  if (typeof header !== "string" || !header.startsWith("Basic ")) return null;
  let decoded;
  try {
    // atob คืน byte ดิบ ต้องถอดเป็น UTF-8 อีกที ไม่งั้นรหัสภาษาไทย/อีโมจิจะเพี้ยน
    const raw = atob(header.slice(6).trim());
    decoded = new TextDecoder().decode(Uint8Array.from(raw, (c) => c.charCodeAt(0)));
  } catch {
    return null;
  }
  const i = decoded.indexOf(":");
  if (i < 0) return null;
  return { user: decoded.slice(0, i), pass: decoded.slice(i + 1) };
}

// ตัดสินว่าให้ผ่านไหม — แยกออกมาเพื่อเทสต์ได้โดยไม่ต้องมี Netlify
export function isAllowed(header, expectUser, expectPass) {
  if (!expectPass) return false;
  const c = parseBasic(header);
  if (!c) return false;
  if (!safeEqual(c.pass, expectPass)) return false;
  return expectUser ? safeEqual(c.user, expectUser) : true;
}

const env = (k) => {
  try { return globalThis.Netlify?.env?.get(k) ?? globalThis.Deno?.env?.get(k) ?? ""; }
  catch { return ""; }
};

const page = (title, body) =>
  `<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0B0E13;color:#E8EBF0;
font-family:system-ui,"Segoe UI",sans-serif;padding:24px;line-height:1.7}
.box{max-width:44ch;text-align:center}h1{font-size:19px;margin:0 0 10px}
p{color:#8A94A3;font-size:14px;margin:0 0 8px}code{background:#1D242E;padding:2px 7px;border-radius:5px;font-size:13px}
</style></head><body><div class="box">${body}</div></body></html>`;

export default async (request, context) => {
  const user = env("SITE_USER");
  const pass = env("SITE_PASSWORD");

  // ยังไม่ตั้งรหัส — ปิดเว็บไว้ก่อน ปลอดภัยกว่าเปิดทิ้ง แล้วบอกวิธีตั้ง
  if (!pass) {
    return new Response(
      page("ยังไม่ได้ตั้งรหัสผ่าน", `<h1>🔒 ยังไม่ได้ตั้งรหัสผ่าน</h1>
      <p>ไปที่ Netlify → Site configuration → Environment variables</p>
      <p>เพิ่ม <code>SITE_PASSWORD</code> แล้วสั่ง Deploy ใหม่หนึ่งครั้ง</p>`),
      { status: 503, headers: { "content-type": "text/html; charset=utf-8" } }
    );
  }

  if (isAllowed(request.headers.get("authorization"), user, pass)) {
    return context.next();
  }

  return new Response(
    page("ต้องใส่รหัสผ่าน", `<h1>🔒 หน้านี้ต้องใส่รหัสผ่าน</h1>
    <p>รีเฟรชหน้านี้เพื่อกรอกใหม่ หรือขอรหัสจากเจ้าของเว็บ</p>`),
    {
      status: 401,
      headers: {
        "WWW-Authenticate": 'Basic realm="World Live Cams", charset="UTF-8"',
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-store",
      },
    }
  );
};
