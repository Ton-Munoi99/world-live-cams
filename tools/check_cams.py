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


def check(cam):
    url = "https://www.youtube.com/watch?v=" + cam["v"]
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    try:
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf8", "ignore")
    except (urllib.error.URLError, TimeoutError) as e:
        return {**cam, "code": "ERROR", "why": f"เช็คไม่ได้: {e}"}
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
    print("[selftest OK] แกะรายการกล้อง + แปลผล ถูกต้อง")


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
    bad = [r for r in results if r["code"] != "OK"]
    for r in results:
        if a.only_bad and r["code"] == "OK":
            continue
        print(f'{icon[r["code"]]:10} {r["name"][:38]:40} {r["loc"][:16]:18} {r["why"]}')

    print(f'\nสรุป: ใช้ได้ {len(results)-len(bad)}/{len(results)}')
    if bad:
        print(f"ต้องแก้ {len(bad)} ตัว — ลบออกหรือหาลิงก์ใหม่มาแทน:")
        for r in bad:
            print(f'  {r["name"]}  (v:"{r["v"]}")  {r["why"]}')
    else:
        print("ทุกกล้องใช้ได้ปกติ")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
