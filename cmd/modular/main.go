package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"
)

func runCommand(bin string) ([]byte, error) {
	out, err := exec.Command(bin).Output()
	if err != nil {
		return nil, err
	}
	return out, nil
}

// version is set at build time via -ldflags "-X main.version=..."
// (see Makefile). The default matches VERSION on disk.
var version = "0.0.0"

func usage() {
	fmt.Print(`modular - Modular Linux CLI (v` + version + `)

Usage:
  modular list <desktops|wms|roles|gpu|hardware|applications|profiles>   List available profiles
  modular hardware                                         Detect host hardware
  modular resolve [desktop] [features...] [apps...]        Resolve a selection
  modular validate <modular.yaml>                          Validate a configuration
  modular generate-plan <modular.yaml>                     Generate installation plan
  modular install <modular.yaml> [--device /dev/sdX]       Install a configured system
  modular detect-binary                                    Emit raw JSON from prober
  modular version                                          Print version

Environment:
  MODULAR_PROFILES       Override profiles directory (default: ./profiles)
  MODULAR_INSTALL_DEVICE  Default target device (overridden by --device)
  MODULAR_INSTALL_HOSTNAME  Default hostname
  MODULAR_INSTALL_LOCALE    Default locale (default: C.UTF-8)
  MODULAR_INSTALL_TIMEZONE  Default timezone (default: UTC)
  MODULAR_INSTALL_KEYMAP    Default console keymap (default: us)
`)
}

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		usage()
		os.Exit(2)
	}

	reg := NewRegistry()
	if err := reg.LoadDirectory(defaultProfilesDir()); err != nil {
		fatal(err)
	}

	switch args[0] {
	case "list":
		cmdList(reg, args[1:])
	case "hardware", "detect-binary":
		cmdHardware(args[1:])
	case "resolve":
		cmdResolve(reg, args[1:])
	case "validate":
		cmdValidate(reg, args[1:])
	case "generate-plan":
		cmdGeneratePlan(reg, args[1:])
	case "install":
		cmdInstall(reg, args[1:])
	case "version", "--version":
		fmt.Println("modular " + version)
	default:
		usage()
		os.Exit(2)
	}
}

func cmdInstall(reg *Registry, args []string) {
	device := os.Getenv("MODULAR_INSTALL_DEVICE")
	for i := 0; i < len(args)-1; i++ {
		if args[i] == "--device" {
			device = args[i+1]
		}
	}
	if len(args) < 1 {
		usage()
		os.Exit(2)
	}
	configPath := args[0]
	cfg, err := LoadConfig(configPath)
	if err != nil {
		fatal(err)
	}
	if errs := Validate(cfg, reg); len(errs) > 0 {
		for _, e := range errs {
			fmt.Fprintln(os.Stderr, "invalid:", e)
		}
		os.Exit(1)
	}
	if device == "" {
		// No device and no env var: refuse to run rather than
		// accidentally target the live ISO's loopback.
		fmt.Fprintln(os.Stderr,
			"refusing to install without a target device: "+
				"pass --device /dev/sdX or set MODULAR_INSTALL_DEVICE")
		os.Exit(2)
	}
	if !strings.HasPrefix(device, "/dev/") {
		fmt.Fprintf(os.Stderr, "invalid --device: %s\n", device)
		os.Exit(2)
	}
	// Validate, plan, and defer the destructive steps to the Python
	// orchestrator (which handles pacstrap/chroot/bootloader/etc).
	// This keeps a single source of truth for the install sequence.
	fmt.Printf("validating %s ...\n", configPath)
	fmt.Println("OK")
	fmt.Printf("planning install on %s ...\n", device)
	hw := hardwareForResolution(reg, cfg)
	res, err := NewResolver(reg).Resolve(
		desktopOrNone(cfg), hw, cfg.Applications, cfg.Roles)
	if err != nil {
		fatal(err)
	}
	plan := BuildPlan(cfg, res)
	out, _ := yaml.Marshal(plan)
	fmt.Print(string(out))
	fmt.Println("delegating install to Python orchestrator")
	pyBin, err := findPythonOrchestrator()
	if err != nil {
		fatal(err)
	}
	pyArgs := []string{pyBin, configPath,
		"--device", device,
		"--non-interactive",
	}
	cmd := exec.Command("python3", pyArgs...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	if err := cmd.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "install failed: %v\n", err)
		os.Exit(1)
	}
}

func findPythonOrchestrator() (string, error) {
	exe, _ := os.Executable()
	candidates := []string{
		filepath.Join(filepath.Dir(exe), "..", "..",
			"installer", "installation", "orchestrator.py"),
		"installer/installation/orchestrator.py",
	}
	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			return p, nil
		}
	}
	return "", fmt.Errorf(
		"cannot find Python orchestrator; tried %v", candidates)
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, "error:", err)
	os.Exit(1)
}

func cmdList(reg *Registry, args []string) {
	if len(args) != 1 {
		usage()
		os.Exit(2)
	}
	var profiles []*Profile
	switch args[0] {
	case "desktops":
		profiles = reg.ByGroup("desktop")
	case "wms":
		profiles = reg.ByGroup("wm")
	case "applications":
		profiles = reg.ByGroup("applications")
	case "hardware":
		profiles = reg.ByGroup("hardware")
	case "gpu":
		profiles = reg.ByGroup("gpu")
	case "roles":
		profiles = reg.ByGroup("roles")
	case "profiles":
		profiles = reg.All()
	default:
		usage()
		os.Exit(2)
	}
	for _, p := range profiles {
		src := ""
		if p.Source != "" && p.Source != "-" {
			src = fmt.Sprintf(" [%s]", p.Source)
		}
		fmt.Printf("%-24s %-16s %s%s\n", p.ID, p.Category, p.Name, src)
	}
}

