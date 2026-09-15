<#
Formlabs MES - password-protects (Encrypt) or opens (Decrypt) the
Move_To_New_PC.bat transfer package with AES-256, so the resin catalog
and every other table in the bundled database backup travels as
something other than a plain-text file sitting in an unencrypted zip.

Deliberately plain PowerShell / .NET Framework primitives only - no
external module, no Python, nothing from this project's own venv.
Unlock_Move_Package.bat (the double-click entry point on the receiving
PC) runs BEFORE Setup_On_New_PC.bat has installed anything at all, so
this script can't assume Python, pip, or even an internet connection
exist yet - only whatever already ships with Windows.

File layout of a *.zip.enc file:
    magic (9 bytes) | salt (16) | iv (16) | ciphertext (...) | hmac (32)

AES-256-CBC for confidentiality, HMAC-SHA256 for integrity
(encrypt-then-MAC) - the HMAC is checked BEFORE any AES decryption is
attempted, so a wrong password is reported plainly instead of surfacing
as a cryptic padding exception. Both keys come from one operator-chosen
password via PBKDF2-HMAC-SHA256 (600,000 iterations - OWASP's current
minimum for PBKDF2-SHA256).

Usage (called by Move_To_New_PC.bat and Unlock_Move_Package.bat, but
safe to run by hand):
    powershell -File Unlock_Move_Package.ps1 -Mode Encrypt -Path <zip>
    powershell -File Unlock_Move_Package.ps1 -Mode Decrypt -Path <zip.enc>
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('Encrypt', 'Decrypt')][string]$Mode,
    [Parameter(Mandatory = $true)][string]$Path
)

$ErrorActionPreference = 'Stop'
$Magic = [System.Text.Encoding]::ASCII.GetBytes("FLMESENC1")
$Iterations = 600000

function Read-PasswordPlain([string]$Prompt) {
    $secure = Read-Host -Prompt $Prompt -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

function New-RandomBytes([int]$Count) {
    $bytes = New-Object byte[] $Count
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return , $bytes
}

# Both keys come from the same PBKDF2 run (64 bytes = 32 for AES + 32 for
# HMAC) so a wrong password fails the HMAC check the same way regardless
# of which key it would have gotten wrong.
function Get-DerivedKeys([string]$Password, [byte[]]$Salt) {
    $pbkdf2 = [System.Security.Cryptography.Rfc2898DeriveBytes]::new(
        $Password, $Salt, $Iterations, [System.Security.Cryptography.HashAlgorithmName]::SHA256)
    try {
        $material = $pbkdf2.GetBytes(64)
        [PSCustomObject]@{
            AesKey  = [byte[]]$material[0..31]
            HmacKey = [byte[]]$material[32..63]
        }
    }
    finally { $pbkdf2.Dispose() }
}

function Get-Hmac([byte[]]$Key, [byte[]]$Data) {
    $hmac = [System.Security.Cryptography.HMACSHA256]::new($Key)
    try { return , $hmac.ComputeHash($Data) }
    finally { $hmac.Dispose() }
}

# Not a true constant-time compare (no CryptographicOperations.FixedTimeEquals
# in classic .NET Framework), but this never runs against a live oracle - it's
# a one-shot local file check - so a plain full-length compare is enough here.
function Test-BytesEqual([byte[]]$A, [byte[]]$B) {
    if ($A.Length -ne $B.Length) { return $false }
    $diff = 0
    for ($i = 0; $i -lt $A.Length; $i++) { $diff = $diff -bor ($A[$i] -bxor $B[$i]) }
    return $diff -eq 0
}

function Invoke-Aes([byte[]]$Key, [byte[]]$Iv, [byte[]]$Data, [bool]$ForEncrypt) {
    $aes = [System.Security.Cryptography.Aes]::Create()
    $aes.Key = $Key
    $aes.IV = $Iv
    $aes.Mode = [System.Security.Cryptography.CipherMode]::CBC
    $aes.Padding = [System.Security.Cryptography.PaddingMode]::PKCS7
    try {
        $transform = if ($ForEncrypt) { $aes.CreateEncryptor() } else { $aes.CreateDecryptor() }
        try { return , $transform.TransformFinalBlock($Data, 0, $Data.Length) }
        finally { $transform.Dispose() }
    }
    finally { $aes.Dispose() }
}

function Invoke-Encrypt([string]$ZipPath) {
    if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) {
        Write-Output "ENCRYPT_FAILED: $ZipPath not found"
        exit 1
    }

    Write-Host ""
    Write-Host "Set a password to protect this package. Anyone restoring it on"
    Write-Host "the new PC will need to type this exact password - write it"
    Write-Host "down somewhere that is NOT the same USB drive or folder as"
    Write-Host "this file. There is no way to recover it if it's lost."
    Write-Host ""
    $pw1 = Read-PasswordPlain "Password (at least 8 characters)"
    if ($pw1.Length -lt 8) {
        Write-Output "ENCRYPT_FAILED: password must be at least 8 characters"
        exit 1
    }
    $pw2 = Read-PasswordPlain "Confirm password"
    if ($pw1 -cne $pw2) {
        Write-Output "ENCRYPT_FAILED: passwords did not match"
        exit 1
    }

    $salt = New-RandomBytes 16
    $iv = New-RandomBytes 16
    $keys = Get-DerivedKeys $pw1 $salt

    $plaintext = [System.IO.File]::ReadAllBytes($ZipPath)
    $ciphertext = Invoke-Aes $keys.AesKey $iv $plaintext $true
    $tag = Get-Hmac $keys.HmacKey ($salt + $iv + $ciphertext)

    $outPath = "$ZipPath.enc"
    $out = [System.IO.FileStream]::new($outPath, [System.IO.FileMode]::Create)
    try {
        $out.Write($Magic, 0, $Magic.Length)
        $out.Write($salt, 0, $salt.Length)
        $out.Write($iv, 0, $iv.Length)
        $out.Write($ciphertext, 0, $ciphertext.Length)
        $out.Write($tag, 0, $tag.Length)
    }
    finally { $out.Dispose() }

    Remove-Item -LiteralPath $ZipPath -Force
    Write-Output "ENCRYPT_OK:$(Split-Path -Leaf $outPath)"
    exit 0
}

