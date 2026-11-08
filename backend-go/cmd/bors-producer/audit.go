package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"borsterminal/backend/internal/codal"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/snapshot"
	"borsterminal/backend/internal/sync"
)

func runAudit(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		printAuditHelp(stdout)
		return 0
	}

	sub := args[0]
	rest := args[1:]

	switch sub {
	case "universe":
		return runAuditUniverse(ctx, rest, stdout, stderr)
	case "key":
		return runAuditKey(ctx, rest, stdout, stderr)
	case "help", "-h", "--help":
		printAuditHelp(stdout)
		return 0
	default:
		fmt.Fprintf(stderr, "unknown audit subcommand %q\nRun 'bors-producer audit help' for usage.\n", sub)
		return 1
	}
}

func printAuditHelp(w io.Writer) {
	help := `Usage: bors-producer audit <subcommand> [flags]

Subcommands:
  universe  Comprehensive data coverage and anomaly audit across market universe
  key       Cryptographic validation that signing key matches client UPDATE_PUBKEY

Flags for 'universe':
  --data-dir=PATH  Directory containing database files (default: .)
  --out=PATH       Optional path to write detailed JSON report

Flags for 'key':
  --pubkey=STR     Expected public key (default: built-in DefaultUpdatePubKey)
`
	fmt.Fprint(w, help)
}

func runAuditUniverse(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if err := checkSensitiveCLIArgs(args, stderr); err != nil {
		return 1
	}

	fs := flag.NewFlagSet("audit universe", flag.ContinueOnError)
	fs.SetOutput(stderr)
	dataDirFlag := fs.String("data-dir", ".", "Directory containing database files")
	outFlag := fs.String("out", "", "Path to write JSON audit report (optional)")

	if err := fs.Parse(args); err != nil {
		return 1
	}

	dataDir := *dataDirFlag
	marketPath := filepath.Join(dataDir, "market.db")
	dbConn, err := db.OpenRWC(marketPath)
	if err != nil {
		fmt.Fprintf(stderr, "failed to open %s: %v\n", marketPath, err)
		return 1
	}
	defer dbConn.Close()

	report, err := codal.AuditMarketUniverse(ctx, dbConn)
	if err != nil {
		fmt.Fprintf(stderr, "audit failed: %v\n", err)
		return 1
	}

	fmt.Fprintln(stdout, "================================================================================")
	fmt.Fprintln(stdout, "                    BorsTerminal Market Universe Audit Report                   ")
	fmt.Fprintln(stdout, "================================================================================")
	fmt.Fprintf(stdout, "  Instruments Total:       %d (Active / Traded: %d, Sectors: %d)\n", report.InstrumentCount, report.ActiveInstruments, report.SectorCount)
	fmt.Fprintf(stdout, "  TSETMC Market Watch:     %d rows\n", report.MarketWatchCount)
	fmt.Fprintf(stdout, "  Client Type:             %d live rows, %d historical value points\n", report.ClientTypeCount, report.ClientTypeValueCount)
	fmt.Fprintf(stdout, "  Corporate Actions:       %d price adjust, %d share change (%d symbols)\n", report.PriceAdjustEventsCount, report.ShareChangeEventsCount, report.CorporateSymbolsCovered)
	fmt.Fprintf(stdout, "  CODAL Notices:           %d total (%d statements, %d monthly sales)\n", report.CodalNoticesTotal, report.CodalStatementsTotal, report.CodalMonthlyTotal)
	fmt.Fprintf(stdout, "  Quarantined Records:     %d records\n", report.QuarantineCount)
	for reason, count := range report.QuarantineErrors {
		fmt.Fprintf(stdout, "    - %s: %d\n", reason, count)
	}
	fmt.Fprintf(stdout, "  Duplicate Notices:       %d duplicate records across %d tracing numbers\n", report.DuplicateNoticesCount, len(report.DuplicateTracingNos))
	fmt.Fprintf(stdout, "  FTS Recalculation:       %d total evaluated (%d PASS, %d MARGINAL, %d FAIL)\n", report.FTSResultsCount, report.FTSPassCount, report.FTSMarginalCount, report.FTSFailCount)
	fmt.Fprintf(stdout, "  Detected Data Anomalies: %d\n", len(report.DataAnomalies))
	for i, anomaly := range report.DataAnomalies {
		if i >= 10 {
			fmt.Fprintf(stdout, "    ... and %d more anomalies\n", len(report.DataAnomalies)-10)
			break
		}
		fmt.Fprintf(stdout, "    [%d] %s\n", i+1, anomaly)
	}
	fmt.Fprintln(stdout, "================================================================================")

	if *outFlag != "" {
		outPath := *outFlag
		if err := os.MkdirAll(filepath.Dir(outPath), 0755); err != nil && filepath.Dir(outPath) != "." {
			fmt.Fprintf(stderr, "failed to create directory for %s: %v\n", outPath, err)
			return 1
		}
		jsonData, err := json.MarshalIndent(report, "", "  ")
		if err != nil {
			fmt.Fprintf(stderr, "failed to serialize JSON report: %v\n", err)
			return 1
		}
		if err := os.WriteFile(outPath, jsonData, 0644); err != nil {
			fmt.Fprintf(stderr, "failed to write report to %s: %v\n", outPath, err)
			return 1
		}
		fmt.Fprintf(stdout, "Audit report JSON written to %s\n", outPath)
	}

	return 0
}

