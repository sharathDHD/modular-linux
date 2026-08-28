package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"
)

var basePackages = []string{"base", "linux", "linux-firmware", "sudo"}
var supportedFilesystems = []string{"ext4", "btrfs"}
var supportedBootloaders = []string{"systemd-boot", "grub"}
var supportedDesktops = []string{"kde", "gnome", "xfce", "cinnamon", "mate",
	"lxqt", "lxde", "budgie", "cosmic", "hyprland", "none"}
var supportedWMs = []string{"sway", "i3", "openbox", "awesome", "bspwm",
	"river", "labwc", "none"}
var supportedKernels = []string{"linux", "linux-lts", "linux-zen",
	"linux-hardened"}
var supportedShells = []string{"bash", "zsh", "fish"}
var supportedGPUModes = []string{"automatic", "open-source",
	"nvidia-proprietary", "manual"}
var knownRoles = map[string]bool{"general": true, "developer": true,
	"ai-ml": true, "gaming": true, "creator": true, "student": true,
	"server": true, "security": true}

// Config mirrors modular.yaml v1 (spec §30).
type Config struct {
	Version any `yaml:"version"`
	Base    struct {
		Distribution string `yaml:"distribution"`
	} `yaml:"base"`
	System struct {
		Architecture string `yaml:"architecture"`
		Kernel       string `yaml:"kernel"`
		Init         string `yaml:"init"`
	} `yaml:"system"`
	Desktop struct {
		Environment  string `yaml:"environment"`
		Display      string `yaml:"display"`
		LoginManager string `yaml:"login_manager"`
	} `yaml:"desktop"`
	Hardware     map[string]any `yaml:"hardware"`
	Roles        []string       `yaml:"roles"`
	Applications []string       `yaml:"applications"`
	Shell        struct {
		Type string `yaml:"type"`
	} `yaml:"shell"`
	Filesystem struct {
		Type string `yaml:"type"`
	} `yaml:"filesystem"`
	Bootloader struct {
		Type string `yaml:"type"`
	} `yaml:"bootloader"`
	Sources map[string]bool `yaml:"sources"`
}

// InstallationPlan mirrors engine.packages.InstallationPlan (spec §14/§29).
type InstallationPlan struct {
	Version         string          `yaml:"version"`
	Distribution    string          `yaml:"distribution"`
	Architecture    string          `yaml:"architecture"`
	Init            string          `yaml:"init"`
	Kernel          string          `yaml:"kernel"`
	BasePackages    []string        `yaml:"base_packages"`
	Packages        []string        `yaml:"packages"`
	AURPackages     []string        `yaml:"aur_packages"`
	FlatpakPackages []string        `yaml:"flatpak_packages"`
	Services        []string        `yaml:"services"`
	Filesystem      string          `yaml:"filesystem"`
	Bootloader      string          `yaml:"bootloader"`
	Shell           string          `yaml:"shell"`
	Display         string          `yaml:"display,omitempty"`
	LoginManager    string          `yaml:"login_manager,omitempty"`
	Desktop         string          `yaml:"desktop,omitempty"`
	Roles           []string        `yaml:"roles,omitempty"`
	Hardware        []string        `yaml:"hardware,omitempty"`
	Sources         map[string]bool `yaml:"sources"`
}

func LoadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("cannot read %s: %w", path, err)
	}
	var c Config
	if err := yaml.Unmarshal(data, &c); err != nil {
		return nil, fmt.Errorf("invalid YAML in %s: %w", path, err)
	}
	return &c, nil
}

func selectedHardware(hw map[string]any) []string {
	var out []string
	for k, v := range hw {
		if b, ok := v.(bool); ok && b {
			out = append(out, k)
		}
	}
	sort.Strings(out)
	return out
}

func kernelPackages(kernel string) []string {
	out := make([]string, len(basePackages))
	copy(out, basePackages)
	if contains(supportedKernels, kernel) && kernel != "linux" {
		out[1] = kernel
	}
	return out
}

// desktopLoginManager implements spec §27 derivation.
var desktopLoginManager = map[string]string{
	"kde": "sddm", "gnome": "gdm", "xfce": "lightdm",
	"cinnamon": "lightdm", "mate": "lightdm", "lxqt": "sddm",
	"lxde": "lightdm", "budgie": "lightdm", "cosmic": "cosmic-greeter",
	"hyprland": "ly", "sway": "ly", "i3": "ly",
}

func deriveLoginManager(desktopID, override string) string {
	if override != "" && override != "automatic" {
		return override
	}
	env := strings.TrimPrefix(strings.TrimPrefix(desktopID, "desktop."), "wm.")
	return desktopLoginManager[env]
}

