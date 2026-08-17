@set PYTHONIOENCODING=utf-8
@powershell -noprofile -c "cmd /c \"$(thebleep %* $(doskey /history)[-2])\"; [Console]::ResetColor();"
