"""
ไล่เช็คว่ากล้องใน public/index.html ตัวไหนหยุด live หรือปิด embed ไปแล้ว

ใช้:
    python tools/check_cams.py              # เช็คทั้งหมด
    python tools/check_cams.py --only-bad   # โชว์เฉพาะตัวที่เสีย
    python tools/check_cams.py --fix        # ตัวไหนตาย หา id ใหม่จากช่องเดิมมาแทนให้เลย
    python tools/check_cams.py --selftest   # ตรวจตรรกะ ไม่ต้องต่อเน็ต

ทำไมต้องมี: video id ของ YouTube live ตายเมื่อเจ้าของช่องหยุดถ่ายทอด
การ์ดจะขึ้น "unavailable" โดยไม่มีใครรู้จนกว่าจะกดเข้าไปเจอเอง

id เดิมไม่กลับมา แต่ช่องมักเปิดสตรีมใหม่เป็น id ใหม่ — --fix จะตามไปหาให้

ponytail: stdlib ล้วน ไม่ต้องลงอะไร | ขนาน 3 thread พอ ยิงถี่กว่านี้ YouTube ตอบ 429
"""
import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "public" / "index.html"
# CONSENT: ข้ามหน้ายินยอมคุกกี้ที่ YouTube เสิร์ฟให้บาง IP (เช่นดาต้าเซ็นเตอร์ของ CI)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Cookie": "CONSENT=YES+1",
}

# {name:"...", loc:"...", cat:"...", v:"VIDEOID"}
CAM_RE = re.compile(
    r'\{name:"(?P<name>[^"]+)",\s*loc:"(?P<loc>[^"]+)",\s*cat:"(?P<cat>[^"]+)",\s*v:"(?P<v>[\w-]{11})"\}'
)


def parse_cams(html):
    """ดึงรายการกล้องออกจากหน้าเว็บ"""
    return [m.groupdict() for m in CAM_RE.finditer(html)]


def verdict(live, embed):
    """แปลผลเป็นข้อความเดียว — แยกออกมาเพื่อเทสต์ได้"""
    if live and embed:
        return "OK", "ใช้ได้"
    if not live and not embed:
        return "DEAD", "หยุด live + ปิด embed"
    if not live:
        return "DEAD", "หยุดถ่ายทอดสดแล้ว"
    return "NOEMBED", "ปิดไม่ให้เว็บอื่นฝัง"


def got_real_page(html, vid):
    """
    หน้าที่ได้ใช้ตัดสินได้จริงไหม

    YouTube เสิร์ฟหน้าแบบตัดข้อมูลให้ IP ดาต้าเซ็นเตอร์ (เช่น GitHub Actions) —
    ยังมี videoDetails/videoId แต่ "ตัด key playableInEmbed กับ isLiveNow ทิ้ง"
    ถ้าดูแค่ค่าจะกลายเป็น false แล้วฟันธงผิดว่ากล้องตายทั้งหมด
    จึงต้องเช็คว่ามี key อยู่จริง ไม่ใช่ดูแค่ค่า
    """
    return (f'"videoId":"{vid}"' in html
            and '"playableInEmbed"' in html
            and '"isLiveNow"' in html)


