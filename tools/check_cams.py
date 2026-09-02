"""
ไล่เช็คว่ากล้องใน public/index.html ตัวไหนหยุด live หรือปิด embed ไปแล้ว

ใช้:
    python tools/check_cams.py              # เช็คทั้งหมด
    python tools/check_cams.py --only-bad   # โชว์เฉพาะตัวที่เสีย
    python tools/check_cams.py --selftest   # ตรวจตรรกะ ไม่ต้องต่อเน็ต

ทำไมต้องมี: video id ของ YouTube live ตายเมื่อเจ้าของช่องหยุดถ่ายทอด
การ์ดจะขึ้น "unavailable" โดยไม่มีใครรู้จนกว่าจะกดเข้าไปเจอเอง

ponytail: stdlib ล้วน ไม่ต้องลงอะไร | เช็คขนานด้วย thread เพราะรอเน็ตเป็นหลัก
"""
import argparse
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "public" / "index.html"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
# CONSENT: ข้ามหน้ายินยอมคุกกี้ที่ YouTube เสิร์ฟให้บาง IP (เช่นดาต้าเซ็นเตอร์ของ CI)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+1"}

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
    """ได้หน้าวิดีโอจริงไหม — กัน YouTube เสิร์ฟหน้า consent/บล็อกบอทแล้วเราไปฟันธงว่ากล้องตาย"""
    return '"videoDetails"' in html and f'"videoId":"{vid}"' in html


def check(cam):
    url = "https://www.youtube.com/watch?v=" + cam["v"] + "&hl=en&gl=US"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf8", "ignore")
    except (urllib.error.URLError, TimeoutError) as e:
        return {**cam, "code": "ERROR", "why": f"เรียกหน้าไม่สำเร็จ: {e}"}
    if not got_real_page(html, cam["v"]):
        return {**cam, "code": "ERROR", "why": "ไม่ได้หน้าวิดีโอจริง (อาจโดน YouTube บล็อก)"}
    live = '"isLiveNow":true' in html
    embed = '"playableInEmbed":true' in html
    code, why = verdict(live, embed)
    return {**cam, "code": code, "why": why}


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

    assert got_real_page('x"videoDetails"y"videoId":"abcdefghijk"z', "abcdefghijk")
    assert not got_real_page("หน้ายินยอมคุกกี้", "abcdefghijk"), "หน้าไม่ใช่วิดีโอต้องไม่ผ่าน"
    assert not got_real_page('"videoDetails" แต่คนละคลิป "videoId":"zzzzzzzzzzz"', "abcdefghijk")
    print("[selftest OK] แกะรายการกล้อง + แปลผล + กันหน้าปลอม ถูกต้อง")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-bad", action="store_true", help="โชว์เฉพาะตัวที่เสีย")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    cams = parse_cams(PAGE.read_text(encoding="utf-8"))
    if not cams:
        sys.exit(f"ไม่พบกล้องใน {PAGE}")
    print(f"กำลังเช็ค {len(cams)} กล้อง…\n")

    with ThreadPoolExecutor(max_workers=8) as pool:
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
        print(f"ต้องแก้ {len(bad)} ตัว — ลบออกหรือหาลิงก์ใหม่มาแทน:")
        for r in bad:
            print(f'  {r["name"]}  (v:"{r["v"]}")  {r["why"]}')
    elif not unknown:
        print("ทุกกล้องใช้ได้ปกติ")

    # เช็คไม่สำเร็จเกินครึ่ง = เชื่อผลรอบนี้ไม่ได้ ห้ามฟันธงว่ากล้องเสีย
    if len(unknown) > len(results) / 2:
        print(f"\nเชื่อผลรอบนี้ไม่ได้ — เช็คไม่สำเร็จ {len(unknown)}/{len(results)} ตัว")
        return 2
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
