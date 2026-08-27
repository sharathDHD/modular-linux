package main

import (
	"fmt"
	"sort"
	"strings"
)

// ResolutionResult mirrors engine.resolver.ResolutionResult.
type ResolutionResult struct {
	Selected        []*Profile
	Dependencies    map[string][]string
	Packages        []string
	Services        []string
	DisplayProtocol string
}

type Resolver struct {
	reg *Registry
}

func NewResolver(reg *Registry) *Resolver { return &Resolver{reg: reg} }

func qualify(name, prefix string) string {
	if strings.Contains(name, ".") {
		return name
	}
	return prefix + "." + name
}

// Resolve loads requested profiles plus transitive dependencies, merges and
// deduplicates packages/services, detects cycles (spec §32).
func (rs *Resolver) Resolve(desktop string, hardware, applications,
	roles []string) (*ResolutionResult, error) {
	var requested []string
	if desktop != "" && desktop != "none" {
		requested = append(requested, qualify(desktop, "desktop"))
	}
	for _, r := range roles {
		requested = append(requested, qualify(r, "role"))
	}
	for _, h := range hardware {
		requested = append(requested, qualify(h, "hardware"))
	}
	for _, a := range applications {
		requested = append(requested, qualify(a, "app"))
	}

	res := &ResolutionResult{Dependencies: map[string][]string{}}
	resolved := map[string]bool{}
	var visiting []string

	var visit func(id string) error
	visit = func(id string) error {
		if resolved[id] {
			return nil
		}
		for _, v := range visiting {
			if v == id {
				cycle := append(append([]string{}, visiting...), id)
				return fmt.Errorf("dependency cycle detected: %v", cycle)
			}
		}
		p, err := rs.reg.Get(id)
		if err != nil {
			return err
		}
		visiting = append(visiting, id)
		deps := []string{}
		for _, dep := range p.Requires {
			if err := visit(dep); err != nil {
				return err
			}
			deps = append(deps, dep)
		}
		visiting = visiting[:len(visiting)-1]
		resolved[id] = true
		res.Selected = append(res.Selected, p)
		res.Dependencies[id] = deps

		for _, pkg := range p.Packages {
			if !contains(res.Packages, pkg) {
				res.Packages = append(res.Packages, pkg)
			}
		}
		for _, svc := range p.enableServices() {
			if !contains(res.Services, svc) {
				res.Services = append(res.Services, svc)
			}
		}
		if p.Display.Protocol != "" {
			res.DisplayProtocol = p.Display.Protocol
		}
		return nil
	}

	if err := rs.checkConflicts(requested); err != nil {
		return nil, err
	}
	for _, id := range requested {
		if err := visit(id); err != nil {
			return nil, err
		}
	}
	sort.Strings(res.Packages)
	sort.Strings(res.Services)
	return res, nil
}

func (rs *Resolver) checkConflicts(requested []string) error {
	expanded := map[string]bool{}
	for _, id := range requested {
		expanded[id] = true
		p, err := rs.reg.Get(id)
		if err != nil {
			return err
		}
		for _, req := range p.Requires {
			expanded[req] = true
		}
	}
	for _, id := range requested {
		p, _ := rs.reg.Get(id)
		for _, c := range p.Conflicts {
			if contains(requested, c) || (expanded[c] && c != p.ID) {
				return fmt.Errorf("profile conflict: '%s' conflicts with '%s'", p.ID, c)
			}
		}
	}
	return nil
}

func contains(list []string, s string) bool {
	for _, x := range list {
		if x == s {
			return true
		}
	}
	return false
}

func sortProfiles(ps []*Profile) {
	sort.Slice(ps, func(i, j int) bool { return ps[i].ID < ps[j].ID })
}
