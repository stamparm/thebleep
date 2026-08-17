if ((Get-Command "bleep").CommandType -eq "Function") {
	bleep @args;
	[Console]::ResetColor()
	exit
}

"First time use of thebleep detected. "

if ((Get-Content $PROFILE -Raw -ErrorAction Ignore) -like "*thebleep*") {
} else {
	"  - Adding thebleep intialization to user `$PROFILE"
	$script = "`n`$env:PYTHONIOENCODING='utf-8' `niex `"`$(thebleep --alias)`"";
	Write-Output $script | Add-Content $PROFILE
}

"  - Adding bleep() function to current session..."
$env:PYTHONIOENCODING='utf-8'
iex "$($(thebleep --alias).Replace("function bleep", "function global:bleep"))"

"  - Invoking bleep()`n"
bleep @args;
[Console]::ResetColor()
