<#
.SYNOPSIS
  흰 배경 위에 생성된 가구·캐릭터 이미지(JPEG/PNG)를 투명 PNG 로 만든다.

.DESCRIPTION
  1) 이미지 네 모서리에서 시작해 "거의 흰색" 픽셀만 flood-fill 로 지운다(바깥 배경만 제거, 물체 안의 흰색은 유지).
  2) 제거 경계의 안티에일리어싱 픽셀은 밝기에 따라 반투명으로 만든다(흰 테두리 방지).
  3) 남은 내용의 bbox 로 자르고, 발끝(가장 아래 픽셀)이 이미지 하단에 오도록 여백을 둔다.
     → features/room 의 기준점(가로 중앙, 세로 95%)과 맞는다.
  Windows PowerShell 5.1 + .NET System.Drawing 전용. 에셋 제작용 로컬 도구이며 앱 빌드와 무관하다.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/assets/remove-white-bg.ps1 -Source images/generated-1.png -Target assets/sprites/furniture/sofa.png
  powershell -File scripts/assets/remove-white-bg.ps1 -Source in.jpg -Target out.png -Tolerance 12 -Padding 8
#>
param(
  # $Input 은 PowerShell 자동 변수라 쓰지 않는다
  [Parameter(Mandatory = $true)][string]$Source,
  [Parameter(Mandatory = $true)][string]$Target,
  # 배경(키) 색. 기본 흰색. 크림색 물체처럼 흰 배경과 구분이 안 되면 마젠타(#FF00FF) 배경으로 생성해 지정한다.
  [string]$KeyColor = "#FFFFFF",
  # (흰색 키) 키 색과의 채널 차이가 이 값 이내면 배경으로 본다. 물체가 지워지면 줄인다.
  [int]$Tolerance = 10,
  # (유채색 키) 색조 치우침(keyness)이 이 값 이상이면 배경. 순수 마젠타 ≈ 208. 물체가 지워지면 올린다.
  [int]$KeyThreshold = 90,
  # (유채색 키) 남은 픽셀의 키 색조 성분 제거 강도 0~1. 보라·핑크 물체가 있으면 낮춘다.
  [double]$Spill = 1.0,
  # (유채색 키) 이 값 이하의 약한 키 색조는 물체 고유색으로 보고 중화하지 않는다
  [int]$SpillMin = 30,
  # (유채색 키) 배경 그림자를 검은 반투명으로 되살리지 않음
  [switch]$NoShadow,
  # bbox 바깥 여백(px). 발끝은 아래 여백 안에 들어간다.
  [int]$Padding = 6,
  # 자르지 않고 배경만 제거하려면 지정
  [switch]$NoCrop
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$csharp = @"
using System;
using System.Collections.Generic;
public static class WhiteBg {
  // pixels: BGRA 배열. 반환: 알파가 적용된 새 배열. key*: 배경 색, tol: 채널 차이 허용치
  public static byte[] Remove(byte[] px, int w, int h, int keyR, int keyG, int keyB, int tol) {
    bool[] bg = new bool[w * h];
    var stack = new Stack<int>();
    Action<int> push = (i) => { if (!bg[i] && Dist(px, i, keyR, keyG, keyB) <= tol) { bg[i] = true; stack.Push(i); } };
    for (int x = 0; x < w; x++) { push(x); push((h - 1) * w + x); }
    for (int y = 0; y < h; y++) { push(y * w); push(y * w + (w - 1)); }
    while (stack.Count > 0) {
      int i = stack.Pop(); int x = i % w; int y = i / w;
      if (x > 0) push(i - 1); if (x < w - 1) push(i + 1);
      if (y > 0) push(i - w); if (y < h - 1) push(i + w);
    }
    byte[] outPx = (byte[])px.Clone();
    for (int i = 0; i < w * h; i++) {
      int o = i * 4;
      if (bg[i]) { outPx[o] = 0; outPx[o + 1] = 0; outPx[o + 2] = 0; outPx[o + 3] = 0; continue; }
      // 배경과 맞닿은 경계 픽셀: 배경 색에 가까울수록 투명하게 (안티에일리어싱 처리)
      int x = i % w; int y = i / w;
      bool edge = (x > 0 && bg[i - 1]) || (x < w - 1 && bg[i + 1]) || (y > 0 && bg[i - w]) || (y < h - 1 && bg[i + w]);
      if (edge) {
        int d = Dist(px, i, keyR, keyG, keyB);
        int alpha = Math.Min(255, d * 255 / Math.Max(1, tol * 2));
        outPx[o + 3] = (byte)alpha;
      }
    }
    return outPx;
  }
  // 키 색과의 최대 채널 차이 (px 는 BGRA)
  static int Dist(byte[] px, int i, int keyR, int keyG, int keyB) {
    int o = i * 4;
    return Math.Max(Math.Abs(px[o + 2] - keyR), Math.Max(Math.Abs(px[o + 1] - keyG), Math.Abs(px[o] - keyB)));
  }

  // 유채색 키(마젠타 등) 전용 크로마키.
  // keyness = 픽셀 색조가 키 색조 방향으로 얼마나 치우쳤는지(회색·흰색 = 0, 순수 키 색 ≈ 최대).
  // 밝기가 달라도(그림자) keyness 는 유지되므로 그림자도 배경으로 잡힌다. keepShadow 면 그림자를 검은 반투명으로 되살린다.
  // spill: 남은 픽셀에서 키 색조 성분을 빼 반사 물듦을 중화한다(1 = 전부 제거).
  public static byte[] RemoveChroma(byte[] px, int w, int h, int keyR, int keyG, int keyB, int threshold, double spill, int spillMin, bool keepShadow) {
    double km = (keyR + keyG + keyB) / 3.0;
    double kr = keyR - km, kg = keyG - km, kb = keyB - km;
    double kl = Math.Sqrt(kr * kr + kg * kg + kb * kb); kr /= kl; kg /= kl; kb /= kl;
    double keyLum = 0.299 * keyR + 0.587 * keyG + 0.114 * keyB;
    int n = w * h;
    double[] keyness = new double[n];
    for (int i = 0; i < n; i++) {
      int o = i * 4; double r = px[o + 2], g = px[o + 1], b = px[o]; double m = (r + g + b) / 3.0;
      keyness[i] = (r - m) * kr + (g - m) * kg + (b - m) * kb;
    }
    // 키 색은 물체에 쓰이지 않는다고 보고, 연결 여부와 무관하게(가구 다리 사이 막힌 구멍 포함) 전부 배경으로 잡는다
    bool[] bg = new bool[n];
    for (int i = 0; i < n; i++) bg[i] = keyness[i] >= threshold;
    byte[] outPx = (byte[])px.Clone();
    for (int i = 0; i < n; i++) {
      int o = i * 4;
      if (bg[i]) {
        double lum = 0.299 * px[o + 2] + 0.587 * px[o + 1] + 0.114 * px[o];
        double ratio = keepShadow ? (keyLum - lum) / keyLum : 0;
        outPx[o] = 0; outPx[o + 1] = 0; outPx[o + 2] = 0;
        outPx[o + 3] = (byte)(ratio > 0.08 ? Math.Min(255, (int)(ratio * 255 * 1.3)) : 0);
        continue;
      }
      int x = i % w; int y = i / w;
      bool edge = (x > 0 && bg[i - 1]) || (x < w - 1 && bg[i + 1]) || (y > 0 && bg[i - w]) || (y < h - 1 && bg[i + w]);
      double k = keyness[i];
      if (edge && k > threshold / 2.0) {
        outPx[o + 3] = (byte)Math.Max(0, Math.Min(255, (int)(255 * (threshold - k) / (threshold / 2.0))));
      }
      // 스필 중화: 약한 색조(테라코타 같은 물체 고유색)는 두고 spillMin 을 넘는 강한 키 색조만 뺀다
      if (spill > 0 && k > spillMin) {
        double d = (k - spillMin) * spill;
        outPx[o + 2] = (byte)Math.Max(0, Math.Min(255, px[o + 2] - d * kr));
        outPx[o + 1] = (byte)Math.Max(0, Math.Min(255, px[o + 1] - d * kg));
        outPx[o]     = (byte)Math.Max(0, Math.Min(255, px[o]     - d * kb));
      }
    }
    return outPx;
  }
  // 알파가 있는 픽셀의 bbox: [minX, minY, maxX, maxY], 없으면 null
  public static int[] Bounds(byte[] px, int w, int h) {
    int minX = w, minY = h, maxX = -1, maxY = -1;
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
      if (px[(y * w + x) * 4 + 3] > 8) { if (x < minX) minX = x; if (x > maxX) maxX = x; if (y < minY) minY = y; if (y > maxY) maxY = y; }
    }
    return maxX < 0 ? null : new int[] { minX, minY, maxX, maxY };
  }
}
"@
if (-not ("WhiteBg" -as [type])) { Add-Type -TypeDefinition $csharp }

