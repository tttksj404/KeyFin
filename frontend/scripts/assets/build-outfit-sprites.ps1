<#
.SYNOPSIS
  등급별 의상 세트 원본(투명 PNG)을 방 씬·상점용 스프라이트로 만든다.

.DESCRIPTION
  원본은 세트마다 따로 생성돼 캔버스 여백과 렌더 배율이 조금씩 다르다(내용 높이 1296~1357px).
  그대로 쓰면 옷을 갈아입을 때마다 캐릭터 키가 달라 보이므로 내용 경계로 정규화한다.

  1) 알파 > 8 인 픽셀의 경계(bbox)를 찾아 내용만 잘라낸다.
  2) standing 의 내용 높이를 ContentHeight 로 맞추는 배율을 구하고, **같은 세트의 sitting 에도 그 배율을 그대로** 쓴다.
     포즈마다 높이를 700 으로 맞추면 "앉으면 조금 낮아진다"는 원본의 비율이 사라져 앉을 때 캐릭터가 커 보인다.
     세트별로 배율을 하나만 쓰므로 옷을 갈아입어도 키는 같고, 포즈 사이 높이 차이는 원본 그대로 남는다.
  3) 캔버스는 가로 중앙 · 발끝이 캔버스 아래에서 BottomPadding 만큼 위 → char1-idle.png(496x756, 내용 271x700, 하단 여백 32)와
     같은 규약이라 features/room 의 기준점(가로 중앙, 세로 95%)과 CHARACTER_SIZE 를 그대로 쓸 수 있다.
  4) shop 은 상품 타일용이라 내용 bbox 를 ShopWidth 에 맞춰 줄이고 여백 없이 저장한다.

  Windows PowerShell 5.1 + .NET System.Drawing 전용 로컬 도구이며 앱 빌드와 무관하다.
  원본에 이미 알파가 있으므로 remove-white-bg.ps1 을 먼저 돌릴 필요가 없다.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/assets/build-outfit-sprites.ps1 -Source C:\Users\SSAFY\Desktop\rpg_grade_outfit_sets -Target assets/sprites/outfits
