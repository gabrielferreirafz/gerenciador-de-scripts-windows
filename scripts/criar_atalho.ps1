param(
    [Parameter(Mandatory = $true)]
    [string]$PythonwPath,

    [switch]$Iniciar,

    [switch]$IniciarComWindows
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

# O .lnk inicia o receptor. Ctrl+Alt+Z é registrado pelo próprio receptor.
$programs = [Environment]::GetFolderPath('Programs')
if (-not $programs -or -not (Test-Path -LiteralPath $programs -PathType Container)) {
    throw 'Não foi possível localizar o menu Iniciar do usuário.'
}
$shortcutPath = Join-Path $programs 'Gerenciador de Scripts.lnk'
$startup = [Environment]::GetFolderPath('Startup')
if (-not $startup -or -not (Test-Path -LiteralPath $startup -PathType Container)) {
    throw 'Não foi possível localizar a pasta Inicializar do usuário.'
}
$startupPath = Join-Path $startup 'Gerenciador de Scripts.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    $backupDir = Join-Path $env:LOCALAPPDATA 'GerenciadorScripts\config'
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $backupPath = Join-Path $backupDir ('atalho_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.lnk')
    Copy-Item -LiteralPath $shortcutPath -Destination $backupPath
    Write-Output "Backup do atalho anterior: $backupPath"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '"' + $entryPoint + '"'
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Iniciar o receptor de Ctrl+Alt+Z do Gerenciador de Scripts'
$shortcut.Hotkey = ''
$shortcut.WindowStyle = 1
$shortcut.Save()

# No logon, o Windows executa diretamente o receptor via pythonw, sem interface.
# Se já foi ativado antes, atualiza também os caminhos da inicialização.
if ($IniciarComWindows -or (Test-Path -LiteralPath $startupPath)) {
    Copy-Item -LiteralPath $shortcutPath -Destination $startupPath -Force
    Write-Output "Inicialização ao entrar no Windows configurada: $startupPath"
}

if (-not ('GerenciadorAtalho.Shell' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace GerenciadorAtalho {
    public static class Shell {
        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        public static extern void SHChangeNotify(uint evento, uint flags, string caminho, IntPtr outro);
    }
}
'@
}
[GerenciadorAtalho.Shell]::SHChangeNotify(0x2000, 5, $shortcutPath, [IntPtr]::Zero)

Write-Output "Atalho criado: $shortcutPath"
Write-Output 'Ctrl+Alt+Z será recebido pelo programa em segundo plano; o .lnk não possui hotkey.'
if ($Iniciar) {
    Start-Sleep -Seconds 2
    $processo = Start-Process -FilePath $pythonw -ArgumentList @('-B', ('"' + $entryPoint + '"')) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
    Write-Output 'Receptor iniciado. Use Ctrl+Alt+Z no campo desejado.'
    Write-Output "PID iniciado: $($processo.Id) (se já houver receptor, essa nova execução termina)."
}
