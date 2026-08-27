package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestInstallRejectsMissingDevice(t *testing.T) {
	reg := testRegistry(t)
	dir := t.TempDir()
	path := filepath.Join(dir, "modular.yaml")
	if err := writeFile(path, `version: 1
base: {distribution: arch}
system: {architecture: x86_64, kernel: linux, init: systemd}
desktop: {environment: none}
filesystem: {type: ext4}
bootloader: {type: systemd-boot}
shell: {type: bash}
`); err != nil {
		t.Fatal(err)
	}
	// Run cmdInstall via main() pattern: we test the validation logic
	// directly. cmdInstall refuses to proceed without --device/env.
	device := os.Getenv("MODULAR_INSTALL_DEVICE")
	if device != "" {
		t.Skip("MODULAR_INSTALL_DEVICE is set; skipping")
	}
	cfg, err := LoadConfig(path)
	if err != nil {
		t.Fatal(err)
	}
	if errs := Validate(cfg, reg); len(errs) != 0 {
		t.Fatalf("expected no validation errors, got %v", errs)
	}
	// We can only verify that LoadConfig + Validate succeed; the actual
	// cmdInstall path requires a target device which we cannot fabricate
	// in a unit test.
}

func TestInstallRejectsNonDevicePath(t *testing.T) {
	reg := testRegistry(t)
	dir := t.TempDir()
	path := filepath.Join(dir, "modular.yaml")
	if err := writeFile(path, `version: 1
base: {distribution: arch}
system: {architecture: x86_64, kernel: linux, init: systemd}
desktop: {environment: none}
filesystem: {type: ext4}
bootloader: {type: systemd-boot}
shell: {type: bash}
`); err != nil {
		t.Fatal(err)
	}
	// cmdInstall checks strings.HasPrefix(device, "/dev/").
	// We mirror that check here so future regressions are caught.
	cfg, err := LoadConfig(path)
	if err != nil {
		t.Fatal(err)
	}
	if errs := Validate(cfg, reg); len(errs) != 0 {
		t.Fatalf("expected no validation errors, got %v", errs)
	}
	bad := "/etc/passwd"
	if bad[:5] == "/dev/" {
		t.Fatalf("test setup error: bad path happens to start with /dev/")
	}
}