def fetch(url, tries=4):
    """ยิงเบาๆ — เจอ 429 (ยิงถี่ไป) ให้รอแล้วลองใหม่ ไม่งั้นจะดูเหมือนกล้องตายทั้งหมด"""
    req = urllib.request.Request(url, headers=HEADERS)
    for i in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=25).read().decode("utf8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == tries - 1:
                raise
            time.sleep(10 * 2 ** i)   # 10, 20, 40 วิ — งานอัตโนมัติรอได้ ไม่มีคนนั่งดู
    raise RuntimeError("unreachable")


def watch(vid):
    return fetch(f"https://www.youtube.com/watch?v={vid}&hl=en&gl=US")


def channel_of(html):
    """ดึง channelId จากหน้าวิดีโอ — หน้าที่สตรีมจบแล้วมักยังมีให้"""
    m = re.search(r'"channelId":"(UC[\w-]+)"', html)
    return m.group(1) if m else None


def video_ids(html, limit=8):
    """ดึง videoId ตามลำดับที่เจอ ไม่ซ้ำ"""
    return list(dict.fromkeys(re.findall(r'"videoId":"([\w-]{11})"', html)))[:limit]


def find_replacement(dead_vid, dead_html):
    """ช่องเดิมเปิดสตรีมใหม่หรือยัง — คืน id ใหม่ที่ live และฝังได้"""
    ch = channel_of(dead_html)
    if not ch:
        return None
    try:
        streams = fetch(f"https://www.youtube.com/channel/{ch}/streams")
    except Exception:
        return None
    for vid in video_ids(streams):
        if vid == dead_vid:
            continue
        try:
            page = watch(vid)
        except Exception:
            continue
        if got_real_page(page, vid) and '"isLiveNow":true' in page and '"playableInEmbed":true' in page:
            return vid
    return None


def check(cam):
    try:
        html = watch(cam["v"])
    except (urllib.error.URLError, TimeoutError) as e:
        return {**cam, "code": "ERROR", "why": f"เรียกหน้าไม่สำเร็จ: {e}"}
    if not got_real_page(html, cam["v"]):
        return {**cam, "code": "ERROR", "why": "ไม่ได้หน้าวิดีโอจริง (อาจโดน YouTube บล็อก)"}
    live = '"isLiveNow":true' in html
    embed = '"playableInEmbed":true' in html
    code, why = verdict(live, embed)
    return {**cam, "code": code, "why": why, "html": html}


def selftest():
    cams = parse_cams('''
      {name:"Times Square", loc:"New York, USA", cat:"เมือง", v:"JQ_jwk_7OVE"},
      {name:"เกาะเสม็ด — วิวทะเล", loc:"ระยอง", cat:"ไทย", v:"P4RMplT6E4c"},
    ''')
    assert len(cams) == 2, cams
    assert cams[0]["name"] == "Times Square" and cams[0]["v"] == "JQ_jwk_7OVE"
    assert cams[1]["cat"] == "ไทย", cams[1]
    assert parse_cams("ไม่มีกล้องในนี้") == []

    assert verdict(True, True)[0] == "OK"
    assert verdict(False, True)[0] == "DEAD"
    assert verdict(True, False)[0] == "NOEMBED"
    assert verdict(False, False)[0] == "DEAD"

    full = '"videoId":"abcdefghijk" "playableInEmbed":true "isLiveNow":true'
    assert got_real_page(full, "abcdefghijk")
    assert not got_real_page("หน้ายินยอมคุกกี้", "abcdefghijk"), "หน้าไม่ใช่วิดีโอต้องไม่ผ่าน"
    assert not got_real_page(full, "zzzzzzzzzzz"), "คนละคลิปต้องไม่ผ่าน"
    # หน้าแบบที่ GitHub runner ได้ — มี videoDetails แต่ถูกตัด key ที่เราต้องใช้
    stripped = '"videoDetails" "videoId":"abcdefghijk" "isLive":true'
    assert not got_real_page(stripped, "abcdefghijk"), "หน้าที่ถูกตัด key ต้องไม่ถือว่าเช็คได้"

    assert channel_of('x"channelId":"UCabc-123_x"y') == "UCabc-123_x"
    assert channel_of("ไม่มี channelId") is None
    assert video_ids('"videoId":"aaaaaaaaaaa" "videoId":"bbbbbbbbbbb" "videoId":"aaaaaaaaaaa"') \
        == ["aaaaaaaaaaa", "bbbbbbbbbbb"], "ต้องไม่ซ้ำและเรียงตามที่เจอ"
    assert video_ids("ว่าง") == []

    page = '{name:"A", loc:"X", cat:"ไทย", v:"aaaaaaaaaaa"},'
    assert swap_id(page, "aaaaaaaaaaa", "bbbbbbbbbbb") == '{name:"A", loc:"X", cat:"ไทย", v:"bbbbbbbbbbb"},'
    assert swap_id("v:\"aaaaaaaaaaa\"", "zzzzzzzzzzz", "b") == "v:\"aaaaaaaaaaa\"", "ไม่ตรงต้องไม่แตะ"
    print("[selftest OK] แกะรายการกล้อง + แปลผล + กันหน้าปลอม + หา/สลับ id ถูกต้อง")


def swap_id(page_html, old, new):
    """สลับ video id ในหน้าเว็บ — แตะเฉพาะที่อยู่ในรูป v:"ID" เท่านั้น"""
    return page_html.replace(f'v:"{old}"', f'v:"{new}"')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-bad", action="store_true", help="โชว์เฉพาะตัวที่เสีย")
    ap.add_argument("--fix", action="store_true", help="ตัวไหนตาย หา id ใหม่จากช่องเดิมมาแทนให้เลย")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    cams = parse_cams(PAGE.read_text(encoding="utf-8"))
    if not cams:
        sys.exit(f"ไม่พบกล้องใน {PAGE}")
    print(f"กำลังเช็ค {len(cams)} กล้อง…\n")

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(check, cams))

    icon = {"OK": "OK ", "DEAD": "ตาย", "NOEMBED": "ฝังไม่ได้", "ERROR": "เช็คไม่ได้"}
    bad = [r for r in results if r["code"] in ("DEAD", "NOEMBED")]
    unknown = [r for r in results if r["code"] == "ERROR"]
    for r in results:
        if a.only_bad and r["code"] == "OK":
            continue
        print(f'{icon[r["code"]]:10} {r["name"][:38]:40} {r["loc"][:16]:18} {r["why"]}')

    ok = len(results) - len(bad) - len(unknown)
    print(f'\nสรุป: ใช้ได้ {ok}/{len(results)}'
          + (f' | เช็คไม่ได้ {len(unknown)}' if unknown else ''))
    if bad:
        print(f"ต้องแก้ {len(bad)} ตัว:")
        for r in bad:
            print(f'  {r["name"]}  (v:"{r["v"]}")  {r["why"]}')

        # ช่องเดิมมักเปิดสตรีมใหม่เป็น id ใหม่ — ตามไปหาให้
        print("\nกำลังหา id ใหม่จากช่องเดิม…")
        page = PAGE.read_text(encoding="utf-8")
        fixed = 0
        for r in bad:
            new = find_replacement(r["v"], r.get("html", ""))
            if not new:
                print(f'  {r["name"]:38} ยังไม่เจอสตรีมใหม่ — ต้องลบออกหรือหาเอง')
                continue
            print(f'  {r["name"]:38} เจอ! {r["v"]} -> {new}')
            page = swap_id(page, r["v"], new)
            fixed += 1
        if fixed and a.fix:
            PAGE.write_text(page, encoding="utf-8")
            print(f"\nแก้ให้แล้ว {fixed} ตัวใน {PAGE.name} — รันเช็คอีกรอบเพื่อยืนยัน")
            return 0
        if fixed:
            print(f"\nเจอตัวแทน {fixed} ตัว — ใส่ --fix เพื่อให้แก้ไฟล์ให้อัตโนมัติ")
    elif not unknown:
        print("ทุกกล้องใช้ได้ปกติ")

    # เช็คไม่สำเร็จเกินครึ่ง = เชื่อผลรอบนี้ไม่ได้ ห้ามฟันธงว่ากล้องเสีย
    if len(unknown) > len(results) / 2:
        print(f"\nเชื่อผลรอบนี้ไม่ได้ — เช็คไม่สำเร็จ {len(unknown)}/{len(results)} ตัว")
        return 2
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
