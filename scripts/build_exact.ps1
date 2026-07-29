param(
  [ValidateSet("1.26.33")][string]$BdsBuild = "1.26.33",
  [ValidateSet("windows-x64")][string]$Platform = "windows-x64",
  [ValidateRange(1, 4)][int]$Parallel = 2
)
$ErrorActionPreference = "Stop"
python scripts/build_exact.py --bds $BdsBuild --platform $Platform --parallel $Parallel
if ($LASTEXITCODE -ne 0) { throw "Exact Sign API build failed with exit code $LASTEXITCODE" }
