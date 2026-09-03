# เช็คกล้องอัตโนมัติทุกวัน — หาตัวแทนให้ตัวที่ตาย แล้ว push ขึ้น GitHub
#
# ติดตั้งให้รันทุก 8 โมงเช้า:  powershell -ExecutionPolicy Bypass -File tools\install_task.ps1
# รันเองเดี๋ยวนี้:              powershell -ExecutionPolicy Bypass -File tools\daily_check.ps1
#
# ต้องรันบนเครื่องตัวเอง — YouTube ตัดข้อมูลให้ IP ดาต้าเซ็นเตอร์ CI จึงเช็คไม่ได้

$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$log = Join-Path $root "tools\daily_check.log"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm"

function Write-Log($text) {
    Add-Content -Path $log -Value $text -Encoding UTF8
}

Write-Log ""
Write-Log "===== $stamp ====="

# --fix = ตัวไหนตาย ตามไปหา id ใหม่จากช่องเดิมมาแทนให้เลย
$out = & python tools/check_cams.py --only-bad --fix 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { Write-Log $_ }

if ($code -eq 2) {
    # เช็คไม่สำเร็จเกินครึ่ง (เน็ตล่ม / โดน 429) — ห้ามแตะไฟล์ ไว้รอบหน้าค่อยว่า
    Write-Log "ผล: เชื่อไม่ได้ ข้ามรอบนี้ ไม่แก้อะไร"
    exit 0
}

# มีอะไรเปลี่ยนไหม (check_cams --fix จะแก้เฉพาะ public/index.html)
$changed = & git status --porcelain public/index.html
if (-not $changed) {
    Write-Log "ผล: ทุกกล้องปกติ ไม่มีอะไรต้องแก้"
    exit 0
}

Write-Log "ผล: มีการสลับ id — กำลัง commit และ push"
& git add public/index.html
& git -c user.email="sponlapat99999@gmail.com" -c user.name="Ton-Munoi99" commit -q -m "อัปเดต id กล้องอัตโนมัติ $stamp

สลับ id ที่หยุด live เป็นสตรีมใหม่ของช่องเดิม โดย tools/check_cams.py --fix

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
& git push -q origin main
if ($LASTEXITCODE -eq 0) {
    Write-Log "push สำเร็จ — Netlify จะ deploy ให้เอง"
} else {
    Write-Log "push ไม่สำเร็จ (exit $LASTEXITCODE) — commit ค้างไว้ในเครื่อง"
}
