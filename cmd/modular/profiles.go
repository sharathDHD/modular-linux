package main

import (
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// Profile mirrors a YAML profile definition (spec §9-§11).
type Services struct {
	Enable  []string `yaml:"enable"`
	Disable []string `yaml:"disable"`
}

type Profile struct {
	ID          string    `yaml:"id"`
	Name        string    `yaml:"name"`
	Category    string    `yaml:"category"`
	Description string    `yaml:"description"`
	Packages    []string  `yaml:"packages"`
	Requires    []string  `yaml:"requires"`
	Conflicts   []string  `yaml:"conflicts"`
	Services    *Services `yaml:"services"`
	Display     struct {
		Protocol string `yaml:"protocol"`
	} `yaml:"display"`
	Source string `yaml:"source"`
	Group  string `yaml:"-"`
}

type Registry struct {
	profiles map[string]*Profile
}

func NewRegistry() *Registry {
	return &Registry{profiles: map[string]*Profile{}}
}

func (r *Registry) LoadDirectory(root string) error {
	cats, err := os.ReadDir(root)
	if err != nil {
		return fmt.Errorf("profile directory: %w", err)
	}
	for _, cat := range cats {
		if !cat.IsDir() {
			continue
		}
		catDir := filepath.Join(root, cat.Name())
		entries, err := os.ReadDir(catDir)
		if err != nil {
			continue
		}
		for _, e := range entries {
			name := e.Name()
			if filepath.Ext(name) != ".yaml" && filepath.Ext(name) != ".yml" {
				continue
			}
			path := filepath.Join(catDir, name)
			p, err := loadProfile(path, cat.Name())
			if err != nil {
				return err
			}
			if _, dup := r.profiles[p.ID]; dup {
				return fmt.Errorf("duplicate profile id '%s' (%s)", p.ID, path)
			}
			r.profiles[p.ID] = p
		}
	}
	return nil
}

func loadProfile(path, group string) (*Profile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var p Profile
	if err := yaml.Unmarshal(data, &p); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	if p.ID == "" || p.Name == "" || p.Category == "" {
		return nil, fmt.Errorf("%s: profile must define id, name and category", path)
	}
	p.Group = group
	return &p, nil
}

func (r *Registry) Get(id string) (*Profile, error) {
	p, ok := r.profiles[id]
	if !ok {
		return nil, fmt.Errorf("unknown profile: %s", id)
	}
	return p, nil
}

func (r *Registry) Has(id string) bool {
	_, ok := r.profiles[id]
	return ok
}

func (r *Registry) ByGroup(group string) []*Profile {
	var out []*Profile
	for _, p := range r.profiles {
		if p.Group == group {
			out = append(out, p)
		}
	}
	sortProfiles(out)
	return out
}

func (r *Registry) All() []*Profile {
	out := make([]*Profile, 0, len(r.profiles))
	for _, p := range r.profiles {
		out = append(out, p)
	}
	sortProfiles(out)
	return out
}

func (p *Profile) enableServices() []string {
	if p.Services == nil {
		return nil
	}
	return p.Services.Enable
}
