<#
.SYNOPSIS
  가로로 나열된 포즈 이미지(투명 PNG)를 균일 셀 스프라이트 시트 + JSON 으로 만든다.

.DESCRIPTION
  1) 알파가 있는 열(column)을 훑어 포즈 구간을 나눈다(투명 열이 Gap 이상 이어지면 다음 포즈).
  2) 모든 포즈에 같은 배율을 적용해 셀 안에 넣는다(캐릭터 크기가 프레임마다 달라지지 않게).
  3) 각 포즈를 셀의 가로 중앙, 발끝이 셀 높이의 AnchorY(기본 95%) 지점에 오도록 배치한다.
     → features/room 의 기준점(가로 중앙, 세로 95%)과 일치한다.
  4) <Target>.json 에 프레임 정보를 쓴다.
  입력은 remove-white-bg.ps1 -NoCrop 으로 배경을 먼저 지운 PNG 여야 한다.
  Windows PowerShell 5.1 + .NET System.Drawing 전용 로컬 도구.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/assets/build-sprite-sheet.ps1 -Source walk-nobg.png -Target assets/sprites/characters/char1-walk.png -Animation walk -Fps 8
#>
param(
  [Parameter(Mandatory = $true)][string]$Source,
  [Parameter(Mandatory = $true)][string]$Target,
  [int]$CellWidth = 256,
  [int]$CellHeight = 384,
  # 포즈 사이로 인정할 최소 투명 열 수
  [int]$Gap = 6,
  # 발끝 기준선 (셀 높이 비율)
  [double]$AnchorY = 0.95,
  # 셀 안에서 포즈가 차지할 최대 비율
  [double]$Fill = 0.92,
  [string]$Animation = "walk",
  [int]$Fps = 8,
  [bool]$Loop = $true
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$csharp = @"
using System;
using System.Collections.Generic;
public static class SheetScan {
  // 알파 > 8 인 픽셀이 있는 열 배열
  public static bool[] Columns(byte[] px, int w, int h) {
    bool[] cols = new bool[w];
    for (int x = 0; x < w; x++) for (int y = 0; y < h; y++) { if (px[(y * w + x) * 4 + 3] > 8) { cols[x] = true; break; } }
    return cols;
  }
  // 구간 [x0,x1] 안의 세로 bbox: [minY, maxY]
  public static int[] RowsIn(byte[] px, int w, int h, int x0, int x1) {
    int minY = h, maxY = -1;
    for (int y = 0; y < h; y++) for (int x = x0; x <= x1; x++) { if (px[(y * w + x) * 4 + 3] > 8) { if (y < minY) minY = y; if (y > maxY) maxY = y; break; } }
    return maxY < 0 ? null : new int[] { minY, maxY };
  }
}
"@
if (-not ("SheetScan" -as [type])) { Add-Type -TypeDefinition $csharp }

$src = [System.Drawing.Bitmap]::FromFile((Resolve-Path $Source).Path)
try {
  $w = $src.Width; $h = $src.Height
  $bmp = New-Object System.Drawing.Bitmap $w, $h, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp); $g.DrawImage($src, 0, 0, $w, $h); $g.Dispose()
  $rect = New-Object System.Drawing.Rectangle 0, 0, $w, $h
  $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, $bmp.PixelFormat)
  $bytes = New-Object byte[] ($data.Stride * $h)
  [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
  $bmp.UnlockBits($data)

  # 1) 포즈 구간 나누기
  $cols = [SheetScan]::Columns($bytes, $w, $h)
  $segments = @(); $start = -1; $blank = 0
  for ($x = 0; $x -lt $w; $x++) {
    if ($cols[$x]) {
      if ($start -lt 0) { $start = $x }
      $blank = 0; $last = $x
    } elseif ($start -ge 0) {
      $blank++
      if ($blank -ge $Gap) { $segments += ,@($start, $last); $start = -1; $blank = 0 }
    }
  }
  if ($start -ge 0) { $segments += ,@($start, $last) }
  if ($segments.Count -eq 0) { throw "포즈를 찾지 못했습니다: $Source" }

  # 2) 각 포즈 bbox 와 공통 배율
  $boxes = @()
  foreach ($s in $segments) {
    $rows = [SheetScan]::RowsIn($bytes, $w, $h, $s[0], $s[1])
    $boxes += ,@($s[0], $rows[0], ($s[1] - $s[0] + 1), ($rows[1] - $rows[0] + 1))
  }
  $maxW = ($boxes | ForEach-Object { $_[2] } | Measure-Object -Maximum).Maximum
  $maxH = ($boxes | ForEach-Object { $_[3] } | Measure-Object -Maximum).Maximum
  $scale = [Math]::Min(($CellWidth * $Fill) / $maxW, ($CellHeight * $Fill) / $maxH)

  # 3) 시트에 배치
  $count = $boxes.Count
  $sheet = New-Object System.Drawing.Bitmap ($CellWidth * $count), $CellHeight, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $sg = [System.Drawing.Graphics]::FromImage($sheet)
  $sg.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $sg.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $baseline = [Math]::Round($CellHeight * $AnchorY)
  for ($i = 0; $i -lt $count; $i++) {
    $b = $boxes[$i]
    $dw = [Math]::Round($b[2] * $scale); $dh = [Math]::Round($b[3] * $scale)
    $dx = $i * $CellWidth + [Math]::Round(($CellWidth - $dw) / 2); $dy = $baseline - $dh
    $dest = New-Object System.Drawing.Rectangle $dx, $dy, $dw, $dh
    $srcRect = New-Object System.Drawing.Rectangle $b[0], $b[1], $b[2], $b[3]
    $sg.DrawImage($bmp, $dest, $srcRect, [System.Drawing.GraphicsUnit]::Pixel)
  }
  $sg.Dispose()

  $outDir = Split-Path -Parent $Target
  if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Force $outDir | Out-Null }
  $sheet.Save($Target, [System.Drawing.Imaging.ImageFormat]::Png)
  $sheet.Dispose(); $bmp.Dispose()

  # 4) 프레임 정보 JSON (features/room 이 읽는 형식)
  $frames = 0..($count - 1)
  $json = [ordered]@{
    sheet      = (Split-Path -Leaf $Target)
    cell       = @($CellWidth, $CellHeight)
    columns    = $count
    anchor     = @(0.5, $AnchorY)
    animations = [ordered]@{ $Animation = [ordered]@{ frames = $frames; fps = $Fps; loop = $Loop } }
  }
  $jsonPath = [System.IO.Path]::ChangeExtension($Target, ".json")
  [System.IO.File]::WriteAllText($jsonPath, ($json | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding $false))
  Write-Output ("{0}: 포즈 {1}개, 배율 {2:N3}, 시트 {3}x{4} -> {5}" -f (Split-Path -Leaf $Source), $count, $scale, ($CellWidth * $count), $CellHeight, $Target)
} finally {
  $src.Dispose()
}
