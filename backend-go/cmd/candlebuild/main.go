// Command candlebuild materializes adjusted_candles and adjustment_verification
// from reference_raw + adjustment_factors in the Phase 4.9.2 candle DB.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"borsterminal/backend/internal/candlebuild"
	"borsterminal/backend/internal/db"
)

func main() {
	dbPath := flag.String("db", "", "path to the market.db carrying reference_raw and adjustment_factors")
	flag.Parse()
	if *dbPath == "" {
		fmt.Fprintln(os.Stderr, "candlebuild: --db is required")
		os.Exit(2)
	}
	conn, err := db.OpenRW(*dbPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "candlebuild: cannot open db:", err)
		os.Exit(1)
	}
	defer conn.Close()
	res, err := candlebuild.Build(conn)
	if err != nil {
		fmt.Fprintln(os.Stderr, "candlebuild:", err)
		os.Exit(1)
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", " ")
	if err := enc.Encode(res); err != nil {
		fmt.Fprintln(os.Stderr, "candlebuild: encode:", err)
		os.Exit(1)
	}
}
