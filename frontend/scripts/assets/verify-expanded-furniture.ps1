<#
.SYNOPSIS
  Verify staged expanded furniture sprites against their sources and pre-change PNGs.
.DESCRIPTION
  Read-only for source/app assets. Writes the JSON verification report and contact
  sheets to ReportTarget. Before must contain the previous key/{left,right,shop}.png.
  For the optional LegacyGitRef check, Legacy must contain an ordinary
  (no geometry options) reference-source build.
#>
param(
  [Parameter(Mandatory = $true)][string]$Source,
  [Parameter(Mandatory = $true)][string]$ReferenceSource,
  [Parameter(Mandatory = $true)][string]$Sprites,
  [Parameter(Mandatory = $true)][string]$Before,
  [string]$Legacy,
  [Parameter(Mandatory = $true)][string]$Geometry,
  [Parameter(Mandatory = $true)][string]$ReportTarget,
  # Pin the pre-expansion commit when checking the legacy generator's PNG bytes.
  # Omit for reruns after the expanded assets have been committed.
  [string]$LegacyGitRef,
  [double]$SceneScale = (2.0 / 3),
  [int]$ShopSize = 256,
  [int]$Padding = 2,
  [int]$AlphaFloor = 8
)
$ErrorActionPreference = 'Stop'
if ($LegacyGitRef -and -not $Legacy) { throw 'Legacy is required when LegacyGitRef is specified.' }
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public class ExpandedSpriteReport {
  public int Width, Height, OriginalWidth, OriginalHeight, OffsetX, OffsetY;
  public int TransparentBorder, ChangedOriginalPixels, OpaqueRgbChanged, MaxOpaqueRgbDelta;
  public int InteriorRgbChanged, MaxInteriorRgbDelta, AddedVisiblePixels;
  public string PixelFormat;
}
public class SourceCoverageReport {
  public double Left, Top, Right, Bottom, ScaleX, ScaleY, MinimumCanvasMargin;
  public int OriginalCropX, OriginalCropY, OriginalCropWidth, OriginalCropHeight;
  public bool EntireSourceAlphaBoundsContained;
}
public static class ExpandedFurnitureQA {
  static byte[] Pixels(Bitmap image) {
    var data = image.LockBits(new Rectangle(0,0,image.Width,image.Height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
    try { var bytes = new byte[data.Stride * image.Height]; Marshal.Copy(data.Scan0, bytes, 0, bytes.Length); return bytes; }
    finally { image.UnlockBits(data); }
  }
  static Rectangle Bounds(Bitmap image, int alphaFloor) {
    var pixels = Pixels(image);
    int xMin=image.Width, yMin=image.Height, xMax=-1, yMax=-1;
    for(int y=0;y<image.Height;y++) for(int x=0;x<image.Width;x++) {
      if(pixels[(y*image.Width+x)*4+3]<=alphaFloor) continue;
      xMin=Math.Min(xMin,x); yMin=Math.Min(yMin,y); xMax=Math.Max(xMax,x); yMax=Math.Max(yMax,y);
    }
    if(xMax<0) throw new Exception("Empty source");
    return new Rectangle(xMin,yMin,xMax-xMin+1,yMax-yMin+1);
  }
  public static SourceCoverageReport CheckCoverage(string referencePath, string sourcePath, bool shop, double sceneScale, int shopSize, int padding, int alphaFloor, int[] geometry) {
    using(var reference=new Bitmap(referencePath)) using(var source=new Bitmap(sourcePath)) {
      var crop=Bounds(reference,alphaFloor);
      if(!shop) {
        int x=Math.Max(0,crop.X-padding), y=Math.Max(0,crop.Y-padding);
        crop=new Rectangle(x,y,Math.Min(reference.Width,crop.Right+padding)-x,Math.Min(reference.Height,crop.Bottom+padding)-y);
      }
      double ratio=shop ? (double)shopSize/Math.Max(crop.Width,crop.Height) : sceneScale;
      int oldWidth=Math.Max(1,(int)Math.Round(crop.Width*ratio)), oldHeight=Math.Max(1,(int)Math.Round(crop.Height*ratio));
      if(oldWidth!=geometry[4] || oldHeight!=geometry[5]) throw new Exception("Legacy scale changed: " + sourcePath);
      var bounds=Bounds(source,0);
      double sx=(double)oldWidth/crop.Width, sy=(double)oldHeight/crop.Height;
      var r=new SourceCoverageReport {
        Left=geometry[2]+(bounds.Left-crop.Left)*sx, Top=geometry[3]+(bounds.Top-crop.Top)*sy,
        Right=geometry[2]+(bounds.Right-crop.Left)*sx, Bottom=geometry[3]+(bounds.Bottom-crop.Top)*sy,
        ScaleX=sx, ScaleY=sy, OriginalCropX=crop.X, OriginalCropY=crop.Y, OriginalCropWidth=crop.Width, OriginalCropHeight=crop.Height
      };
      r.MinimumCanvasMargin=Math.Min(Math.Min(r.Left,r.Top),Math.Min(geometry[0]-r.Right,geometry[1]-r.Bottom));
      // Source bounds use pixel edges, independently of the resampler's alpha
      // quantization. Only floating-point arithmetic tolerance is permitted.
      r.EntireSourceAlphaBoundsContained=r.MinimumCanvasMargin>=-1e-9;
      if(!r.EntireSourceAlphaBoundsContained) throw new Exception("Source shadow extent is clipped: " + sourcePath);
      return r;
    }
  }
  public static int CompareSource(string referencePath, string sourcePath) {
    using (var reference = new Bitmap(referencePath)) using (var source = new Bitmap(sourcePath)) {
      if (reference.Size != source.Size) throw new Exception("Source canvas changed: " + sourcePath);
      var a = Pixels(reference); var b = Pixels(source); int changedShadow = 0;
      for (int i=0; i<a.Length; i+=4) {
        if (b[i+3] < a[i+3]) throw new Exception("Source alpha reduced: " + sourcePath);
        if (a[i+3] == 255) for(int c=0;c<4;c++) if(a[i+c] != b[i+c]) throw new Exception("Source opaque body changed: " + sourcePath);
        if (b[i+3] > a[i+3]) changedShadow++;
      }
      if (changedShadow == 0) throw new Exception("Source has no new shadow: " + sourcePath);
      return changedShadow;
    }
  }
  public static ExpandedSpriteReport Compare(string beforePath, string expandedPath, int xOffset, int yOffset, int width, int height, int contentWidth, int contentHeight) {
    using (var before = new Bitmap(beforePath)) using (var expanded = new Bitmap(expandedPath)) {
      if (before.Width != contentWidth || before.Height != contentHeight || expanded.Width != width || expanded.Height != height)
        throw new Exception("Geometry/PNG size mismatch: " + expandedPath);
      if (expanded.PixelFormat != PixelFormat.Format32bppArgb) throw new Exception("Expected RGBA: " + expandedPath);
      if (xOffset < 0 || yOffset < 0 || xOffset + contentWidth > width || yOffset + contentHeight > height)
        throw new Exception("Original canvas is clipped: " + expandedPath);
      var r = new ExpandedSpriteReport { Width=width, Height=height, OriginalWidth=contentWidth, OriginalHeight=contentHeight, OffsetX=xOffset, OffsetY=yOffset, PixelFormat=expanded.PixelFormat.ToString(), TransparentBorder=Math.Min(width,height) };
      var a = Pixels(before); var b = Pixels(expanded);
      for(int y=0;y<height;y++) for(int x=0;x<width;x++) {
        int offset=(y*width+x)*4;
        if(b[offset+3] == 0) continue;
        r.TransparentBorder=Math.Min(r.TransparentBorder, Math.Min(Math.Min(x,width-1-x),Math.Min(y,height-1-y)));
        if(x<xOffset || x>=xOffset+contentWidth || y<yOffset || y>=yOffset+contentHeight) r.AddedVisiblePixels++;
      }
      for(int y=0;y<contentHeight;y++) for(int x=0;x<contentWidth;x++) {
        int ai=(y*contentWidth+x)*4, bi=((y+yOffset)*width+x+xOffset)*4;
        bool changed=false; int rgbDelta=0;
        for(int c=0;c<4;c++) { if(a[ai+c]!=b[bi+c]) changed=true; if(c<3) rgbDelta=Math.Max(rgbDelta,Math.Abs((int)a[ai+c]-b[bi+c])); }
        if(changed) r.ChangedOriginalPixels++;
        if(a[ai+3] != 255) continue;
        if(rgbDelta>0) r.OpaqueRgbChanged++;
        r.MaxOpaqueRgbDelta=Math.Max(r.MaxOpaqueRgbDelta,rgbDelta);
        bool interior=x>=3 && y>=3 && x<contentWidth-3 && y<contentHeight-3;
        if(interior) for(int dy=-3;dy<=3;dy++) for(int dx=-3;dx<=3;dx++) if(a[((y+dy)*contentWidth+x+dx)*4+3]!=255) interior=false;
        if(interior) { if(rgbDelta>0) r.InteriorRgbChanged++; r.MaxInteriorRgbDelta=Math.Max(r.MaxInteriorRgbDelta,rgbDelta); }
      }
      if(r.TransparentBorder<2) throw new Exception("Shadow lacks two transparent pixels: " + expandedPath);
      if(r.AddedVisiblePixels==0) throw new Exception("No recovered shadow beyond original canvas: " + expandedPath);
      if(r.ChangedOriginalPixels!=0) throw new Exception("Original canvas pixels changed: " + expandedPath);
      return r;
    }
  }
}
'@

$keys = @(Get-ChildItem -LiteralPath $Source -Filter '*__left_wall.png' | ForEach-Object { $_.Name -replace '__left_wall\.png$', '' } | Sort-Object)
$geometryText = Get-Content -LiteralPath $Geometry -Raw
$geometryByKey = @{}
foreach ($key in $keys) {
  $entry = [regex]::Match($geometryText, "(?s)  $($key): \{(.*?)\r?\n  \},").Groups[1].Value
  if (-not $entry) { throw "Missing geometry: $key" }
  $geometryByKey[$key] = @{}
  foreach ($view in @('left','right','shop')) {
    $m = [regex]::Match($entry, "$($view): \{ pixelSize: \{ width: (\d+), height: (\d+) \}, contentRect: \{ x: (\d+), y: (\d+), width: (\d+), height: (\d+) \}")
    if (-not $m.Success) { throw "Invalid geometry: $key/$view" }
    $geometryByKey[$key][$view] = [int[]]@(1..6 | ForEach-Object { $m.Groups[$_].Value })
  }
}
$sourceResults = @(
  foreach ($key in $keys) {
    foreach ($direction in @('left_wall','right_wall')) {
      $file = "${key}__${direction}.png"
      $changed = [ExpandedFurnitureQA]::CompareSource((Join-Path $ReferenceSource $file), (Join-Path $Source $file))
      [pscustomobject]@{File=$file; OpaqueBodyUnchanged=$true; AdditionalShadowPixels=$changed}
    }
  }
)
$spriteResults = @(
  foreach ($key in $keys) {
    foreach ($view in @('left','right','shop')) {
      $file = "$key/$view.png"
      $v = $geometryByKey[$key][$view]
      $pixels = [ExpandedFurnitureQA]::Compare((Join-Path $Before $file), (Join-Path $Sprites $file), $v[2], $v[3], $v[0], $v[1], $v[4], $v[5])
      $sourceView = if ($view -eq 'right') { 'right_wall' } else { 'left_wall' }
      $sourceFile = "${key}__${sourceView}.png"
      $coverage = [ExpandedFurnitureQA]::CheckCoverage((Join-Path $ReferenceSource $sourceFile), (Join-Path $Source $sourceFile), ($view -eq 'shop'), $SceneScale, $ShopSize, $Padding, $AlphaFloor, $v)
      $legacyMatches = $null
      if ($LegacyGitRef) {
        $baselineHash = git hash-object (Join-Path $Legacy $file)
        if ($LASTEXITCODE -ne 0) { throw "Failed to hash legacy sprite: $file" }
        $trackedHash = git rev-parse "$($LegacyGitRef):frontend/assets/sprites/furniture/$file"
        if ($LASTEXITCODE -ne 0 -or $trackedHash -ne $baselineHash) { throw "Legacy generator does not reproduce tracked PNG: $file" }
        $legacyMatches = $true
      }
      [pscustomobject]@{File=$file; LegacyMatchesTrackedOriginal=$legacyMatches; Pixels=$pixels; SourceCoverage=$coverage}
    }
  }
)
$actual = @(Get-ChildItem -LiteralPath $Sprites -Filter '*.png' -Recurse)
if ($actual.Count -ne $spriteResults.Count) { throw 'Unexpected sprite count' }
$summary = [pscustomobject]@{
  Passed=$true; FurnitureCount=$keys.Count; SourcePngCount=$sourceResults.Count; AppPngCount=$spriteResults.Count
  LegacyGitRef=$LegacyGitRef
  LegacyModeExactReproductionCount=@($spriteResults | Where-Object { $_.LegacyMatchesTrackedOriginal -eq $true }).Count
  OpaqueSourceBodyUnchanged=$true; TransparentBorderAtLeast=2
  EntireSourceAlphaBoundsContainedCount=@($spriteResults | Where-Object { $_.SourceCoverage.EntireSourceAlphaBoundsContained }).Count
  MinimumSourceAlphaCanvasMargin=($spriteResults.SourceCoverage.MinimumCanvasMargin | Measure-Object -Minimum).Minimum
  MaxBodyInteriorRgbDelta=($spriteResults.Pixels.MaxInteriorRgbDelta | Measure-Object -Maximum).Maximum
  MaxOpaqueRgbDelta=($spriteResults.Pixels.MaxOpaqueRgbDelta | Measure-Object -Maximum).Maximum
  IdenticalOriginalRegionCount=@($spriteResults | Where-Object { $_.Pixels.ChangedOriginalPixels -eq 0 }).Count
  RecoveredShadowPixels=($spriteResults.Pixels.AddedVisiblePixels | Measure-Object -Sum).Sum
}
New-Item -ItemType Directory -Force -Path $ReportTarget | Out-Null
[pscustomobject]@{Summary=$summary; Sources=$sourceResults; Sprites=$spriteResults} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $ReportTarget 'verification.json') -Encoding UTF8
$summary | ConvertTo-Json

# All 36 furniture/color combinations, left/right and shop, at preserved scale.
$kinds = @('sofa','dining_table','desk','dining_chair','coffee_table','bed','nightstand','bookcase','tv_set')
$editions = @('original','black','pink','sunset')
$font = New-Object System.Drawing.Font 'Segoe UI', 13
$heading = New-Object System.Drawing.Font 'Segoe UI', 21, ([System.Drawing.FontStyle]::Bold)
$ink = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml('#303943'))
$oldBox = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(130, 195, 89, 63)), 1
try {
  for ($page=0; $page -lt 3; $page++) {
    $sheet = New-Object System.Drawing.Bitmap 1440, 1540
    $g = [System.Drawing.Graphics]::FromImage($sheet)
    try {
      $g.Clear([System.Drawing.ColorTranslator]::FromHtml('#eee9e0'))
      $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
      $g.DrawString("Expanded shadow v4 / $($page+1) / box = previous PNG", $heading, $ink, 24, 15)
      for ($row=0; $row -lt 3; $row++) {
        for ($col=0; $col -lt 4; $col++) {
          $key = "$($kinds[$page*3+$row])_$($editions[$col])"
          $left = 15 + $col * 360; $top = 74 + $row * 485
          $g.DrawString($key, $font, $ink, $left, $top)
          $ix = 0
          foreach ($view in @('left','right','shop')) {
            $img = [System.Drawing.Bitmap]::FromFile((Join-Path $Sprites "$key/$view.png"))
            try {
              $v = $geometryByKey[$key][$view]
              if ($view -eq 'shop') { $scale = [Math]::Min(88.0/$v[4], 88.0/$v[5]); $imageX=$left+128-$v[2]*$scale; $imageY=$top+348-$v[3]*$scale }
              else { $scale = [Math]::Min(162.0/$v[0], 258.0/$v[1]); $imageX=$left+($ix*176); $imageY=$top+48 }
              $g.DrawImage($img, [single]$imageX, [single]$imageY, [single]($v[0]*$scale), [single]($v[1]*$scale))
              $g.DrawRectangle($oldBox, [single]($imageX+$v[2]*$scale), [single]($imageY+$v[3]*$scale), [single]($v[4]*$scale), [single]($v[5]*$scale))
              $g.DrawString($view, $font, $ink, [single]$imageX, [single]($imageY+$v[1]*$scale+5))
              $ix++
            } finally { $img.Dispose() }
          }
        }
      }
      $sheet.Save((Join-Path $ReportTarget "qa-$($page+1).png"), [System.Drawing.Imaging.ImageFormat]::Png)
    } finally { $g.Dispose(); $sheet.Dispose() }
  }
} finally { $font.Dispose(); $heading.Dispose(); $ink.Dispose(); $oldBox.Dispose() }
