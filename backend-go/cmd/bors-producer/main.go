package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"syscall"
)

var version = "1.0.95"

// Version returns the current bors-producer binary version.
func Version() string {
	return version
}

// initLogging sets up the default slog structured logger based on level and format strings.
// Environment variables LOG_LEVEL and LOG_FORMAT take precedence when present and non-empty.
func initLogging(levelStr, formatStr string) {
	if envL := strings.TrimSpace(os.Getenv("LOG_LEVEL")); envL != "" {
		levelStr = envL
	}
	if envF := strings.TrimSpace(os.Getenv("LOG_FORMAT")); envF != "" {
		formatStr = envF
	}

	var level slog.Level
	switch strings.ToLower(strings.TrimSpace(levelStr)) {
	case "debug":
		level = slog.LevelDebug
	case "warn", "warning":
		level = slog.LevelWarn
	case "error":
		level = slog.LevelError
	default:
		level = slog.LevelInfo
	}

	opts := &slog.HandlerOptions{
		Level: level,
	}

	var handler slog.Handler
	if strings.EqualFold(strings.TrimSpace(formatStr), "json") {
		handler = slog.NewJSONHandler(os.Stderr, opts)
	} else {
		handler = slog.NewTextHandler(os.Stderr, opts)
	}

	slog.SetDefault(slog.New(handler))
}

var blockedFlags = map[string]struct{}{
	"--token":        {},
	"-token":         {},
	"--github-token": {},
	"-github-token":  {},
	"--key":          {},
	"-key":           {},
	"--secret-key":   {},
	"-secret-key":    {},
	"--private-key":  {},
	"-private-key":   {},
	"--minisign-key": {},
	"-minisign-key":  {},
	"--password":     {},
	"-password":      {},
}

// checkSensitiveCLIArgs scans arguments for sensitive credentials (tokens, private keys, passwords)
// and returns an error with an actionable message if any are found.
func checkSensitiveCLIArgs(args []string, stderr io.Writer) error {
	for _, arg := range args {
		lower := strings.ToLower(strings.TrimSpace(arg))
		flagName := lower
		if idx := strings.IndexAny(lower, "=:"); idx != -1 {
			flagName = lower[:idx]
		}
		if _, exists := blockedFlags[flagName]; exists {
			msg := "security error: passing sensitive credentials (tokens, private keys, passwords) via CLI arguments is strictly prohibited; use environment variables instead\n"
			if stderr != nil {
				fmt.Fprint(stderr, msg)
			}
			return errors.New(strings.TrimSpace(msg))
		}
	}
	return nil
}

func main() {
	initLogging(os.Getenv("LOG_LEVEL"), os.Getenv("LOG_FORMAT"))
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	code := Run(ctx, os.Args[1:], os.Stdout, os.Stderr)
	os.Exit(code)
}

// Run parses command-line arguments and dispatches to the appropriate subcommand.
// Returns an exit code: 0 for success, non-zero for error.
func Run(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	initLogging(os.Getenv("LOG_LEVEL"), os.Getenv("LOG_FORMAT"))
	if err := checkSensitiveCLIArgs(args, stderr); err != nil {
		return 1
	}

	if len(args) == 0 {
		printHelp(stdout)
		return 0
	}

	cmd := args[0]
	rest := args[1:]

	switch cmd {
	case "help", "-h", "--help":
		printHelp(stdout)
		return 0

	case "version", "-v", "--version":
		printVersion(stdout)
		return 0

	case "codal":
		return runCodal(ctx, rest, stdout, stderr)

	case "market":
		return runMarket(ctx, rest, stdout, stderr)

	case "audit":
		return runAudit(ctx, rest, stdout, stderr)

	case "daemon":
		return runDaemon(ctx, rest, stdout, stderr)

	default:
		fmt.Fprintf(stderr, "unknown command %q\nRun 'bors-producer help' for usage.\n", cmd)
		return 1
	}
}

func printVersion(w io.Writer) {
	fmt.Fprintf(w, "bors-producer version %s\n", Version())
}

func printHelp(w io.Writer) {
	helpText := `bors-producer - High-performance data producer CLI for BorsTerminal

Usage:
  bors-producer <command> [subcommand] [flags]

Available Commands:
  codal run       Discover, extract, validate, and ingest CODAL notices, then recalc dirty FTS
  codal backfill  Backfill pending/unprocessed notices from codal_notices
  codal recalc    Recalculate FTS 5-axis fundamental metrics (--all or --symbols)
  codal snapshot  Create compressed LZMA snapshots and manifest (signs if keys present)
  codal publish   Publish snapshot set to GitHub Release (requires GITHUB_TOKEN in env)
  market run      Ingest TSETMC market watch, client type history, and corporate events
  audit universe  Audit data coverage, anomalies, duplicate notices, and FTS statistics
  daemon          Run the background worker daemon orchestrating periodic tasks
  version         Print producer binary version
  help            Print this usage help message

Examples:
  bors-producer codal run --mode=update --data-dir=./data --limit=50
  bors-producer codal backfill --limit=100 --data-dir=./data
  bors-producer codal recalc --all --data-dir=./data
  bors-producer codal snapshot --data-dir=./data --out=dist/snapshots --tag=v1.0.95
  bors-producer codal publish --tag=v1.0.95 --manifest=dist/snapshots/manifest.json --repo=owner/repo
  bors-producer market run --data-dir=./data --history=true --events=true
  bors-producer audit universe --data-dir=./data --out=universe_report.json
  bors-producer daemon --config=producer_config.json --data-dir=./data
`
	fmt.Fprint(w, helpText)
}
