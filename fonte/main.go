//go:build windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"
)

const (
	appName     = "MeuLauncher"
	appVersion  = "1.0.0"
	exeName     = "MeuLauncher.exe"
	icoName     = "MeuLauncher.ico"
	uninstName  = "Desinstalar.exe"
	runKey      = `Software\Microsoft\Windows\CurrentVersion\Run`
	uninstKey   = `Software\Microsoft\Windows\CurrentVersion\Uninstall\MeuLauncher`
	createNoWin = 0x08000000
)

type options struct {
	desktop   bool
	autostart bool
	launch    bool
}

type paths struct {
	installDir, exe, ico, uninst string
	startMenuLnk, desktopLnk     string
	configDir, configFile        string
}

func resolvePaths() paths {
	var p paths
	local := os.Getenv("LOCALAPPDATA")
	if local == "" {
		local, _ = os.UserCacheDir()
	}
	p.installDir = filepath.Join(local, "Programs", appName)
	p.exe = filepath.Join(p.installDir, exeName)
	p.ico = filepath.Join(p.installDir, icoName)
	p.uninst = filepath.Join(p.installDir, uninstName)

	programs := knownFolder(&folderPrograms)
	if programs == "" {
		programs = filepath.Join(os.Getenv("APPDATA"), `Microsoft\Windows\Start Menu\Programs`)
	}
	p.startMenuLnk = filepath.Join(programs, appName+".lnk")
	desktop := knownFolder(&folderDesktop)
	if desktop == "" {
		desktop = filepath.Join(os.Getenv("USERPROFILE"), "Desktop")
	}
	p.desktopLnk = filepath.Join(desktop, appName+".lnk")

	// Same location the app itself uses (config.py: %APPDATA%\MeuLauncher).
	roaming := os.Getenv("APPDATA")
	if roaming == "" {
		roaming, _ = os.UserConfigDir()
	}
	p.configDir = filepath.Join(roaming, appName)
	p.configFile = filepath.Join(p.configDir, "config.json")
	return p
}

func exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func system32(name string) string {
	root := os.Getenv("SystemRoot")
	if root == "" {
		root = `C:\Windows`
	}
	return filepath.Join(root, "System32", name)
}

func hidden(cmd *exec.Cmd) *exec.Cmd {
	if cmd.SysProcAttr == nil {
		cmd.SysProcAttr = &syscall.SysProcAttr{}
	}
	cmd.SysProcAttr.HideWindow = true
	cmd.SysProcAttr.CreationFlags |= createNoWin
	return cmd
}

// stopRunningApp closes any running MeuLauncher (PyInstaller onefile = 2 processes).
func stopRunningApp() {
	_ = hidden(exec.Command(system32("taskkill.exe"), "/F", "/T", "/IM", exeName)).Run()
}

// writeFileReplacing writes to a temp file and swaps it in, retrying while the
// old file is still locked by a process that is shutting down.
func writeFileReplacing(dst string, data []byte) error {
	tmp := dst + ".novo"
	if err := os.WriteFile(tmp, data, 0o755); err != nil {
		return err
	}
	var err error
	for i := 0; i < 40; i++ {
		if err = os.Rename(tmp, dst); err == nil {
			return nil
		}
		time.Sleep(250 * time.Millisecond)
	}
	os.Remove(tmp)
	return err
}

func runCommand(exe string) string { return `"` + exe + `"` }

