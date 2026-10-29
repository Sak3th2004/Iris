param([Parameter(Mandatory=$true)][string]$Sentence)
# Synthetic speech fixture only. Never presented as a human microphone recording.
$fixtureRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\artifacts'))
[IO.Directory]::CreateDirectory($fixtureRoot) | Out-Null
$fixturePath = Join-Path $fixtureRoot 'synthetic-speech.wav'
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $speaker.SetOutputToWaveFile($fixturePath, $format)
    $speaker.Speak($Sentence)
} finally { $speaker.Dispose() }
Write-Output 'Synthetic speech fixture written under artifacts.'
