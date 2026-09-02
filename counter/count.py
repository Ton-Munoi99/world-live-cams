"""
นับคนเดินข้ามเส้น เข้า/ออก — YOLO11 + supervision ByteTrack + LineZone
วิธีใช้และข้อจำกัดดูที่ README หัวข้อ "โฟลเดอร์ counter/"

ponytail: การนับใช้ supervision.LineZone ทั้งหมด เราแค่ต่อท่อ YOLO→tracker→เส้น
"""
import argparse, sys


def selftest():
    # ตรวจว่า logic นับข้ามเส้นทำงาน: คน 1 คน เดินจากใต้เส้นขึ้นข้ามเส้น = ต้องนับได้ 1 ครั้ง
    import numpy as np, supervision as sv
    line = sv.LineZone(start=sv.Point(0, 100), end=sv.Point(200, 100),
                       triggering_anchors=(sv.Position.CENTER,))

    def det(cy):  # คนกล่องเดียว ที่ y = cy, tracker_id=1
        return sv.Detections(xyxy=np.array([[90., cy - 10, 110., cy + 10]]),
                             tracker_id=np.array([1]))

    line.trigger(det(150))   # อยู่ใต้เส้น (y มาก = ล่างในพิกัดภาพ)
    line.trigger(det(50))    # ข้ามขึ้นเหนือเส้น
    total = line.in_count + line.out_count
    assert total == 1, f"คาดว่านับข้ามได้ 1 ครั้ง แต่ได้ {total} (in={line.in_count}, out={line.out_count})"
    print(f"[selftest OK] นับข้ามเส้นได้ 1 ครั้ง (in={line.in_count}, out={line.out_count})")


def stream_url(url):
    """แปลงลิงก์ YouTube เป็น URL สตรีมที่ OpenCV เปิดได้"""
    import subprocess
    out = subprocess.run([sys.executable, "-m", "yt_dlp", "-g", "-f", "best[height<=720]/best", url],
                         capture_output=True, text=True, timeout=90)
    if out.returncode:
        sys.exit("ดึง URL สตรีมไม่ได้: " + out.stderr[-500:])
    return out.stdout.strip().splitlines()[0]


def run(source, line_pts, save_path, show, minutes=0, every=1):
    import time
    import cv2, supervision as sv
    from ultralytics import YOLO

    src = int(source) if str(source).isdigit() else source
    model = YOLO("yolo11n.pt")  # โหลดอัตโนมัติครั้งแรก (~5MB)

    # หาขนาดเฟรมเพื่อวางเส้นกลางจอถ้าไม่ได้ระบุ
    cap = cv2.VideoCapture(src)
    ok, frame = cap.read()
    if not ok:
        sys.exit(f"เปิดวิดีโอไม่ได้: {source}")
    h, w = frame.shape[:2]
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    cap.release()

    if line_pts:
        x1, y1, x2, y2 = line_pts
    else:  # เส้นแนวนอนกลางจอ
        x1, y1, x2, y2 = 0, h // 2, w, h // 2
    line = sv.LineZone(start=sv.Point(x1, y1), end=sv.Point(x2, y2),
                       triggering_anchors=(sv.Position.BOTTOM_CENTER,))

    box = sv.BoxAnnotator(thickness=2)
    labels = sv.LabelAnnotator(text_scale=0.5)
    trace = sv.TraceAnnotator(thickness=2, trace_length=30)
    line_anno = sv.LineZoneAnnotator(thickness=2, text_scale=0.8,
                                     custom_in_text="IN", custom_out_text="OUT")

    writer = None
    if save_path:
        writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    deadline = time.time() + minutes * 60 if minutes else None
    idx = 0
    # classes=[0] = คนเท่านั้น | persist=True เพื่อคง tracker_id ข้ามเฟรม
    for res in model.track(source=src, stream=True, persist=True, classes=[0],
                           tracker="bytetrack.yaml", verbose=False):
        if deadline and time.time() > deadline:
            break
        idx += 1
        if idx % every:          # ข้ามเฟรมเพื่อลดภาระ CPU ตอนรับสตรีมสด
            continue
        f = res.orig_img
        det = sv.Detections.from_ultralytics(res)
        # เฟรมที่ tracker ยังไม่ให้ id (เช่นเฟรมแรก/ไม่มีคน) ข้ามการนับและวาดเส้นทาง
        if det.tracker_id is not None:
            line.trigger(det)
            f = trace.annotate(f, det)
            f = labels.annotate(f, det, labels=[f"#{i}" for i in det.tracker_id])
        f = box.annotate(f, det)
        f = line_anno.annotate(f, line)
        cv2.putText(f, f"IN {line.in_count}  OUT {line.out_count}  NOW {len(det)}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        if writer:
            writer.write(f)
        if show:
            cv2.imshow("people counter", f)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    if writer:
        writer.release()
        print(f"เซฟแล้ว: {save_path}")
    print(f"สรุป: IN={line.in_count}  OUT={line.out_count}  net={line.in_count - line.out_count}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source", nargs="?", help="ไฟล์วิดีโอ หรือ 0 = เว็บแคม")
    p.add_argument("--url", help="ลิงก์ YouTube live (ต้องมี yt-dlp)")
    p.add_argument("--minutes", type=float, default=0, help="นับกี่นาทีแล้วหยุด (0 = จนจบวิดีโอ)")
    p.add_argument("--every", type=int, default=1, help="ประมวลผลทุกเฟรมที่ N (สตรีมสดใช้ 3)")
    p.add_argument("--line", nargs=4, type=int, metavar=("x1", "y1", "x2", "y2"))
    p.add_argument("--save", metavar="out.mp4")
    p.add_argument("--show", action="store_true", help="เปิดหน้าต่างดูสด")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--demo", action="store_true", help="ดึงวิดีโอคนเดินตัวอย่างมารันเลย")
    a = p.parse_args()
    if a.selftest:
        selftest()
        sys.exit()
    if a.demo:
        from supervision.assets import download_assets, VideoAssets
        src = download_assets(VideoAssets.PEOPLE_WALKING)
    elif a.url:
        src = stream_url(a.url)
    elif a.source:
        src = a.source
    else:
        p.error("ต้องระบุไฟล์วิดีโอ, --url, --demo หรือ --selftest")
    run(src, a.line, a.save, a.show or not a.save, a.minutes, a.every)
