package httpapi

import (
	_ "embed"
	"encoding/json"
)

//go:embed routes.json
var routesJSON []byte

var routeSet map[string]struct{}

func init() {
	var list []string
	if err := json.Unmarshal(routesJSON, &list); err != nil {
		panic("routes.json: " + err.Error())
	}
	routeSet = make(map[string]struct{}, len(list))
	for _, r := range list {
		routeSet[r] = struct{}{}
	}
}

func Routes() []string {
	var list []string
	for r := range routeSet {
		list = append(list, r)
	}
	for i := 1; i < len(list); i++ {
		for j := i; j > 0 && list[j] < list[j-1]; j-- {
			list[j], list[j-1] = list[j-1], list[j]
		}
	}
	return list
}
