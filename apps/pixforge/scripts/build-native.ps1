param(
    [string]$OutputDirectory,
    [string]$BuildDirectory,
    [switch]$DebugBuild,
    [string]$PythonExecutable
)
$ErrorActionPreference = 'Stop'
$applicationRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $PythonExecutable) { $PythonExecutable = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $applicationRoot '.runtime\native\bin' }
if (-not $BuildDirectory) { $BuildDirectory = Join-Path $applicationRoot '.runtime\native\build' }
$outputPath = [IO.Path]::GetFullPath($OutputDirectory)
$buildPath = [IO.Path]::GetFullPath($BuildDirectory)
New-Item -ItemType Directory -Force -Path $outputPath, $buildPath | Out-Null
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$installation = $null
if (Test-Path -LiteralPath $vswhere) {
    $installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
}
if (-not $installation) { throw 'Install Visual Studio Build Tools with C++ desktop support, then run build-native.ps1 again.' }
$vcvars = Join-Path $installation 'VC\Auxiliary\Build\vcvars64.bat'
$source = Join-Path $PSScriptRoot 'native'
$modeFlags = if ($DebugBuild) { '/Od /Zi /MTd' } else { '/O2 /MT /DNDEBUG' }
$executable = Join-Path $outputPath 'PixForgeNative.exe'
$command = @"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
rc.exe /nologo /I "$source" /fo "$buildPath\app.res" "$source\app.rc"
if errorlevel 1 exit /b 1
cl.exe /nologo /std:c++20 /EHsc /W4 /utf-8 /permissive- $modeFlags /DUNICODE /D_UNICODE /D_WIN32_WINNT=0x0A00 /DWINVER=0x0A00 /Fo"$buildPath\\" /Fe"$executable" "$source\main.cpp" "$source\app.cpp" "$source\app_scene.cpp" "$source\scene_editor.cpp" "$source\minecraft_editor.cpp" "$source\minecraft_preview.cpp" "$source\minecraft_workbench.cpp" "$source\material_editor.cpp" "$buildPath\app.res" /link /SUBSYSTEM:WINDOWS /DYNAMICBASE /NXCOMPAT /MANIFEST:EMBED /MANIFESTINPUT:"$source\native.manifest"
exit /b %errorlevel%
"@
$commandPath = Join-Path $buildPath 'compile-native.cmd'
[IO.File]::WriteAllText($commandPath, $command.Replace("`r`n", "`n").Replace("`n", "`r`n"), [Text.UTF8Encoding]::new($false))
& $env:ComSpec /d /c $commandPath
if ($LASTEXITCODE -ne 0) { throw "Native C++ build failed ($LASTEXITCODE)." }
$development = @{schema='pixforge.development-install/v1'; python=[IO.Path]::GetFullPath($PythonExecutable); entry=(Join-Path $PSScriptRoot 'app_entry.py'); workspace=(Join-Path (Split-Path -Parent $PSScriptRoot) 'workspace')}
[IO.File]::WriteAllText((Join-Path $outputPath 'pixforge-development.json'), (($development | ConvertTo-Json) + "`n").Replace("`r`n", "`n"), [Text.UTF8Encoding]::new($false))
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\public-api.json') -Destination (Join-Path $outputPath 'application.json') -Force
Write-Output $executable