function Invoke-Decrypt([string]$EncPath) {
    if (-not (Test-Path -LiteralPath $EncPath -PathType Leaf)) {
        Write-Output "DECRYPT_FAILED: $EncPath not found"
        exit 1
    }

    $data = [System.IO.File]::ReadAllBytes($EncPath)
    $minLen = $Magic.Length + 16 + 16 + 32
    if ($data.Length -lt $minLen -or -not (Test-BytesEqual ([byte[]]$data[0..($Magic.Length - 1)]) $Magic)) {
        Write-Output "DECRYPT_FAILED: not a recognized encrypted package"
        exit 1
    }

    $pos = $Magic.Length
    $salt = [byte[]]$data[$pos..($pos + 15)]; $pos += 16
    $iv = [byte[]]$data[$pos..($pos + 15)]; $pos += 16
    $tag = [byte[]]$data[($data.Length - 32)..($data.Length - 1)]
    $ciphertext = [byte[]]$data[$pos..($data.Length - 33)]

    Write-Host ""
    $pw = Read-PasswordPlain "Password for this package"

    $keys = Get-DerivedKeys $pw $salt
    $expectedTag = Get-Hmac $keys.HmacKey ($salt + $iv + $ciphertext)
    if (-not (Test-BytesEqual $tag $expectedTag)) {
        Write-Output "DECRYPT_FAILED: wrong password (or the file is damaged/incomplete)"
        exit 1
    }

    $plaintext = Invoke-Aes $keys.AesKey $iv $ciphertext $false
    $outPath = if ($EncPath.ToLower().EndsWith('.enc')) { $EncPath.Substring(0, $EncPath.Length - 4) } else { "$EncPath.zip" }
    [System.IO.File]::WriteAllBytes($outPath, $plaintext)

    Write-Output "DECRYPT_OK:$(Split-Path -Leaf $outPath)"
    exit 0
}

try {
    if ($Mode -eq 'Encrypt') { Invoke-Encrypt $Path } else { Invoke-Decrypt $Path }
}
catch {
    Write-Output "$($Mode.ToUpper())_FAILED: $($_.Exception.Message)"
    exit 1
}