#>
param(
  # 등급 폴더(01_epic, 02_legendary, 03_mythic)를 담은 원본 루트
  [Parameter(Mandatory = $true)][string]$Source,
  # 결과를 쓸 폴더. 등급별 하위 폴더를 만든다
  [Parameter(Mandatory = $true)][string]$Target,
  # 방 씬 스프라이트 캔버스
  [int]$CanvasWidth = 496,
  [int]$CanvasHeight = 756,
  # 캔버스 안 내용(캐릭터) 높이와 발끝 아래 여백
  [int]$ContentHeight = 700,
  [int]$BottomPadding = 32,
  # 상점 타일 가로 크기
  [int]$ShopWidth = 512,
  # 이 값보다 알파가 큰 픽셀만 내용으로 본다(안티에일리어싱 가장자리 제외)
  [int]$AlphaFloor = 8
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

# 원본 폴더 이름 → asset_key. 서버 items.asset_key 와 같아야 앱이 스프라이트를 찾는다(백엔드 V19__seed_avatar_outfit_sets.sql 의 값, 2026-09-21 대조).
$SETS = [ordered]@{
  '01_epic'      = 'outfit_epic_mage'
  '02_legendary' = 'outfit_legendary_paladin'
  '03_mythic'    = 'outfit_mythic_dragon'
}

function Get-AlphaBounds {
  param([System.Drawing.Bitmap]$Bitmap, [int]$Floor)

  $w = $Bitmap.Width; $h = $Bitmap.Height
  $rect = New-Object System.Drawing.Rectangle 0, 0, $w, $h
  $data = $Bitmap.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  try {
    $stride = $data.Stride
    $bytes = New-Object byte[] ($stride * $h)
    [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
  } finally {
    $Bitmap.UnlockBits($data)
  }

  $minX = $w; $maxX = -1; $minY = $h; $maxY = -1
  for ($y = 0; $y -lt $h; $y++) {
    $row = $y * $stride
    for ($x = 0; $x -lt $w; $x++) {
      if ($bytes[$row + $x * 4 + 3] -gt $Floor) {
        if ($x -lt $minX) { $minX = $x }
        if ($x -gt $maxX) { $maxX = $x }
        if ($y -lt $minY) { $minY = $y }
        if ($y -gt $maxY) { $maxY = $y }
      }
    }
  }
  if ($maxX -lt 0) { throw "내용이 없는 이미지다(알파 전부 $Floor 이하)" }

  New-Object System.Drawing.Rectangle $minX, $minY, ($maxX - $minX + 1), ($maxY - $minY + 1)
}

function New-Canvas {
  param([int]$Width, [int]$Height)

  $bmp = New-Object System.Drawing.Bitmap $Width, $Height, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.Clear([System.Drawing.Color]::Transparent)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  # 투명 캔버스에 올리므로 합성하지 않고 그대로 복사한다(가장자리 흐림 방지)
  $g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
  @{ Bitmap = $bmp; Graphics = $g }
}

# 세트의 기준 배율. 서 있는 자세의 내용 높이를 ContentHeight 에 맞추는 값이며 같은 세트의 앉은 자세도 이 값을 쓴다.
function Get-SceneScale {
  param([string]$StandingFile)

  $src = [System.Drawing.Bitmap]::FromFile((Resolve-Path $StandingFile).Path)
  try {
    $box = Get-AlphaBounds -Bitmap $src -Floor $AlphaFloor
    $ContentHeight / $box.Height
  } finally {
    $src.Dispose()
  }
}

function Write-Sprite {
  param(
    [string]$SourceFile,
    [string]$TargetFile,
    # 'scene' = 캔버스 고정 + 발끝 정렬, 'tile' = bbox 를 가로 기준으로 축소
    [string]$Mode,
    # 'scene' 에서 쓸 배율. 세트 안에서 같은 값을 넘겨야 포즈 사이 키가 어긋나지 않는다
    [double]$Scale = 0
  )

  $src = [System.Drawing.Bitmap]::FromFile((Resolve-Path $SourceFile).Path)
  try {
    $box = Get-AlphaBounds -Bitmap $src -Floor $AlphaFloor

    if ($Mode -eq 'scene') {
      if ($Scale -le 0) { throw "scene 모드에는 Scale 이 필요하다" }
      $drawW = [int][Math]::Round($box.Width * $Scale)
      $drawH = [int][Math]::Round($box.Height * $Scale)
      $canvas = New-Canvas -Width $CanvasWidth -Height $CanvasHeight
      $x = [int][Math]::Round(($CanvasWidth - $drawW) / 2.0)
      $y = $CanvasHeight - $BottomPadding - $drawH
      if ($drawW -gt $CanvasWidth) { throw "내용 가로 $drawW 가 캔버스 $CanvasWidth 를 넘는다 — CanvasWidth 를 키워라" }
      if ($y -lt 0) { throw "내용 세로가 캔버스를 넘는다 — CanvasHeight 를 키워라" }
    } else {
      $drawW = $ShopWidth
      $drawH = [int][Math]::Round($box.Height * ($ShopWidth / $box.Width))
      $canvas = New-Canvas -Width $drawW -Height $drawH
      $x = 0; $y = 0
    }

    $dest = New-Object System.Drawing.Rectangle $x, $y, $drawW, $drawH
    $canvas.Graphics.DrawImage($src, $dest, $box.X, $box.Y, $box.Width, $box.Height, [System.Drawing.GraphicsUnit]::Pixel)
    $canvas.Graphics.Dispose()

    $dir = Split-Path $TargetFile -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $canvas.Bitmap.Save($TargetFile, [System.Drawing.Imaging.ImageFormat]::Png)
    $canvas.Bitmap.Dispose()

    $kb = [int]((Get-Item $TargetFile).Length / 1KB)
    Write-Output ("  {0,-13} bbox {1,4}x{2,-4} -> {3,3}x{4,-3} @({5},{6})  {7} KB" -f (Split-Path $TargetFile -Leaf), $box.Width, $box.Height, $drawW, $drawH, $x, $y, $kb)
  } finally {
    $src.Dispose()
  }
}

$sourceRoot = (Resolve-Path $Source).Path
foreach ($folder in $SETS.Keys) {
  $key = $SETS[$folder]
  Write-Output "[$key] $folder"
  $scale = Get-SceneScale -StandingFile (Join-Path $sourceRoot "$folder\standing.png")
  foreach ($pose in @('standing', 'sitting')) {
    Write-Sprite -SourceFile (Join-Path $sourceRoot "$folder\$pose.png") -TargetFile (Join-Path $Target "$key\$pose.png") -Mode 'scene' -Scale $scale
  }
  Write-Sprite -SourceFile (Join-Path $sourceRoot "$folder\shop.png") -TargetFile (Join-Path $Target "$key\shop.png") -Mode 'tile'
}
