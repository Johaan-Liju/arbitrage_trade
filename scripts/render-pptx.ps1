param([string]$Pptx, [string]$OutDir)
$app = New-Object -ComObject PowerPoint.Application
try {
  $pres = $app.Presentations.Open((Resolve-Path $Pptx).Path, $true, $false, $false)
  New-Item -ItemType Directory -Force $OutDir | Out-Null
  $pres.Export((Resolve-Path $OutDir).Path, "PNG", 1280, 720)
  $pres.Close()
} finally { $app.Quit() }
