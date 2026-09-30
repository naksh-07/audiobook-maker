param(
    [Parameter(Mandatory=$true)]
    [string]$Text,
    [Parameter(Mandatory=$false)]
    [string]$VoicePattern = "*David*",
    [Parameter(Mandatory=$true)]
    [string]$OutputPath
)

Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType = WindowsRuntime] | Out-Null
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer

$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -like $VoicePattern -or $_.Language -like $VoicePattern } | Select-Object -First 1
if ($voice) {
    $synth.Voice = $voice
}

$op = $synth.SynthesizeTextToStreamAsync($Text)
$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
$asTask = $asTaskGeneric.MakeGenericMethod([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
$task = $asTask.Invoke($null, @($op))
$task.Wait()

$asStream = [System.IO.WindowsRuntimeStreamExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsStreamForRead' } | Select-Object -First 1
$netStream = $asStream.Invoke($null, @($task.Result))

$outDir = [System.IO.Path]::GetDirectoryName($OutputPath)
if ($outDir -and -not [System.IO.Directory]::Exists($outDir)) {
    [System.IO.Directory]::CreateDirectory($outDir) | Out-Null
}

$fs = [System.IO.File]::Create($OutputPath)
$netStream.CopyTo($fs)
$fs.Close()
$netStream.Close()
Write-Output "SYNTH_OK: $OutputPath ($((Get-Item $OutputPath).Length) bytes)"
