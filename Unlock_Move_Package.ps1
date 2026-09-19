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

Everything is streamed through in fixed 1 MB chunks rather than read
into one big byte array. An earlier version called
[System.IO.File]::ReadAllBytes() on the whole package (and built a
second full-size array for the ciphertext, on top of that) - on at
least one real machine that failed outright with "Array dimensions
exceeded supported range", which is the classic .NET single-array-
allocation ceiling. Chunked streaming has no such ceiling: peak memory
stays a few MB regardless of whether the package is 50 MB or 50 GB.

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
$BufferSize = 1MB   # an exact multiple of the AES block size (16 bytes)

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

# Not a true constant-time compare (no CryptographicOperations.FixedTimeEquals
# in classic .NET Framework), but this never runs against a live oracle - it's
# a one-shot local file check - so a plain full-length compare is enough here.
function Test-BytesEqual([byte[]]$A, [byte[]]$B) {
    if ($A.Length -ne $B.Length) { return $false }
    $diff = 0
    for ($i = 0; $i -lt $A.Length; $i++) { $diff = $diff -bor ($A[$i] -bxor $B[$i]) }
    return $diff -eq 0
}

# Loops Stream.Read until exactly $Count bytes have landed in $Buffer -
# a single .Read() call is allowed to return short even before EOF, so
# every fixed-size read in this file goes through here rather than
# trusting one call to fill the buffer.
function Read-Exact([System.IO.Stream]$Stream, [byte[]]$Buffer, [int]$Count) {
    $offset = 0
    while ($offset -lt $Count) {
        $n = $Stream.Read($Buffer, $offset, $Count - $offset)
        if ($n -le 0) { throw "Unexpected end of file (wanted $Count bytes, got $offset)." }
        $offset += $n
    }
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

    $outPath = "$ZipPath.enc"
    $aes = [System.Security.Cryptography.Aes]::Create()
    $aes.Key = $keys.AesKey
    $aes.IV = $iv
    $aes.Mode = [System.Security.Cryptography.CipherMode]::CBC
    $aes.Padding = [System.Security.Cryptography.PaddingMode]::PKCS7
    $encryptor = $aes.CreateEncryptor()
    $hmac = [System.Security.Cryptography.HMACSHA256]::new($keys.HmacKey)

    $inStream = $null
    $outStream = $null
    try {
        $inStream = [System.IO.File]::OpenRead($ZipPath)
        $outStream = [System.IO.FileStream]::new($outPath, [System.IO.FileMode]::Create)
        $outStream.Write($Magic, 0, $Magic.Length)
        $outStream.Write($salt, 0, $salt.Length)
        $outStream.Write($iv, 0, $iv.Length)
        $hmac.TransformBlock($salt, 0, $salt.Length, $salt, 0) | Out-Null
        $hmac.TransformBlock($iv, 0, $iv.Length, $iv, 0) | Out-Null

        $buf = New-Object byte[] $BufferSize
        $cipherBuf = New-Object byte[] $BufferSize
        $remaining = $inStream.Length
        while ($remaining -gt $BufferSize) {
            Read-Exact $inStream $buf $BufferSize
            $written = $encryptor.TransformBlock($buf, 0, $BufferSize, $cipherBuf, 0)
            if ($written -gt 0) {
                $outStream.Write($cipherBuf, 0, $written)
                $hmac.TransformBlock($cipherBuf, 0, $written, $cipherBuf, 0) | Out-Null
            }
            $remaining -= $BufferSize
        }
        $lastLen = [int]$remaining
        if ($lastLen -gt 0) { Read-Exact $inStream $buf $lastLen }
        $finalBlock = $encryptor.TransformFinalBlock($buf, 0, $lastLen)
        $outStream.Write($finalBlock, 0, $finalBlock.Length)
        if ($finalBlock.Length -gt 0) {
            $hmac.TransformBlock($finalBlock, 0, $finalBlock.Length, $finalBlock, 0) | Out-Null
        }

        $hmac.TransformFinalBlock([byte[]]@(), 0, 0) | Out-Null
        $tag = $hmac.Hash
        $outStream.Write($tag, 0, $tag.Length)
    }
    finally {
        if ($inStream) { $inStream.Dispose() }
        if ($outStream) { $outStream.Dispose() }
        $encryptor.Dispose()
        $aes.Dispose()
        $hmac.Dispose()
    }

    Remove-Item -LiteralPath $ZipPath -Force
    Write-Output "ENCRYPT_OK:$(Split-Path -Leaf $outPath)"
    exit 0
}

