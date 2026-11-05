param(
    [Parameter(Mandatory = $true)][string]$Docx,
    [Parameter(Mandatory = $true)][string]$Pdf
)

# Convierte DOCX -> PDF con Microsoft Word (COM), sin instalar docx2pdf.
# Ademas actualiza el indice (TOC) y los campos antes de exportar, para que
# el PDF salga con numeros de pagina reales.
$ErrorActionPreference = "Stop"
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0

    $doc = $word.Documents.Open($Docx, $false, $false)
    $doc.Fields.Update() | Out-Null
    if ($doc.TablesOfContents.Count -gt 0) {
        $doc.TablesOfContents.Item(1).Update() | Out-Null
    }
    $doc.Repaginate()
    $doc.Save()
    $doc.SaveAs2($Pdf, 17)   # wdFormatPDF
}
finally {
    if ($doc) { $doc.Close($false) }
    if ($word) { $word.Quit() }
    if ($doc) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) }
    if ($word) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
