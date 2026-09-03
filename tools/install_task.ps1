# ตั้ง/ถอน งานอัตโนมัติเช็คกล้องทุกวัน 08:00
#
# ติดตั้ง:  powershell -ExecutionPolicy Bypass -File tools\install_task.ps1
# ถอน:     powershell -ExecutionPolicy Bypass -File tools\install_task.ps1 -Remove
# ดูสถานะ: schtasks /Query /TN "WorldLiveCams-CheckCams" /V /FO LIST

param([switch]$Remove)

$name = "WorldLiveCams-CheckCams"
$script = Join-Path $PSScriptRoot "daily_check.ps1"

if ($Remove) {
    schtasks /Delete /TN $name /F
    exit $LASTEXITCODE
}

if (-not (Test-Path $script)) {
    Write-Host "ไม่พบ $script"
    exit 1
}

# /RL LIMITED = สิทธิ์ผู้ใช้ธรรมดา ไม่ต้อง admin
$action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
schtasks /Create /TN $name /TR $action /SC DAILY /ST 08:00 /RL LIMITED /F

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "ตั้งเรียบร้อย — จะเช็คกล้องทุกวัน 08:00 น."
    Write-Host "ดูผลย้อนหลังที่: tools\daily_check.log"
    Write-Host "ทดสอบเดี๋ยวนี้:  schtasks /Run /TN $name"
    Write-Host "ถอนออก:         powershell -ExecutionPolicy Bypass -File tools\install_task.ps1 -Remove"
}
exit $LASTEXITCODE
