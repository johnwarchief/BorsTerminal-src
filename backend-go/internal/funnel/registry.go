package funnel

import (
	_ "embed"
	"encoding/json"
)

//go:embed registry.json
var registryJSON []byte

// RegistryPayload بازگرداندن داده‌های رجیستری فیلترها و پیش‌تنظیم‌های قیف FTS.
func RegistryPayload() (map[string]any, error) {
	var m map[string]any
	if err := json.Unmarshal(registryJSON, &m); err != nil {
		return nil, err
	}
	return m, nil
}

// RegistryRawBytes بازگرداندن بایت‌های خام رجیستری جهت پاسخ مستقیم HTTP سریع.
func RegistryRawBytes() []byte {
	return registryJSON
}
