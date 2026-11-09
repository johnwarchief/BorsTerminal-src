package config

import (
	"flag"
	"os"
	"path/filepath"
	"strconv"
)

const DefaultPort = 8198

type Config struct {
	Addr         string
	DataDir      string
	CalendarPath string
	StaticDir    string
	ReadOnly     bool
	NoLoops      bool
	NoShell      bool
	// Port is the actual bound port (set by main after Listen). The in-app
	// updater needs it to health-check the restarted process.
	Port int
	// Args is the original CLI, replayed when the updater restarts the app.
	Args []string
	// Shutdown gracefully stops the process; the updater calls it after the
	// detached watcher has started.
	Shutdown func()
}

func Load(args []string, getenv func(string) string) (Config, error) {
	fs := flag.NewFlagSet("borsd", flag.ContinueOnError)
	port := fs.Int("port", DefaultPort, "listen port on 127.0.0.1")
	dir := fs.String("db-dir", "", "directory holding market.db/user.db (default: BORS_DATA_DIR or .)")
	staticDirArg := fs.String("static-dir", "", "directory holding frontend static assets (default: auto-detected)")
	ro := fs.Bool("read-only", true, "open market.db read-only (phase A; default)")
	rw := fs.Bool("read-write", false, "turn read-only off; market.db becomes writable (not phase A)")
	noLoops := fs.Bool("no-loops", false, "do not start sync/fetch loops")
	noShell := fs.Bool("no-shell", false, "do not launch desktop shell window")
	serverOnly := fs.Bool("server-only", false, "run HTTP server without desktop shell")
	if err := fs.Parse(args); err != nil {
		return Config{}, err
	}
	data := *dir
	if data == "" {
		data = getenv("BORS_DATA_DIR")
	}
	if data == "" {
		data = "."
	}
	abs, err := filepath.Abs(data)
	if err != nil {
		return Config{}, err
	}
	cal := getenv("BORS_CALENDAR_PATH")
	if cal == "" {
		cal = filepath.Join("static", "calendar", "cache.json")
	}
	calAbs, err := filepath.Abs(cal)
	if err != nil {
		return Config{}, err
	}

	// Auto-detect static frontend dir
	staticDir := *staticDirArg
	if staticDir == "" {
		staticDir = getenv("BORS_STATIC_DIR")
	}
	if staticDir == "" {
		candidates := []string{
			filepath.Join(abs, "frontend"),
			filepath.Join(".", "frontend"),
			filepath.Join(".", "frontend-v2", "dist"),
			filepath.Join("..", "frontend-v2", "dist"),
		}
		for _, c := range candidates {
			if info, err := os.Stat(filepath.Join(c, "index.html")); err == nil && !info.IsDir() {
				staticDir = c
				break
			}
		}
	}
	var staticAbs string
	if staticDir != "" {
		if sAbs, err := filepath.Abs(staticDir); err == nil {
			staticAbs = sAbs
		}
	}

	isNoShell := *noShell || *serverOnly || getenv("BORS_NO_SHELL") == "1" || getenv("BORS_SERVER_ONLY") == "1"

	return Config{
		Addr:         "127.0.0.1:" + strconv.Itoa(*port),
		DataDir:      abs,
		CalendarPath: calAbs,
		StaticDir:    staticAbs,
		ReadOnly:     *ro && !*rw,
		NoLoops:      *noLoops,
		NoShell:      isNoShell,
		Port:         *port,
		Args:         append([]string(nil), args...),
	}, nil
}

func (c Config) MarketDB() string { return filepath.Join(c.DataDir, "market.db") }
func (c Config) UserDB() string   { return filepath.Join(c.DataDir, "user.db") }
