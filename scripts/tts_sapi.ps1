param(
    [Parameter(Mandatory = $true)][string]$TextPath,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [string]$VoiceName = "",
    [string]$Culture = "en-US"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voices = @(
        $synth.GetInstalledVoices() |
            Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like "en-*" }
    )
    if ($voices.Count -eq 0) {
        throw "No enabled English voice is installed"
    }

    $selected = $null
    if ($VoiceName) {
        $selected = $voices |
            Where-Object { $_.VoiceInfo.Name -eq $VoiceName } |
            Select-Object -First 1
    }
    if (-not $selected) {
        $selected = $voices |
            Where-Object { $_.VoiceInfo.Culture.Name -eq $Culture } |
            Select-Object -First 1
    }
    if (-not $selected) {
        $selected = $voices[0]
    }

    $synth.SelectVoice($selected.VoiceInfo.Name)
    $synth.Rate = 0
    $synth.Volume = 100

    $text = Get-Content -LiteralPath $TextPath -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "Text is empty"
    }

    $synth.SetOutputToWaveFile($OutputPath)
    $synth.Speak($text.Trim())
    Write-Output ("VOICE|" + $selected.VoiceInfo.Name + "|" + $selected.VoiceInfo.Culture.Name)
}
finally {
    $synth.Dispose()
}