function Invoke-Decrypt([string]$EncPath) {
    if (-not (Test-Path -LiteralPath $EncPath -PathType Leaf)) {
        Write-Output "DECRYPT_FAILED: $EncPath not found"
        exit 1
    }

    $fileLength = (Get-Item -LiteralPath $EncPath).Length
    # magic + salt + iv + at least one full AES block of ciphertext + hmac -
    # PKCS7 padding means even an empty package encrypts to one whole block,
    # so anything shorter than this could not be a genuine package.
    $minLen = $Magic.Length + 16 + 16 + 16 + 32
    if ($fileLength -lt $minLen) {
        Write-Output "DECRYPT_FAILED: not a recognized encrypted package"
        exit 1
    }

    $outPath = $null
    $inStream = [System.IO.File]::OpenRead($EncPath)
    try {
        $magicBuf = New-Object byte[] $Magic.Length
        Read-Exact $inStream $magicBuf $Magic.Length
        if (-not (Test-BytesEqual $magicBuf $Magic)) {
            Write-Output "DECRYPT_FAILED: not a recognized encrypted package"
            exit 1
        }
        $salt = New-Object byte[] 16
        Read-Exact $inStream $salt 16
        $iv = New-Object byte[] 16
        Read-Exact $inStream $iv 16

        $ciphertextLength = $fileLength - $Magic.Length - 16 - 16 - 32
        $ciphertextStart = $inStream.Position

        Write-Host ""
        $pw = Read-PasswordPlain "Password for this package"
        $keys = Get-DerivedKeys $pw $salt

        # Pass 1: stream the ciphertext through the HMAC only, verifying it
        # before any decryption is attempted - a wrong password is reported
        # plainly here rather than surfacing as a padding exception out of
        # the decryptor in pass 2.
        $buf = New-Object byte[] $BufferSize
        $hmac = [System.Security.Cryptography.HMACSHA256]::new($keys.HmacKey)
        try {
            $hmac.TransformBlock($salt, 0, $salt.Length, $salt, 0) | Out-Null
            $hmac.TransformBlock($iv, 0, $iv.Length, $iv, 0) | Out-Null
            $remaining = $ciphertextLength
            while ($remaining -gt 0) {
                $chunk = [Math]::Min($BufferSize, $remaining)
                Read-Exact $inStream $buf $chunk
                $hmac.TransformBlock($buf, 0, $chunk, $buf, 0) | Out-Null
                $remaining -= $chunk
            }
            $hmac.TransformFinalBlock([byte[]]@(), 0, 0) | Out-Null
            $computedTag = $hmac.Hash
        }
        finally { $hmac.Dispose() }

        $storedTag = New-Object byte[] 32
        Read-Exact $inStream $storedTag 32

        if (-not (Test-BytesEqual $computedTag $storedTag)) {
            Write-Output "DECRYPT_FAILED: wrong password (or the file is damaged/incomplete)"
            exit 1
        }

        # Pass 2: the password's confirmed right - decrypt for real, the
        # same streamed way, straight into the restored .zip.
        $outPath = if ($EncPath.ToLower().EndsWith('.enc')) { $EncPath.Substring(0, $EncPath.Length - 4) } else { "$EncPath.zip" }
        $aes = [System.Security.Cryptography.Aes]::Create()
        $aes.Key = $keys.AesKey
        $aes.IV = $iv
        $aes.Mode = [System.Security.Cryptography.CipherMode]::CBC
        $aes.Padding = [System.Security.Cryptography.PaddingMode]::PKCS7
        $decryptor = $aes.CreateDecryptor()
        $outStream = $null
        try {
            $inStream.Position = $ciphertextStart
            $outStream = [System.IO.FileStream]::new($outPath, [System.IO.FileMode]::Create)
            $plainBuf = New-Object byte[] $BufferSize
            $remaining = $ciphertextLength
            while ($remaining -gt $BufferSize) {
                Read-Exact $inStream $buf $BufferSize
                $written = $decryptor.TransformBlock($buf, 0, $BufferSize, $plainBuf, 0)
                if ($written -gt 0) { $outStream.Write($plainBuf, 0, $written) }
                $remaining -= $BufferSize
            }
            $lastLen = [int]$remaining
            Read-Exact $inStream $buf $lastLen
            $finalPlain = $decryptor.TransformFinalBlock($buf, 0, $lastLen)
            $outStream.Write($finalPlain, 0, $finalPlain.Length)
        }
        finally {
            if ($outStream) { $outStream.Dispose() }
            $decryptor.Dispose()
            $aes.Dispose()
        }
    }
    finally { $inStream.Dispose() }

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
