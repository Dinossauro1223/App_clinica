param(
    [Parameter(Mandatory=$true)][string]$Root,
    [Parameter(Mandatory=$true)][string]$RemoteSha
)

$ErrorActionPreference = "Stop"
$Repo = "Dinossauro1223/App_clinica"
$Root = [System.IO.Path]::GetFullPath($Root)
$Output = Join-Path $Root "Executavel do programa"
$TempRoot = Join-Path $env:TEMP ("NutriLab-update-" + [guid]::NewGuid().ToString("N"))
$Zip = Join-Path $TempRoot "source.zip"
$Extract = Join-Path $TempRoot "extract"
$DataBackup = Join-Path $TempRoot "dados"

function Fail($msg) {
    Write-Host ""
    Write-Host "ERRO: $msg" -ForegroundColor Red
    exit 1
}

if ($RemoteSha -notmatch "^[0-9a-fA-F]{40}$") {
    Fail "SHA remoto inválido."
}

New-Item -ItemType Directory -Force -Path $TempRoot,$Extract,$DataBackup | Out-Null

# Garante que nenhuma instância antiga ainda esteja usando o executável.
$exe = Join-Path $Output "NutriLab.exe"
for ($i = 0; $i -lt 20; $i++) {
    $processos = Get-CimInstance Win32_Process -Filter "Name = 'NutriLab.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -and ([System.IO.Path]::GetFullPath($_.ExecutablePath) -eq [System.IO.Path]::GetFullPath($exe)) }
    if (-not $processos) { break }
    foreach ($p in $processos) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
    Start-Sleep -Milliseconds 500
}

try {
    Write-Host "[1/7] Baixando a versão exata do commit $RemoteSha..."
    $url = "https://github.com/$Repo/archive/$RemoteSha.zip"
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $Zip -TimeoutSec 60

    Write-Host "[2/7] Validando e extraindo o pacote..."
    Expand-Archive -LiteralPath $Zip -DestinationPath $Extract -Force
    $newRoot = Get-ChildItem -LiteralPath $Extract -Directory | Select-Object -First 1
    if (-not $newRoot) { Fail "o arquivo ZIP não contém a pasta do projeto." }
    if (-not (Test-Path (Join-Path $newRoot.FullName "Gerar_e_Abrir_NutriLab.bat"))) {
        Fail "o pacote remoto não contém o launcher esperado."
    }
    if (-not (Test-Path (Join-Path $newRoot.FullName "app_clinica.spec"))) {
        Fail "o pacote remoto não contém o arquivo de compilação esperado."
    }

    Write-Host "[3/7] Preservando dados locais do usuário..."
    if (Test-Path $Output) {
        foreach ($nome in @("clinica.db","clinica.db-wal","clinica.db-shm","clinica.db-journal")) {
            $src = Join-Path $Output $nome
            if (Test-Path $src) { Copy-Item -LiteralPath $src -Destination $DataBackup -Force }
        }
        foreach ($pasta in @("backups","arquivos_pacientes")) {
            $src = Join-Path $Output $pasta
            if (Test-Path $src) { Copy-Item -LiteralPath $src -Destination $DataBackup -Recurse -Force }
        }
    }
    $mobileDados = Join-Path $Root "mobiledados"
    if (Test-Path $mobileDados) {
        Copy-Item -LiteralPath $mobileDados -Destination (Join-Path $DataBackup "mobile-dados") -Recurse -Force
    }

    Write-Host "[4/7] Atualizando os arquivos do programa..."
    $excludeDirs = @(".git","Executavel do programa","dist","build","logs","modelo_banco")
    $excludeFiles = @("clinica.db","clinica.db-wal","clinica.db-shm","clinica.db-journal",".nutrilab-version")
    $args = @($newRoot.FullName,$Root,"/E","/R:2","/W:1","/NFL","/NDL","/NJH","/NJS")
    foreach ($d in $excludeDirs) { $args += "/XD"; $args += (Join-Path $newRoot.FullName $d) }
    foreach ($f in $excludeFiles) { $args += "/XF"; $args += $f }
    & robocopy @args | Out-Null
    if ($LASTEXITCODE -ge 8) { Fail "falha ao copiar os arquivos novos." }

    Set-Content -LiteralPath (Join-Path $Root ".nutrilab-version") -Value $RemoteSha -Encoding ascii

    Write-Host "[5/7] Recriando o executável com o novo código..."
    $launcher = Join-Path $Root "Gerar_e_Abrir_NutriLab.bat"
    if (-not (Test-Path $launcher)) { Fail "launcher novo não foi encontrado." }

    # O launcher remove/recria a pasta de saída; o banco será restaurado depois.
    $proc = Start-Process -FilePath $env:ComSpec -ArgumentList @("/c","call",$launcher,"/apos-atualizacao") -WorkingDirectory $Root -Wait -PassThru
    if ($proc.ExitCode -ne 0) { Fail "a compilação da versão nova falhou." }
    if (-not (Test-Path (Join-Path $Output "NutriLab.exe"))) { Fail "novo executável não foi criado." }

    Write-Host "[6/7] Restaurando os dados preservados..."
    foreach ($nome in @("clinica.db","clinica.db-wal","clinica.db-shm","clinica.db-journal")) {
        $src = Join-Path $DataBackup $nome
        if (Test-Path $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $Output $nome) -Force }
    }
    foreach ($pasta in @("backups","arquivos_pacientes")) {
        $src = Join-Path $DataBackup $pasta
        if (Test-Path $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $Output $pasta) -Recurse -Force }
    }
    $mobileBackup = Join-Path $DataBackup "mobile-dados"
    if (Test-Path $mobileBackup) {
        $dest = Join-Path $Root "mobiledados"
        New-Item -ItemType Directory -Force -Path $dest | Out-Null
        Copy-Item -LiteralPath (Join-Path $mobileBackup "*") -Destination $dest -Recurse -Force
    }

    Write-Host "[7/7] Atualização concluída. Abrindo o NutriLab..."
    Start-Process -FilePath (Join-Path $Output "NutriLab.exe") -WorkingDirectory $Output
}
catch {
    Write-Host ""
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "O banco original foi preservado; a atualização não será considerada concluída."
    exit 1
}
finally {
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
exit 0