func Validate(c *Config, reg *Registry) []string {
	var errs []string
	if fmt.Sprint(c.Version) != "1" && fmt.Sprint(c.Version) != "1.0" {
		errs = append(errs, fmt.Sprintf("unsupported configuration version: %v", c.Version))
	}
	if c.Base.Distribution != "arch" && c.Base.Distribution != "" {
		errs = append(errs, fmt.Sprintf("unsupported distribution: %s", c.Base.Distribution))
	}
	if c.System.Architecture != "" && c.System.Architecture != "x86_64" {
		errs = append(errs, fmt.Sprintf("unsupported architecture: %s", c.System.Architecture))
	}
	if c.System.Init != "" && c.System.Init != "systemd" {
		errs = append(errs, fmt.Sprintf("unsupported init system: %s", c.System.Init))
	}
	kernel := c.System.Kernel
	if kernel == "" {
		kernel = "linux"
	}
	if !contains(supportedKernels, kernel) {
		errs = append(errs, fmt.Sprintf("unknown kernel '%s'", kernel))
	}
	env := c.Desktop.Environment
	if env == "" {
		env = "none"
	}
	if !contains(supportedDesktops, env) && !contains(supportedWMs, env) {
		errs = append(errs, fmt.Sprintf("unknown desktop environment '%s'", env))
	}
	disp := c.Desktop.Display
	if disp == "" {
		disp = "automatic"
	}
	if disp != "wayland" && disp != "x11" && disp != "automatic" {
		errs = append(errs, fmt.Sprintf("unknown display protocol: %s", disp))
	}
	lm := c.Desktop.LoginManager
	if lm != "" && lm != "automatic" &&
		!contains([]string{"sddm", "gdm", "lightdm", "ly", "none"}, lm) {
		errs = append(errs, fmt.Sprintf("unknown login manager: %s", lm))
	}
	gpuMode := "automatic"
	if g, ok := c.Hardware["gpu"]; ok {
		if s, ok2 := g.(string); ok2 {
			gpuMode = s
		}
	}
	if !contains(supportedGPUModes, gpuMode) {
		errs = append(errs, fmt.Sprintf("unknown GPU mode '%s'", gpuMode))
	}
	knownHW := map[string]bool{"network": true, "wifi": true, "bluetooth": true,
		"audio": true, "webcam": true, "printing": true, "scanner": true,
		"vpn": true}
	for k := range c.Hardware {
		if k == "gpu" {
			continue
		}
		if !knownHW[k] {
			errs = append(errs, fmt.Sprintf("unknown hardware feature: %s", k))
		}
	}
	if reg != nil {
		for _, r := range c.Roles {
			id := r
			if !strings.Contains(r, ".") {
				id = "role." + r
			}
			if !reg.Has(id) && !knownRoles[r] {
				errs = append(errs, fmt.Sprintf("unknown role profile: %s", id))
			}
		}
	}
	if reg != nil {
		aurSelected, flatpakSelected := false, false
		for _, a := range c.Applications {
			id := a
			if !strings.Contains(a, ".") {
				id = "app." + a
			}
			p, err := reg.Get(id)
			if err != nil {
				errs = append(errs, fmt.Sprintf("unknown application profile: %s", id))
				continue
			}
			switch p.Source {
			case "aur":
				aurSelected = true
			case "flatpak":
				flatpakSelected = true
			}
		}
		if aurSelected && !c.Sources["aur"] {
			errs = append(errs, "configuration selects AUR applications but sources.aur is disabled")
		}
		if flatpakSelected && !c.Sources["flatpak"] {
			errs = append(errs, "configuration selects Flatpak applications but sources.flatpak is disabled")
		}
	}
	fs := c.Filesystem.Type
	if fs == "" {
		fs = "ext4"
	}
	if !contains(supportedFilesystems, fs) {
		errs = append(errs, fmt.Sprintf("unsupported filesystem '%s'", fs))
	}
	bl := c.Bootloader.Type
	if bl == "" {
		bl = "systemd-boot"
	}
	if !contains(supportedBootloaders, bl) {
		errs = append(errs, fmt.Sprintf("unsupported bootloader '%s'", bl))
	}
	shellType := c.Shell.Type
	if shellType == "" {
		shellType = "bash"
	}
	if !contains(supportedShells, shellType) {
		errs = append(errs, fmt.Sprintf("unsupported shell '%s'", shellType))
	}
	return errs
}