func cmdHardware(args []string) {
	bin := ""
	for i := 0; i < len(args)-1; i++ {
		if args[i] == "--detector" {
			bin = args[i+1]
		}
	}
	hw, err := DetectHardware(bin)
	if err != nil {
		fatal(err)
	}
	out, _ := json.MarshalIndent(hw, "", "  ")
	fmt.Println(string(out))
}

func cmdResolve(reg *Registry, args []string) {
	desktop := ""
	var hw, apps, roles []string
	for _, a := range args {
		id := qualify(a, "")
		p, err := reg.Get(id)
		if err == nil {
			switch p.Group {
			case "desktop", "wm":
				desktop = id
				continue
			case "hardware":
				hw = append(hw, id)
				continue
			case "gpu":
				hw = append(hw, id)
				continue
			case "applications":
				apps = append(apps, id)
				continue
			case "roles":
				roles = append(roles, id)
				continue
			}
		}
		switch {
		case contains(append(append([]string{}, supportedDesktops...),
			supportedWMs...), a):
			desktop = "desktop." + a
		case knownRoles[a]:
			roles = append(roles, "role."+a)
		case contains([]string{"network", "wifi", "bluetooth", "audio",
			"webcam", "printing", "scanner", "vpn"}, a):
			hw = append(hw, "hardware."+a)
		default:
			apps = append(apps, "app."+a)
		}
	}
	res, err := NewResolver(reg).Resolve(desktop, hw, apps, roles)
	if err != nil {
		fatal(err)
	}
	printResolution(res)
}

func printResolution(res *ResolutionResult) {
	fmt.Println("Profiles:")
	for _, p := range res.Selected {
		fmt.Printf("  %-24s %s\n", p.ID, p.Name)
		deps := res.Dependencies[p.ID]
		for _, d := range deps {
			fmt.Printf("    <- %s\n", d)
		}
	}
	fmt.Println("\nPackages:")
	for _, pkg := range res.Packages {
		fmt.Println("  -", pkg)
	}
	if len(res.Services) > 0 {
		fmt.Println("\nServices:")
		for _, svc := range res.Services {
			fmt.Println("  -", svc)
		}
	}
	if res.DisplayProtocol != "" {
		fmt.Println("\nDisplay:", res.DisplayProtocol)
	}
}

func cmdValidate(reg *Registry, args []string) {
	if len(args) != 1 {
		usage()
		os.Exit(2)
	}
	cfg, err := LoadConfig(args[0])
	if err != nil {
		fatal(err)
	}
	errs := Validate(cfg, reg)
	if len(errs) == 0 {
		fmt.Println("OK:", args[0], "is valid")
		return
	}
	for _, e := range errs {
		fmt.Println("INVALID:", e)
	}
	os.Exit(1)
}

func cmdGeneratePlan(reg *Registry, args []string) {
	if len(args) != 1 {
		usage()
		os.Exit(2)
	}
	cfg, err := LoadConfig(args[0])
	if err != nil {
		fatal(err)
	}
	if errs := Validate(cfg, reg); len(errs) > 0 {
		for _, e := range errs {
			fmt.Fprintln(os.Stderr, "invalid:", e)
		}
		os.Exit(1)
	}
	res, err := NewResolver(reg).Resolve(
		desktopOrNone(cfg),
		hardwareForResolution(reg, cfg),
		cfg.Applications,
		cfg.Roles,
	)
	if err != nil {
		fatal(err)
	}
	plan := BuildPlan(cfg, res)
	out, _ := yaml.Marshal(plan)
	fmt.Println(string(out))
}

func desktopOrNone(cfg *Config) string {
	if cfg.Desktop.Environment == "" {
		return "none"
	}
	return cfg.Desktop.Environment
}

// hardwareForResolution returns enabled bool features plus the resolved
// gpu.* profile id (spec §33).
func hardwareForResolution(reg *Registry, cfg *Config) []string {
	hw := mapKeysTrue(cfg.Hardware)
	gpuMode := "automatic"
	if g, ok := cfg.Hardware["gpu"]; ok {
		if s, ok2 := g.(string); ok2 {
			gpuMode = s
		}
	}
	vendor := gpuVendorFromDetection()
	switch {
	case gpuMode == "manual":
	case gpuMode == "nvidia-proprietary":
		hw = append(hw, "gpu.nvidia")
	case vendor == "nvidia" && gpuMode == "open-source":
		hw = append(hw, "gpu.nouveau")
	case vendor == "nvidia":
		hw = append(hw, "gpu.nvidia")
	case vendor == "amd":
		hw = append(hw, "gpu.amd")
	case vendor == "intel":
		hw = append(hw, "gpu.intel")
	}
	return hw
}

func gpuVendorFromDetection() string {
	hw, err := DetectHardware("")
	if err != nil {
		return ""
	}
	vendors := map[string]bool{}
	for _, g := range hw.GPU {
	 vendors[g.Vendor] = true
	}
	for _, want := range []string{"nvidia", "amd", "intel"} {
		if vendors[want] {
			return want
		}
	}
	return ""
}

func mapKeysTrue(m map[string]any) []string {
	var out []string
	for k, v := range m {
		if b, ok := v.(bool); ok && b {
			out = append(out, k)
		}
	}
	sort.Strings(out)
	return out
}

func sortStrings(s []string) {
	for i := 1; i < len(s); i++ {
		for j := i; j > 0 && s[j] < s[j-1]; j-- {
			s[j], s[j-1] = s[j-1], s[j]
		}
	}
}