func install(p paths, o options) error {
	stopRunningApp()

	if err := os.MkdirAll(p.installDir, 0o755); err != nil {
		return fmt.Errorf("não foi possível criar a pasta %s: %w", p.installDir, err)
	}
	if err := writeFileReplacing(p.exe, appExe); err != nil {
		return fmt.Errorf("não foi possível gravar %s (o MeuLauncher ainda está aberto?): %w", exeName, err)
	}
	if err := writeFileReplacing(p.ico, appIcon); err != nil {
		return fmt.Errorf("não foi possível gravar o ícone: %w", err)
	}
	if err := writeFileReplacing(p.uninst, uninstallerExe); err != nil {
		return fmt.Errorf("não foi possível gravar o desinstalador: %w", err)
	}

	// Start Menu shortcut (always) and Desktop shortcut (optional).
	_ = os.MkdirAll(filepath.Dir(p.startMenuLnk), 0o755)
	if err := createShortcut(p.startMenuLnk, p.exe, p.installDir, "Menu radial (Ctrl+Espaço)", p.ico); err != nil {
		return fmt.Errorf("não foi possível criar o atalho no Menu Iniciar: %w", err)
	}
	if o.desktop {
		if err := createShortcut(p.desktopLnk, p.exe, p.installDir, "Menu radial (Ctrl+Espaço)", p.ico); err != nil {
			return fmt.Errorf("não foi possível criar o atalho na Área de Trabalho: %w", err)
		}
	} else {
		os.Remove(p.desktopLnk)
	}

	// Autostart: same Run value the app's own tray toggle uses.
	if o.autostart {
		if err := regSetString(runKey, appName, runCommand(p.exe)); err != nil {
			return fmt.Errorf("não foi possível ativar o início com o Windows: %w", err)
		}
	} else {
		regDeleteValue(runKey, appName)
	}

	// Pre-create config.json so the app skips its first-run autostart question
	// (the installer already asked). Existing settings are never touched.
	if !exists(p.configFile) {
		if err := os.MkdirAll(p.configDir, 0o755); err == nil {
			_ = os.WriteFile(p.configFile, defaultConfig, 0o644)
		}
	}

	// "Apps & features" entry.
	size := uint32((len(appExe) + len(appIcon) + len(uninstallerExe)) / 1024)
	vals := map[string]string{
		"DisplayName":          appName,
		"DisplayVersion":       appVersion,
		"Publisher":            appName,
		"DisplayIcon":          p.ico,
		"InstallLocation":      p.installDir,
		"UninstallString":      runCommand(p.uninst) + " /uninstall",
		"QuietUninstallString": runCommand(p.uninst) + " /uninstall /S",
		"InstallDate":          time.Now().Format("20060102"),
	}
	for k, v := range vals {
		if err := regSetString(uninstKey, k, v); err != nil {
			return fmt.Errorf("não foi possível registrar o programa no Windows: %w", err)
		}
	}
	_ = regSetDword(uninstKey, "NoModify", 1)
	_ = regSetDword(uninstKey, "NoRepair", 1)
	_ = regSetDword(uninstKey, "EstimatedSize", size)
	return nil
}

func launchApp(p paths) {
	cmd := exec.Command(p.exe)
	cmd.Dir = p.installDir
	if cmd.Start() == nil {
		_ = cmd.Process.Release()
	}
}

func uninstall(p paths, removeConfig bool) {
	stopRunningApp()
	time.Sleep(500 * time.Millisecond)

	os.Remove(p.startMenuLnk)
	os.Remove(p.desktopLnk)
	if v, ok := regGetString(runKey, appName); ok &&
		strings.Contains(strings.ToLower(v), strings.ToLower(p.installDir)) {
		regDeleteValue(runKey, appName)
	}
	regDeleteKey(uninstKey)

	for i := 0; i < 20; i++ {
		if err := os.Remove(p.exe); err == nil || os.IsNotExist(err) {
			break
		}
		time.Sleep(250 * time.Millisecond)
	}
	os.Remove(p.ico)

	if removeConfig {
		os.Remove(p.configFile)
		os.Remove(p.configDir) // only if empty
	}

	self, _ := os.Executable()
	if strings.EqualFold(filepath.Clean(self), filepath.Clean(p.uninst)) {
		// A running .exe can't delete itself: let a hidden cmd finish the job
		// once this process exits. Only our own file and the (empty) folder.
		line := fmt.Sprintf(`cmd.exe /d /c ping -n 3 127.0.0.1 >nul & del /f /q "%s" & rmdir "%s"`,
			p.uninst, p.installDir)
		cmd := hidden(exec.Command(system32("cmd.exe")))
		cmd.SysProcAttr.CmdLine = line
		cmd.Dir = os.TempDir()
		if cmd.Start() == nil {
			_ = cmd.Process.Release()
		}
	} else {
		os.Remove(p.uninst)
		os.Remove(p.installDir)
	}
}

func hasArg(names ...string) bool {
	for _, a := range os.Args[1:] {
		for _, n := range names {
			if strings.EqualFold(a, n) {
				return true
			}
		}
	}
	return false
}

func main() {
	runtime.LockOSThread()
	procCoInitializeEx.Call(0, 2 /*COINIT_APARTMENTTHREADED*/)

	p := resolvePaths()
	silent := hasArg("/S", "/silent", "--silent", "-s")

	if isUninstaller || hasArg("/uninstall", "--uninstall") {
		if !silent {
			if messageBox(0, "Deseja remover o MeuLauncher deste computador?",
				"Desinstalar o MeuLauncher", mbYesNo|mbIconQuestion) != idYes {
				return
			}
		}
		removeConfig := false
		if !silent && exists(p.configFile) {
			removeConfig = messageBox(0,
				"Remover também suas configurações e favoritos?\n\n"+p.configDir,
				"Desinstalar o MeuLauncher", mbYesNo|mbIconQuestion|mbDefButton2) == idYes
		}
		uninstall(p, removeConfig)
		if !silent {
			messageBox(0, "O MeuLauncher foi removido.", "Desinstalar o MeuLauncher", mbOK|mbIconInfo)
		}
		return
	}

	if silent {
		if err := install(p, options{desktop: false, autostart: true}); err != nil {
			os.Exit(1)
		}
		return
	}
	runSetupWindow(p)
}
