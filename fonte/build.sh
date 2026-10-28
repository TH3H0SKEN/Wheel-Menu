set -e
cd /home/claude/installer
export GOOS=windows GOARCH=amd64 CGO_ENABLED=0 GOFLAGS=-trimpath
python3 -I /home/claude/tools/make_syso.py payload/MeuLauncher.ico app.manifest rsrc_windows_amd64.syso 1.0.0.0 "Desinstalador do MeuLauncher" Desinstalar.exe
go vet -tags uninstaller . || true
go build -tags uninstaller -ldflags "-s -w -H windowsgui" -o payload/Desinstalar.exe .
python3 -I /home/claude/tools/make_syso.py payload/MeuLauncher.ico app.manifest rsrc_windows_amd64.syso 1.0.0.0 "Instalador do MeuLauncher" MeuLauncher-Setup.exe
go vet . || true
mkdir -p /home/claude/out
go build -ldflags "-s -w -H windowsgui" -o /home/claude/out/MeuLauncher-Setup.exe .
ls -la payload/Desinstalar.exe /home/claude/out/MeuLauncher-Setup.exe
