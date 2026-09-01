"""
นับคนจากสตรีมสด YouTube ตามเวลาที่กำหนด

ใช้:  python live_count.py <youtube_url> --minutes 3 --every 3 --save out.mp4

--every N = ประมวลผลทุกเฟรมที่ N (ลดภาระ CPU) ByteTrack ยังตามคนได้ที่ ~10fps
หมายเหตุ: การดึงเฟรมจาก YouTube ผิด ToS ของเขา ใช้เป็น demo เทคนิคเท่านั้น
"""
import argparse, subprocess, sys, time
import cv2, supervision as sv
from ultralytics import YOLO


def stream_url(url):
    out = subprocess.run([sys.executable, "-m", "yt_dlp", "-g", "-f", "232/231/230/best[height<=720]/best", url],
                         capture_output=True, text=True, timeout=90)
    if out.returncode != 0:
        sys.exit("ดึง URL สตรีมไม่ได้:\n" + out.stderr[-500:])
    return out.stdout.strip().splitlines()[0]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--minutes", type=float, default=3)
    p.add_argument("--every", type=int, default=3, help="ประมวลผลทุกเฟรมที่ N")
    p.add_argument("--line", nargs=4, type=int, metavar=("x1", "y1", "x2", "y2"))
    p.add_argument("--save", metavar="out.mp4")
    p.add_argument("--label", default="")
    a = p.parse_args()

    print(f"[1/3] ดึง URL สตรีม…")
    surl = stream_url(a.url)

    cap = cv2.VideoCapture(surl)
    ok, frame = cap.read()
    if not ok:
        sys.exit("เปิดสตรีมไม่ได้")
    h, w = frame.shape[:2]
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    print(f"[2/3] สตรีม {w}x{h} @ {src_fps:.0f}fps | ประมวลผลทุกเฟรมที่ {a.every} (~{src_fps/a.every:.0f}fps)")

    x1, y1, x2, y2 = a.line if a.line else (0, h // 2, w, h // 2)
    line = sv.LineZone(start=sv.Point(x1, y1), end=sv.Point(x2, y2),
                       triggering_anchors=(sv.Position.BOTTOM_CENTER,))
    model = YOLO("yolo11n.pt")
    box = sv.BoxAnnotator(thickness=2)
    trace = sv.TraceAnnotator(thickness=2, trace_length=20)
    line_anno = sv.LineZoneAnnotator(thickness=2, text_scale=0.7, custom_in_text="IN", custom_out_text="OUT")
    writer = cv2.VideoWriter(a.save, cv2.VideoWriter_fourcc(*"mp4v"), src_fps / a.every, (w, h)) if a.save else None

    deadline = time.time() + a.minutes * 60
    idx = proc = 0
    peak = 0
    print(f"[3/3] เริ่มนับ {a.minutes} นาที…")
    while time.time() < deadline:
        ok, frame = cap.read()
        if not ok:
            print("สตรีมหลุด หยุดก่อนกำหนด"); break
        idx += 1
        if idx % a.every:
            continue
        res = model.track(frame, persist=True, classes=[0], tracker="bytetrack.yaml", verbose=False)[0]
        det = sv.Detections.from_ultralytics(res)
        peak = max(peak, len(det))
        if det.tracker_id is not None:
            line.trigger(det)
            frame = trace.annotate(frame, det)
        frame = box.annotate(frame, det)
        frame = line_anno.annotate(frame, line)
        cv2.putText(frame, f"IN {line.in_count}  OUT {line.out_count}  NOW {len(det)}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        if writer:
            writer.write(frame)
        proc += 1
        if proc % 100 == 0:
            print(f"  …เฟรมที่ {proc} | IN {line.in_count} OUT {line.out_count} NOW {len(det)}", flush=True)

    cap.release()
    if writer:
        writer.release()
    mins = a.minutes
    print("\n===== ผลลัพธ์" + (f" — {a.label}" if a.label else "") + " =====")
    print(f"เวลาที่นับ      : {mins} นาที")
    print(f"เฟรมที่ประมวลผล : {proc}")
    print(f"คนเดินเข้า (IN) : {line.in_count}")
    print(f"คนเดินออก (OUT): {line.out_count}")
    print(f"รวมข้ามเส้น     : {line.in_count + line.out_count}  (~{(line.in_count+line.out_count)/mins:.1f} คน/นาที)")
    print(f"คนในเฟรมสูงสุด  : {peak}")


if __name__ == "__main__":
    main()
