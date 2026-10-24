param([string]$Root = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$OutputEncoding=[Console]::OutputEncoding
$Root=[System.IO.Path]::GetFullPath($Root)
$report=[ordered]@{timestamp=(Get-Date).ToString('o'); root=$Root; type='Windows EXE + real HTTP API smoke, not automated browser upload'; checks=@()}
$exe=Join-Path $Root 'MP3Score.exe'
$ready=Join-Path $Root 'portable-data\server.ready'
$stopFile=Join-Path $Root 'portable-data\stop.request'
function Start-App([string]$argument) {
    $si=[System.Diagnostics.ProcessStartInfo]::new($exe)
    $si.UseShellExecute=$false
    $si.WorkingDirectory=$Root
    $si.ArgumentList.Add($argument)
    $si.Environment['PATH']='C:\Windows\System32;C:\Windows'
    foreach($key in @('PYTHONHOME','PYTHONPATH','PYTHONUSERBASE','PIP_PREFIX','PIP_TARGET')){[void]$si.Environment.Remove($key)}
    [System.Diagnostics.Process]::Start($si)
}
$p=Start-App '--no-browser'
$handler=[System.Net.Http.HttpClientHandler]::new()
$handler.UseProxy=$false
$client=[System.Net.Http.HttpClient]::new($handler)
$client.Timeout=[TimeSpan]::FromSeconds(3)
try {
    $info=$null
    for($i=0;$i -lt 100;$i++) {
        [System.Threading.Thread]::Sleep(300)
        if($p.HasExited){throw ('Launcher exited: '+$p.ExitCode)}
        if(-not [System.IO.File]::Exists($ready)){continue}
        $lines=[System.IO.File]::ReadAllLines($ready)
        if($lines.Length -lt 2){continue}
        try {$info=$client.GetStringAsync($lines[1]+'api/info').GetAwaiter().GetResult() | ConvertFrom-Json;break} catch {}
    }
    if(-not $info){throw 'Server did not become ready'}
    $url=$lines[1]
    $serverPid=[int]$lines[0]
    if(-not ($info.engines | Where-Object {$_.name -eq 'basicpitch'}).available){throw 'Bundled engine unavailable'}
    $report.checks += 'EXE startup with no Python/FFmpeg in PATH, bundled engine available'
    $report.url=$url
    $report.version=$info.version
    $proc=[System.Diagnostics.Process]::GetProcessById($serverPid)
    $modules=@($proc.Modules | Where-Object {$_.ModuleName -match '^(python311|msvcp140.*|vcruntime140.*)\.dll$'} | ForEach-Object {$_.FileName})
    if(@($modules | Where-Object {-not $_.StartsWith((Join-Path $Root 'runtime'),[StringComparison]::OrdinalIgnoreCase)}).Count){throw 'A runtime DLL was loaded outside the bundle'}
    $report.runtime_modules=$modules
    $report.checks += 'CPython and VC runtime DLLs loaded from app runtime folder'
    $second=Start-App '--no-browser'
    if(-not $second.WaitForExit(5000)){throw 'Second launch did not exit (singleton failure)'}
    if(([System.IO.File]::ReadAllLines($ready))[0] -ne [string]$serverPid){throw 'Second launch changed server'}
    $report.checks += 'Second EXE launch reuses existing app'
    $media=Join-Path $Root 'samples\piano-chords.mp3'
    $bytes=[System.IO.File]::ReadAllBytes($media)
    $form=[System.Net.Http.MultipartFormDataContent]::new()
    $part=[System.Net.Http.ByteArrayContent]::new($bytes)
    $part.Headers.ContentType=[System.Net.Http.Headers.MediaTypeHeaderValue]::new('audio/mpeg')
    $form.Add($part,'file','piano-chords.mp3')
    $part.Headers.ContentDisposition.FileNameStar='피아노 화음 시험.mp3'
    $form.Add([System.Net.Http.StringContent]::new('120'),'bpm')
    $form.Add([System.Net.Http.StringContent]::new('piano'),'source_mode')
    $form.Add([System.Net.Http.StringContent]::new('false'),'make_pdf')
    $response=$client.PostAsync($url+'api/transcribe',$form).GetAwaiter().GetResult()
    if(-not $response.IsSuccessStatusCode){throw ('Upload HTTP '+[int]$response.StatusCode+': '+$response.Content.ReadAsStringAsync().GetAwaiter().GetResult())}
    $job=($response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json).job_id
    $state=$null
    for($i=0;$i -lt 240;$i++) {
        [System.Threading.Thread]::Sleep(500)
        $state=$client.GetStringAsync($url+'api/jobs/'+$job).GetAwaiter().GetResult() | ConvertFrom-Json
        if($state.status -in @('done','error')){break}
    }
    if($state.status -ne 'done'){throw ('Transcription failed: '+$state.error)}
    if($state.result.engine -ne 'basicpitch' -or $state.result.notes_kept -lt 4){throw 'Actual Basic Pitch transcription not demonstrated'}
    $report.conversion=$state.result
    $xml=$client.GetStringAsync($url+'api/jobs/'+$job+'/files/musicxml').GetAwaiter().GetResult()
    if($xml -notmatch '<score-partwise'){throw 'Invalid MusicXML'}
    $midi=$client.GetByteArrayAsync($url+'api/jobs/'+$job+'/files/midi').GetAwaiter().GetResult()
    if([Text.Encoding]::ASCII.GetString($midi,0,4) -ne 'MThd'){throw 'Invalid MIDI'}
    [System.IO.Directory]::CreateDirectory((Join-Path $Root 'portable-data\smoke-results')) | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $Root 'portable-data\smoke-results\score.musicxml'),$xml,[Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllBytes((Join-Path $Root 'portable-data\smoke-results\score.mid'),$midi)
    [System.IO.File]::WriteAllText((Join-Path $Root 'portable-data\smoke-results\result.json'),($state.result | ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
    $report.checks += 'Real MP3 multipart upload, Basic Pitch inference, MusicXML/MIDI HTTP download'
    $originals=@([System.IO.Directory]::EnumerateFiles((Join-Path $Root 'portable-data\temp'),'upload*',[IO.SearchOption]::AllDirectories))
    if($originals.Count -ne 0){throw 'Uploaded originals were not cleaned'}
    $report.checks += 'Upload original cleanup'
    $stop=Start-App '--stop'
    $stop.WaitForExit()
    if(-not $p.WaitForExit(30000)){throw 'Graceful EXE shutdown timed out'}
    if($p.ExitCode -ne 0){throw ('Launcher failure: '+$p.ExitCode)}
    if([System.IO.File]::Exists($ready)){throw 'Stale ready file after shutdown'}
    $jobs=@([System.IO.Directory]::EnumerateDirectories((Join-Path $Root 'portable-data\temp'),'mp3score_*'))
    if($jobs.Count -ne 0){throw 'Server temp directories remain'}
    $report.checks += 'Stop EXE, clean shutdown, zero server temp directories'
    $report.status='passed'
    $json=$report | ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText((Join-Path $Root 'docs\WINDOWS-EXE-SMOKE.json'),$json,[Text.UTF8Encoding]::new($false))
    $json
}
finally {
    if(-not $p.HasExited) {
        [System.IO.File]::WriteAllText($stopFile,'stop')
        if(-not $p.WaitForExit(15000)){$p.Kill($true)}
    }
    $client.Dispose()
}
