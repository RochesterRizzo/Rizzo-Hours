$ErrorActionPreference = "Stop"

$repoPath = Join-Path $env:USERPROFILE "Documents\GitHub\Rizzo-Hours"
$filePath = Join-Path $repoPath "econ-dept.html"

if (!(Test-Path $filePath)) {
  Write-Host "Could not find econ-dept.html at: $filePath" -ForegroundColor Red
  Write-Host "Move this script into your Rizzo-Hours folder and run it again, or edit the path at the top of the script." -ForegroundColor Yellow
  exit 1
}

$html = Get-Content -Path $filePath -Raw -Encoding UTF8

if ($html -match 'Switching from an existing economics major') {
  Write-Host "The switching-major note is already present. No changes made." -ForegroundColor Yellow
  exit 0
}

$note = @'

        <div class="plain-card" style="margin-top:16px; border-left:10px solid var(--orange);">
          <h3>Switching from an existing economics major?</h3>
          <p>If you are already declared in an economics major and want to move into one of the new majors, please first use the College’s <a href="https://secure1.rochester.edu/ccas/rc-change-form.php">change form</a> to drop your existing major.</p>
          <p>After talking the new program over with Professor Rizzo, use the regular <a href="https://secure1.rochester.edu/registrar/applications/major-minor-declaration.php">major declaration form</a> to declare the new program.</p>
        </div>
'@

$markerTitle = '<h3>Notes on transition rules</h3>'
$titleIndex = $html.IndexOf($markerTitle)
if ($titleIndex -lt 0) {
  Write-Host "Could not find the 'Notes on transition rules' section. No changes made." -ForegroundColor Red
  exit 1
}

$afterTitle = $html.Substring($titleIndex)
$pattern = '(?s)(<div class="plain-card" style="margin-top:16px;">\s*<h3>Notes on transition rules</h3>.*?</div>)(\s*</section>\s*<section id="course-options">)'
$match = [regex]::Match($afterTitle, $pattern)

if (!$match.Success) {
  Write-Host "Could not safely locate the insertion point. No changes made." -ForegroundColor Red
  exit 1
}

$prefix = $html.Substring(0, $titleIndex)
$patchedAfterTitle = [regex]::Replace($afterTitle, $pattern, ('$1' + $note + '$2'), 1)
$patched = $prefix + $patchedAfterTitle

$backupPath = "$filePath.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
Copy-Item -Path $filePath -Destination $backupPath
Set-Content -Path $filePath -Value $patched -Encoding UTF8

Write-Host "Updated econ-dept.html successfully." -ForegroundColor Green
Write-Host "Backup saved at: $backupPath"
Write-Host "Next: open GitHub Desktop, review the one changed file, Commit to main, then Push origin."
