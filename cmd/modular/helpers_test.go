package main

import "os"

func writeFile(path, content string) error {
	return os.WriteFile(path, []byte(content), 0644)
}

func hardwareBools(hw map[string]any) []string {
	var out []string
	for k, v := range hw {
		if b, ok := v.(bool); ok && b {
			out = append(out, k)
		}
	}
	return out
}
