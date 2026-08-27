package main

import (
	"strings"
	"testing"
)

func testRegistry(t *testing.T) *Registry {
	t.Helper()
	reg := NewRegistry()
	if err := reg.LoadDirectory("../../profiles"); err != nil {
		t.Fatalf("load profiles: %v", err)
	}
	if !reg.Has("base.arch") {
		t.Fatal("base.arch missing")
	}
	return reg
}

func TestResolveKdeWithWifiAudio(t *testing.T) {
	reg := testRegistry(t)
	res, err := NewResolver(reg).Resolve("desktop.kde",
		[]string{"hardware.wifi", "hardware.audio"}, []string{"app.firefox"}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if !contains(res.Packages, "plasma") || !contains(res.Packages, "firefox") {
		t.Errorf("expected plasma+firefox, got %v", res.Packages)
	}
	if !contains(res.Packages, "networkmanager") {
		t.Errorf("wifi should pull networkmanager transitively")
	}
	if !contains(res.Services, "NetworkManager") || !contains(res.Services, "sddm") {
		t.Errorf("services wrong: %v", res.Services)
	}
	if res.DisplayProtocol != "wayland" {
		t.Errorf("expected wayland display")
	}
}

func TestResolveWMAndRole(t *testing.T) {
	reg := testRegistry(t)
	res, err := NewResolver(reg).Resolve("wm.sway",
		[]string{"hardware.audio"}, []string{"app.firefox"}, []string{"role.developer"})
	if err != nil {
		t.Fatal(err)
	}
	if !contains(res.Packages, "sway") || !contains(res.Packages, "rustup") {
		t.Errorf("expected sway + developer tooling, got %v", res.Packages)
	}
}

func TestResolveGPUNvidiaConflict(t *testing.T) {
	reg := testRegistry(t)
	_, err := NewResolver(reg).Resolve("",
		[]string{"gpu.nvidia", "gpu.nouveau"}, nil, nil)
	if err == nil || !strings.Contains(err.Error(), "conflict") {
		t.Errorf("expected nvidia/nouveau conflict, got %v", err)
	}
}

func TestResolveDeduplicates(t *testing.T) {
	reg := testRegistry(t)
	res, err := NewResolver(reg).Resolve("desktop.kde",
		[]string{"hardware.wifi", "hardware.network"}, nil, nil)
	if err != nil {
		t.Fatal(err)
	}
	seen := map[string]bool{}
	for _, p := range res.Packages {
		if seen[p] {
			t.Errorf("duplicate package %s", p)
		}
		seen[p] = true
	}
}

func TestUnknownProfile(t *testing.T) {
	reg := testRegistry(t)
	_, err := NewResolver(reg).Resolve("doesnotexist", nil, nil, nil)
	if err == nil || !strings.Contains(err.Error(), "unknown profile") {
		t.Errorf("expected unknown profile error, got %v", err)
	}
}

func TestCycleDetection(t *testing.T) {
	reg := NewRegistry()
	reg.profiles["a.x"] = &Profile{ID: "a.x", Name: "X", Category: "base", Requires: []string{"a.y"}}
	reg.profiles["a.y"] = &Profile{ID: "a.y", Name: "Y", Category: "base", Requires: []string{"a.x"}}
	_, err := NewResolver(reg).Resolve("a.x", nil, nil, nil)
	if err == nil || !strings.Contains(err.Error(), "cycle") {
		t.Errorf("expected cycle error, got %v", err)
	}
}

func TestConflictDetection(t *testing.T) {
	reg := NewRegistry()
	reg.profiles["desktop.one"] = &Profile{ID: "desktop.one", Name: "One", Category: "desktop",
		Conflicts: []string{"desktop.two"}}
	reg.profiles["desktop.two"] = &Profile{ID: "desktop.two", Name: "Two", Category: "desktop"}
	_, err := NewResolver(reg).Resolve("desktop.one", nil, []string{"desktop.two"}, nil)
	if err == nil || !strings.Contains(err.Error(), "conflict") {
		t.Errorf("expected conflict error, got %v", err)
	}
}

func TestValidateAndPlan(t *testing.T) {
	reg := testRegistry(t)
	cfgYaml := `
version: 1
base:
  distribution: arch
system:
  architecture: x86_64
  kernel: linux-zen
  init: systemd
desktop:
  environment: kde
  display: automatic
roles:
  - developer
hardware:
  wifi: true
  audio: true
applications:
  - firefox
filesystem:
  type: ext4
bootloader:
  type: systemd-boot
`
	dir := t.TempDir()
	path := dir + "/modular.yaml"
	if err := writeFile(path, cfgYaml); err != nil {
		t.Fatal(err)
	}
	cfg, err := LoadConfig(path)
	if err != nil {
		t.Fatal(err)
	}
	if errs := Validate(cfg, reg); len(errs) != 0 {
		t.Fatalf("unexpected validation errors: %v", errs)
	}
	hw := hardwareBools(cfg.Hardware)
	res, err := NewResolver(reg).Resolve("desktop.kde", hw,
		cfg.Applications, cfg.Roles)
	if err != nil {
		t.Fatal(err)
	}
	plan := BuildPlan(cfg, res)
	if plan.Filesystem != "ext4" || plan.Bootloader != "systemd-boot" {
		t.Errorf("plan defaults wrong: %+v", plan)
	}
	if plan.Kernel != "linux-zen" || plan.BasePackages[1] != "linux-zen" {
		t.Errorf("kernel selection failed: %v", plan.BasePackages)
	}
	if plan.LoginManager != "sddm" {
		t.Errorf("login manager derivation failed: %v", plan.LoginManager)
	}
	if len(plan.Roles) != 1 || plan.Roles[0] != "developer" {
		t.Errorf("roles not propagated: %v", plan.Roles)
	}
	if !contains(plan.Packages, "firefox") {
		t.Errorf("plan missing firefox")
	}
	if !contains(plan.BasePackages, "sudo") {
		t.Errorf("plan missing base packages")
	}
}

func TestKernelSelection(t *testing.T) {
	_ = testRegistry(t)
	cfg := &Config{}
	cfg.Version = 1
	cfg.System.Kernel = "linux-zen"
	plan := kernelPackages("linux-zen")
	if plan[1] != "linux-zen" || len(plan) != 4 {
		t.Errorf("kernel swap failed: %v", plan)
	}
}

func TestInvalidConfigRejected(t *testing.T) {
	reg := testRegistry(t)
	cfg := &Config{}
	cfg.Version = 0.2
	cfg.Base.Distribution = "debian"
	cfg.Desktop.Environment = "trinity"
	cfg.Shell.Type = "csh"
	errs := Validate(cfg, reg)
	if len(errs) < 3 {
		t.Errorf("expected >=3 errors, got %v", errs)
	}
}