func runAuditKey(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if err := checkSensitiveCLIArgs(args, stderr); err != nil {
		return 1
	}

	fs := flag.NewFlagSet("audit key", flag.ContinueOnError)
	fs.SetOutput(stderr)
	pubKeyFlag := fs.String("pubkey", sync.DefaultUpdatePubKey, "Expected Minisign public key string")

	if err := fs.Parse(args); err != nil {
		return 1
	}

	privKeyStr := getMinisignSecretKey()
	if strings.TrimSpace(privKeyStr) == "" {
		fmt.Fprintf(stderr, "error: BORS_MINISIGN_SECRET_KEY, MINISIGN_SECRET_KEY, or BORS_MINISIGN_KEY_FILE is required\n")
		return 1
	}
	password := getMinisignPassword()

	priv, err := snapshot.ParsePrivateKey(privKeyStr, password)
	if err != nil {
		fmt.Fprintf(stderr, "error parsing/decrypting secret key: %v\n", err)
		return 1
	}

	pub, err := snapshot.ParsePublicKey(*pubKeyFlag)
	if err != nil {
		fmt.Fprintf(stderr, "error parsing public key: %v\n", err)
		return 1
	}

	if priv.ID() != pub.ID() {
		fmt.Fprintf(stderr, "Key ID mismatch: secret=%X pubkey=%X\n", priv.ID(), pub.ID())
		return 1
	}

	// Test sign & verify a cryptographic block
	tmpDir, err := os.MkdirTemp("", "keyaudit_*")
	if err != nil {
		fmt.Fprintf(stderr, "create tmp dir: %v\n", err)
		return 1
	}
	defer os.RemoveAll(tmpDir)

	testFile := filepath.Join(tmpDir, "test.bin")
	if err := os.WriteFile(testFile, []byte("BorsTerminal Stage 4 Key Audit Validation Payload"), 0600); err != nil {
		fmt.Fprintf(stderr, "write test file: %v\n", err)
		return 1
	}

	sigFile, err := snapshot.SignAsset(testFile, privKeyStr, password)
	if err != nil {
		fmt.Fprintf(stderr, "sign asset failed: %v\n", err)
		return 1
	}

	if err := snapshot.VerifyAsset(testFile, sigFile, *pubKeyFlag); err != nil {
		fmt.Fprintf(stderr, "verification failed against expected public key: %v\n", err)
		return 1
	}

	fmt.Fprintf(stdout, "::notice::[key-audit] Secret key mathematically matches client UPDATE_PUBKEY (KeyID: %X). Zero secret values exposed.\n", priv.ID())
	fmt.Fprintf(stdout, "KEY AUDIT PASS: KeyID %X matches public key\n", priv.ID())
	return 0
}
