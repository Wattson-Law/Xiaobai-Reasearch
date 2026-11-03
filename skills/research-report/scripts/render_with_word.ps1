param(
    [Parameter(Mandatory = $true)]
    [string]$InputDocx,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [int]$Dpi = 144
)

$ErrorActionPreference = 'Stop'
$resolvedInput = (Resolve-Path -LiteralPath $InputDocx).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("docx_rnd_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
$stagingDocx = Join-Path $tempDir "report.docx"
$stagingPdf = Join-Path $tempDir "document.pdf"
Copy-Item -LiteralPath $resolvedInput -Destination $stagingDocx -Force

$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($stagingDocx, $false, $true)
    $doc.ExportAsFixedFormat($stagingPdf, 17)
    $doc.Close(0)
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc)
    $doc = $null

    $word.Quit() | Out-Null
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    $word = $null
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()

    $pdfPath = Join-Path $outputPath 'document.pdf'
    Copy-Item -LiteralPath $stagingPdf -Destination $pdfPath -Force

    $pdftoppm = Get-Command pdftoppm -ErrorAction SilentlyContinue
    if ($pdftoppm) {
        & $pdftoppm.Source -png -r $Dpi $stagingPdf (Join-Path $tempDir 'page')
        Get-ChildItem -LiteralPath $tempDir -Filter 'page-*.png' | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $outputPath $_.Name) -Force
        }
    }
    else {
        $py = Get-Command python -ErrorAction SilentlyContinue
        if ($py) {
            $pyScript = @"
import sys
from pathlib import Path
try:
    import pymupdf as fitz
except ImportError:
    import fitz
doc = fitz.open(sys.argv[1])
out_dir = Path(sys.argv[2])
dpi = int(sys.argv[3])
for idx, page in enumerate(doc, 1):
    page.get_pixmap(dpi=dpi).save(str(out_dir / f"page-{idx:02d}.png"))
"@
            $pyFile = Join-Path $tempDir "render_pdf.py"
            Set-Content -LiteralPath $pyFile -Value $pyScript -Encoding UTF8
            try {
                & $py.Source $pyFile $stagingPdf $outputPath $Dpi 2>$null
            }
            catch {
                Write-Warning "Word 已生成 PDF ($pdfPath)，但未检测到 pdftoppm 或 PyMuPDF，跳过 PNG 转换。"
            }
        }
        else {
            Write-Warning "Word 已生成 PDF ($pdfPath)，但未找到 pdftoppm，跳过 PNG 转换。"
        }
    }

    Get-ChildItem -LiteralPath $outputPath -Filter 'page-*.png' |
        Sort-Object Name |
        Select-Object FullName, Length
}
finally {
    if ($null -ne $doc) {
        try { $doc.Close(0) } catch {}
        try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) } catch {}
    }
    if ($null -ne $word) {
        try { $word.Quit() | Out-Null } catch {}
        try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) } catch {}
    }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
    Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
}
