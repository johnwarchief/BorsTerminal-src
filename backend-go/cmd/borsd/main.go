package main

import (
	"log"
	"os"

	"borsterminal/backend/internal/config"
)

var version = "dev"

func main() {
	cfg, err := config.Load(os.Args[1:], os.Getenv)
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("borsd %s data=%s addr=%s", version, cfg.DataDir, cfg.Addr)
}
