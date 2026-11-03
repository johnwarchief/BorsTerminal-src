# _audit/perf/sysinfo.ps1 — Stage 0: مشخصاتِ ماشین، نقشۀ درایو و وضعیتِ برق
# فقط خواندنی. خروجی برایِ `_audit/perf/SYSINFO.txt` (درِ گزارشِ پایانی).
$ErrorActionPreference = 'SilentlyContinue'

$cs  = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$os  = Get-CimInstance Win32_OperatingSystem
$batt = Get-CimInstance Win32_Battery | Select-Object -First 1

"CPU: " + $cpu.Name
"Cores: " + $cpu.NumberOfCores + "  Threads: " + $cpu.NumberOfLogicalProcessors
"CurrentClockMHz: " + $cpu.CurrentClockSpeed + "  MaxClockMHz: " + $cpu.MaxClockSpeed
"Voltage: " + $cpu.CurrentVoltage
"RAM_GB_Total: " + [math]::Round($cs.TotalPhysicalMemory / 1GB, 2)
"RAM_GB_Free: " + [math]::Round($os.FreePhysicalMemory / 1MB, 2)
"Commit_GB_Limit: " + [math]::Round($os.TotalVirtualMemorySize / 1MB, 2)
"Commit_GB_Free: " + [math]::Round($os.FreeVirtualMemory / 1MB, 2)
"OS: " + $os.Caption + " " + $os.Version + " build " + $os.BuildNumber
"Model: " + $cs.Manufacturer + " " + $cs.Model

foreach ($d in Get-PhysicalDisk) {
  $buckets = (Get-CimInstance -Query "ASSOCIATORS OF {Win32_DiskDrive.DeviceID='$($d.DeviceID)'} WHERE AssocClass=Win32_DiskDriveToDiskPartition") +
             (Get-CimInstance -Query "ASSOCIATORS OF {Win32_DiskDrive.DeviceID='$($d.DeviceID)'} WHERE AssocClass=Win32_DiskDriveToDiskPartition" -Namespace root/cimv2)
  "PHYS: " + $d.FriendlyName + " media=" + $d.MediaType + " sizeGB=" + [math]::Round($d.Size / 1GB, 0) +
    " bus=" + $d.BusType + " health=" + $d.HealthStatus + " spindown=" + $d.NoVerify + " reads=" + $d.Reads + " writes=" + $d.Writes
}

foreach ($ld in Get-CimInstance Win32_LogicalDisk) {
  "LOGICAL: " + $ld.DeviceID + " sizeGB=" + [math]::Round($ld.Size / 1GB, 1) + " freeGB=" + [math]::Round($ld.FreeSpace / 1GB, 1)
}

# نگاشتِ حرفِ درایو به دیسکِ فیزیکی
$map = Get-CimInstance Win32_LogicalDiskToPartition
foreach ($m in $map) {
  $antecedent = ($m.Antecedent -split '"')[3]
  $dependent  = ($m.Dependent  -split '"')[3]
  $disk = Get-CimInstance -Query "SELECT * FROM Win32_DiskDrive WHERE DeviceID='$($antecedent.Replace('\','\\'))'"
  "MAP: " + $dependent + " -> " + $antecedent + " -> " + $disk.Model + " [" + $disk.MediaType + "]"
}

if ($batt) {
  "BatteryStatus: " + $batt.BatteryStatus + " (1=AC, 2=battery)  Charge: " + $batt.EstimatedChargeRemaining
}
$plan = Get-CimInstance -Namespace root\cimv2\power -ClassName Win32_PowerPlan -Filter "IsActive=True"
"PowerPlan: " + $plan.ElementName
"Processors_active: " + $cpu.NumberOfActiveCores