$inPath = (Resolve-Path $Source).Path
$src = [System.Drawing.Bitmap]::FromFile($inPath)
try {
  $w = $src.Width; $h = $src.Height
  $bmp = New-Object System.Drawing.Bitmap $w, $h, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp); $g.DrawImage($src, 0, 0, $w, $h); $g.Dispose()

  $rect = New-Object System.Drawing.Rectangle 0, 0, $w, $h
  $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadWrite, $bmp.PixelFormat)
  $bytes = New-Object byte[] ($data.Stride * $h)
  [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
  $key = [System.Drawing.ColorTranslator]::FromHtml($KeyColor)
  $chroma = ([Math]::Max([int]$key.R, [Math]::Max([int]$key.G, [int]$key.B)) - [Math]::Min([int]$key.R, [Math]::Min([int]$key.G, [int]$key.B))) -gt 60
  if ($chroma) {
    # 유채색 키: 색조 기반 크로마키 + 그림자 복원 + 스필 중화
    $result = [WhiteBg]::RemoveChroma($bytes, $w, $h, [int]$key.R, [int]$key.G, [int]$key.B, $KeyThreshold, $Spill, $SpillMin, (-not $NoShadow))
  } else {
    $result = [WhiteBg]::Remove($bytes, $w, $h, [int]$key.R, [int]$key.G, [int]$key.B, $Tolerance)
  }
  [System.Runtime.InteropServices.Marshal]::Copy($result, 0, $data.Scan0, $result.Length)
  $bmp.UnlockBits($data)

  $outBmp = $bmp
  if (-not $NoCrop) {
    $b = [WhiteBg]::Bounds($result, $w, $h)
    if ($null -eq $b) { throw "내용이 없는 이미지입니다: $Source" }
    $x0 = [Math]::Max(0, $b[0] - $Padding); $y0 = [Math]::Max(0, $b[1] - $Padding)
    $x1 = [Math]::Min($w - 1, $b[2] + $Padding); $y1 = [Math]::Min($h - 1, $b[3] + $Padding)
    $crop = New-Object System.Drawing.Rectangle $x0, $y0, ($x1 - $x0 + 1), ($y1 - $y0 + 1)
    $outBmp = $bmp.Clone($crop, $bmp.PixelFormat)
  }

  $outDir = Split-Path -Parent $Target
  if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Force $outDir | Out-Null }
  $outBmp.Save($Target, [System.Drawing.Imaging.ImageFormat]::Png)
  Write-Output ("{0} -> {1} ({2}x{3})" -f (Split-Path -Leaf $Source), $Target, $outBmp.Width, $outBmp.Height)
  if ($outBmp -ne $bmp) { $outBmp.Dispose() }
  $bmp.Dispose()
} finally {
  $src.Dispose()
}
