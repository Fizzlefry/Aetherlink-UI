# Tiny shim so you can run:  .\a up
param([Parameter(ValueFromRemainingArguments = $true)]$Args)
& powershell -NoProfile -ExecutionPolicy Bypass -File ".\makefile.ps1" @Args