func BuildPlan(c *Config, res *ResolutionResult) *InstallationPlan {
	desktop := c.Desktop.Environment
	if desktop == "" {
		desktop = "none"
	}
	hw := selectedHardware(c.Hardware)
	kernel := c.System.Kernel
	if kernel == "" {
		kernel = "linux"
	}
	shellType := c.Shell.Type
	if shellType == "" {
		shellType = "bash"
	}
	sources := map[string]bool{"arch": true, "aur": false,
		"flatpak": false, "appimage": false}
	for k, v := range c.Sources {
		sources[k] = v
	}
	p := &InstallationPlan{
		Version:      "1",
		Distribution: "arch",
		Architecture: "x86_64",
		Init:         "systemd",
		Kernel:       kernel,
		BasePackages: kernelPackages(kernel),
		Packages:     res.Packages,
		Services:     res.Services,
		Filesystem:   c.Filesystem.Type,
		Bootloader:   c.Bootloader.Type,
		Shell:        shellType,
		Desktop:      desktop,
		Roles:        c.Roles,
		Hardware:     hw,
		Sources:      sources,
	}
	if p.Filesystem == "" {
		p.Filesystem = "ext4"
	}
	if p.Bootloader == "" {
		p.Bootloader = "systemd-boot"
	}
	if res.DisplayProtocol != "" {
		p.Display = res.DisplayProtocol
	}
	if lm := deriveLoginManager(desktop, c.Desktop.LoginManager); lm != "" {
		p.LoginManager = lm
	}
	// Route AUR/Flatpak packages to their dedicated lists based on the
	// source field of the originating profile, so the executor knows
	// which install backend to use.
	pkgSource := map[string]string{}
	for _, sel := range res.Selected {
		if sel.Source == "aur" || sel.Source == "flatpak" {
			for _, sp := range sel.Packages {
				pkgSource[sp] = sel.Source
			}
		}
	}
	for _, pkg := range res.Packages {
		switch {
		case strings.HasPrefix(pkg, "aur:"):
			name := strings.TrimPrefix(pkg, "aur:")
			if !contains(p.AURPackages, name) {
				p.AURPackages = append(p.AURPackages, name)
			}
		case strings.HasPrefix(pkg, "flatpak:"):
			name := strings.TrimPrefix(pkg, "flatpak:")
			if !contains(p.FlatpakPackages, name) {
				p.FlatpakPackages = append(p.FlatpakPackages, name)
			}
		case pkgSource[pkg] == "aur":
			if !contains(p.AURPackages, pkg) {
				p.AURPackages = append(p.AURPackages, pkg)
			}
		case pkgSource[pkg] == "flatpak":
			if !contains(p.FlatpakPackages, pkg) {
				p.FlatpakPackages = append(p.FlatpakPackages, pkg)
			}
		default:
			if !contains(p.Packages, pkg) {
				p.Packages = append(p.Packages, pkg)
			}
		}
	}
	return p
}

// HardwareResult mirrors the JSON output of bin/modular-detect.
type HardwareResult struct {
	CPU struct {
		Present bool   `json:"present"`
		Model   string `json:"model"`
		Vendor  string `json:"vendor"`
		Cores   int    `json:"cores"`
	} `json:"cpu"`
	Memory struct {
		TotalMB *int `json:"total_mb"`
	} `json:"memory"`
	GPU []struct {
		ID     string `json:"id"`
		Vendor string `json:"vendor"`
	} `json:"gpu"`
	Storage []struct {
		Name   string `json:"name"`
		SizeGB int64  `json:"size_gb"`
		Model  string `json:"model"`
	} `json:"storage"`
	Network struct {
		Ethernet bool `json:"ethernet"`
		Wifi     bool `json:"wifi"`
	} `json:"network"`
	Bluetooth bool `json:"bluetooth"`
	Audio     bool `json:"audio"`
	Webcam    bool `json:"webcam"`
	Touchpad  bool `json:"touchpad"`
}

func DetectHardware(binPath string) (*HardwareResult, error) {
	if binPath == "" {
		exe, _ := os.Executable()
		candidate := filepath.Join(filepath.Dir(exe), "..", "..", "bin", "modular-detect")
		if _, err := os.Stat(candidate); err == nil {
			binPath = candidate
		} else if _, err2 := os.Stat("bin/modular-detect"); err2 == nil {
			binPath = "bin/modular-detect"
		}
	}
	out, err := runCommand(binPath)
	if err != nil {
		return nil, fmt.Errorf("modular-detect failed: %w", err)
	}
	var hw HardwareResult
	if err := json.Unmarshal(out, &hw); err != nil {
		return nil, fmt.Errorf("invalid JSON from modular-detect: %w", err)
	}
	return &hw, nil
}

func defaultProfilesDir() string {
	if v := os.Getenv("MODULAR_PROFILES"); v != "" {
		return v
	}
	exe, _ := os.Executable()
	candidate := filepath.Join(filepath.Dir(exe), "..", "..", "profiles")
	if info, err := os.Stat(candidate); err == nil && info.IsDir() {
		return candidate
	}
	return "profiles"
}
