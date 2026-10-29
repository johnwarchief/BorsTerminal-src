package config

import (
	"flag"
	"path/filepath"
	"strconv"
)

const DefaultPort = 8198

type Config struct {
	Addr     string
	DataDir  string
	ReadOnly bool
	NoLoops  bool
}

func Load(args []string, getenv func(string) string) (Config, error) {
	fs := flag.NewFlagSet("borsd", flag.ContinueOnError)
	port := fs.Int("port", DefaultPort, "listen port on 127.0.0.1")
	dir := fs.String("db-dir", "", "directory holding market.db/user.db (default: BORS_DATA_DIR or .)")
	ro := fs.Bool("read-only", true, "open market.db read-only (phase A; default)")
	rw := fs.Bool("read-write", false, "turn read-only off; market.db becomes writable (not phase A)")
	noLoops := fs.Bool("no-loops", false, "do not start sync/fetch loops")
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
	return Config{
		Addr:     "127.0.0.1:" + strconv.Itoa(*port),
		DataDir:  abs,
		ReadOnly: *ro && !*rw,
		NoLoops:  *noLoops,
	}, nil
}

func (c Config) MarketDB() string { return filepath.Join(c.DataDir, "market.db") }
func (c Config) UserDB() string   { return filepath.Join(c.DataDir, "user.db") }
