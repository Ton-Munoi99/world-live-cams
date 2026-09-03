# World Live Cams

เว็บดูกล้องถ่ายทอดสด 60 ตัวทั่วโลก — ไฟล์เดียว ไม่ต้อง build ไม่มี dependency

**เดโม:** https://world-live-cams.netlify.app (ต้องใส่รหัสผ่าน)

| หมวด | จำนวน | ตัวอย่าง |
|---|---|---|
| ไทย | 19 | กรุงเทพ 10, เชียงใหม่, เกาะสมุย 3, หัวหิน, พัทยา, เกาะเต่า, เกาะเสม็ด, เกาะช้าง, เกาะพะงัน |
| เมือง | 24 | Times Square, Shibuya, Abbey Road, เวนิส, ซิดนีย์, โซล, SkylineWebcams |
| ธรรมชาติ | 8 | ภูเขาไฟ Mayon, แสงเหนือ, ทะเลทราย Namib, โลกจากอวกาศ |
| สัตว์ | 9 | หมีตกปลา Brooks Falls, แนวปะการัง, พะยูน, สวนสัตว์เชียงใหม่ |

แตะการ์ดเพื่อเล่น — เล่นทีละกล้อง เปิดตัวใหม่หยุดตัวเก่าอัตโนมัติ · กรองด้วยชิปหมวด + ค้นหา ·
เพิ่มกล้องเองด้วยลิงก์ YouTube Live (เก็บใน localStorage) · รองรับมือถือเต็มรูปแบบ

## รันในเครื่อง

ต้องเสิร์ฟผ่าน http — เปิด `file://` ตรงๆ ไม่ได้ YouTube จะบล็อก embed (Error 153)

```bash
cd public && python -m http.server 8777
```

## รหัสผ่านเข้าเว็บ

`netlify/edge-functions/auth.js` เช็ค HTTP Basic Auth ที่ edge **ก่อน**ส่งไฟล์ — รหัสผิดไม่ได้ HTML เลย
รหัสเก็บเป็น environment variable ไม่เคยอยู่ในโค้ด

ตั้งที่ Netlify → Site configuration → Environment variables แล้ว **Deploy ใหม่หนึ่งครั้ง**

| ตัวแปร | จำเป็น | ความหมาย |
|---|---|---|
| `SITE_PASSWORD` | ใช่ | รหัสผ่าน (ภาษาไทยได้) |
| `SITE_USER` | ไม่ | ไม่ตั้ง = ใส่ชื่ออะไรก็ผ่าน ขอแค่รหัสถูก |

ยังไม่ตั้ง `SITE_PASSWORD` = เว็บปิดไว้พร้อมข้อความบอกวิธีตั้ง (ปลอดภัยกว่าเปิดทิ้ง)

## นับคนในเว็บ — `/counter.html`

กดปุ่ม **👣 นับคน** บนหน้าแรก นับคนเดินผ่านจากกล้องของเครื่องหรือไฟล์วิดีโอ
ประมวลผลในเบราว์เซอร์ด้วย TensorFlow.js (coco-ssd) ภาพไม่ถูกส่งออกไปไหน

**นับกล้อง YouTube ในหน้าแรกไม่ได้** — iframe เป็น cross-origin เบราว์เซอร์ห้ามอ่าน pixel เป็นข้อจำกัดตายตัว

## นับคนแบบแม่นกว่า — `counter/count.py`

YOLO11 + ByteTrack แม่นกว่าเวอร์ชันเบราว์เซอร์ เหมาะกับเก็บข้อมูลจริง

```bash
pip install ultralytics supervision opencv-python
python counter/count.py --selftest                       # ตรวจตรรกะ ไม่ต้องมีวิดีโอ
python counter/count.py --demo --save out.mp4            # วิดีโอตัวอย่าง
python counter/count.py your.mp4 --save out.mp4
python counter/count.py 0 --show                         # เว็บแคม
python counter/count.py --url <yt_url> --minutes 3 --every 3   # สตรีมสด (ต้องมี yt-dlp)
```

ได้ `IN` / `OUT` / `net` = foot-traffic data
`--url` ดึงเฟรมจาก YouTube ซึ่งผิด ToS ของเขา — ใช้เป็น demo เทคนิคเท่านั้น

## เช็คกล้องตาย

id ของ YouTube live ตายเมื่อเจ้าของช่องหยุดถ่ายทอด **และไม่กลับมาที่ id เดิม** — ถ้าเปิดใหม่จะเป็น id ใหม่เสมอ

```bash
python tools/check_cams.py             # เช็คทั้งหมด
python tools/check_cams.py --only-bad
python tools/check_cams.py --fix       # เจอตาย -> หา id ใหม่จากช่องเดิมมาแทนให้เลย
python tools/check_cams.py --selftest
```

แยกผล **ตาย** (หยุด live) · **ฝังไม่ได้** (ปิด embed) · **เช็คไม่ได้**

`--fix` ตามไปดูช่องเดิมว่าเปิดสตรีมใหม่หรือยัง เจอแล้วสลับ id ในไฟล์ให้อัตโนมัติ
ไม่ใส่ `--fix` จะแค่บอกว่าเจอตัวแทนตัวไหน ไม่แตะไฟล์

### เช็คอัตโนมัติทุกวัน 08:00

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_task.ps1
```

ตั้ง Windows Task Scheduler ให้รัน `tools\daily_check.ps1` ทุกเช้า — เช็คกล้อง หา id ใหม่ให้ตัวที่ตาย
แล้ว commit + push เอง (Netlify deploy ต่อให้) ผลย้อนหลังดูที่ `tools\daily_check.log`

| คำสั่ง | ทำอะไร |
|---|---|
| `schtasks /Run /TN WorldLiveCams-CheckCams` | สั่งรันเดี๋ยวนี้ |
| `schtasks /Query /TN WorldLiveCams-CheckCams` | ดูสถานะ / รอบถัดไป |
| `powershell -ExecutionPolicy Bypass -File tools\install_task.ps1 -Remove` | ถอนออก |

**รอบไหนเช็คไม่สำเร็จ (เน็ตล่ม / โดน 429) จะข้ามไปเฉยๆ ไม่แตะไฟล์** — กันไม่ให้ไปลบกล้องดีๆ ทิ้ง

> รันบนเครื่องตัวเองเท่านั้น — YouTube ตัด `playableInEmbed`/`isLiveNow` ออกจากหน้าที่เสิร์ฟให้
> IP ดาต้าเซ็นเตอร์ (ขึ้น "Sign in to confirm you're not a bot") ทำให้ CI เช็คไม่ได้

## เทสต์

```bash
python counter/count.py --selftest
python tools/check_cams.py --selftest
node tests/tracker.test.mjs
node tests/auth.test.mjs
```
