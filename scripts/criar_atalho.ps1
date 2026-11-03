param(
    [Parameter(Mandatory = $true)]
    [string]$PythonwPath,

    [ValidatePattern('^(?i)(ALT\+[A-Z0-9]|CTRL\+ALT\+[A-Z0-9])$')]
    [string]$Hotkey = 'ALT+C'
)

$ErrorActionPreference = 'Stop'

$pythonw = (Resolve-Path -LiteralPath $PythonwPath).Path
if ([System.IO.Path]::GetFileName($pythonw) -ine 'pythonw.exe') {
    throw 'Informe o caminho para pythonw.exe para executar sem console.'
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$entryPoint = Join-Path $projectRoot 'src\main.py'
if (-not (Test-Path -LiteralPath $entryPoint -PathType Leaf)) {
    throw "Ponto de entrada inexistente: $entryPoint"
}

# O atalho fica no menu Iniciar do usuário, sem iniciar com o Windows.
$programs = [Environment]::GetFolderPath('Programs')
if (-not $programs -or -not (Test-Path -LiteralPath $programs -PathType Container)) {
    throw 'Não foi possível localizar o menu Iniciar do usuário.'
}
$shortcutPath = Join-Path $programs 'Gerenciador de Scripts.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    throw "Já existe um atalho em $shortcutPath. Remova-o ou ajuste-o manualmente."
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '"' + $entryPoint + '"'
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Abrir o Gerenciador de Scripts sob demanda'
$shortcut.Hotkey = $Hotkey
$shortcut.WindowStyle = 1
$shortcut.Save()

Write-Output "Atalho criado: $shortcutPath"
Write-Output "Combinação: $Hotkey"
