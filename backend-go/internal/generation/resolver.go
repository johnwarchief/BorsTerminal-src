// Package generation مسیرِ دیتابیس‌هایِ نسل فعال را از active_generation.json
// حل می‌کند. borsd پیش از این همیشه dataDir/market.db را باز می‌کرد و اسنپ‌شاتِ
// اعمال‌شده (gens/gen_*) تا ری‌استارتِ دستی دیده نمی‌شد؛ این بسته همان شکافِ P0.1
// را می‌بندد: نسلِ فعال یک قراردادِ فایل است، نه یک حدس.
package generation

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const PointerFile = "active_generation.json"

// ErrInvalidPointer یعنی فایلِ اشاره‌گر هست ولی سالم نیست. در این حالت هرگز
// به dataDir/legacy برنمی‌گردیم: سرو کردنِ دادهٔ قدیمی بی‌برچسب، همان «پاسِ
// جعلی» است که معماری منع می‌کند.
var ErrInvalidPointer = errors.New("active_generation.json is invalid")

// Pointer عینِ قراردادِ snapshot.GenerationPointer است؛ این‌جا فقط خوانده می‌شود
// تا resolver به کلیدِ امضا/Applier وابسته نشود.
type Pointer struct {
	SnapshotSetID         string `json:"snapshot_set_id"`
	GenerationDir         string `json:"generation_dir"`
	AppliedAtUTC          string `json:"applied_at_utc"`
	SchemaVersion         int    `json:"schema_version"`
	PreviousSnapshotSetID string `json:"previous_snapshot_set_id,omitempty"`
	PreviousGenerationDir string `json:"previous_generation_dir,omitempty"`
}

// Info مسیرهایِ حل‌شده برایِ باز کردنِ دیتابیس‌هاست.
type Info struct {
	DataDir       string
	Active        bool
	Pointer       *Pointer
	GenerationDir string // absolute; "" در حالت legacy
	MarketPath    string
	CodalPath     string // "" یعنی در این نسل codal.db نیست
	UserDir       string // user.db همیشه در dataDir می‌ماند
}

// Identity کلیدِ تعویضِ اتمیک است؛ legacy و هر نسل شناسهٔ جدا دارد.
func (i Info) Identity() string {
	if i.Active && i.Pointer != nil {
		return "gen:" + i.Pointer.SnapshotSetID
	}
	return "legacy"
}

type Resolver struct {
	dataDir string
}

func New(dataDir string) *Resolver {
	abs, err := filepath.Abs(dataDir)
	if err != nil {
		abs = dataDir
	}
	return &Resolver{dataDir: abs}
}

func (r *Resolver) DataDir() string { return r.dataDir }

// Resolve:
//   - نبودِ اشاره‌گر ⇒ legacy (dataDir/market.db و dataDir/codal.db)، Active=false.
//   - اشاره‌گرِ خراب/ناقص/بدونِ دایرکتوری/بدونِ market.db ⇒ ErrInvalidPointer.
//   - اشاره‌گرِ سالم ⇒ market/codal از gens/gen_* و user.db از dataDir.
//
// codal.db در نسل غایب باشد، CodalPath تهی می‌ماند و به legacy قاطی نمی‌شود؛
// ترکیبِ دو نسل در یک درخواست ممنوع است.
func (r *Resolver) Resolve() (Info, error) {
	info := Info{
		DataDir:    r.dataDir,
		UserDir:    r.dataDir,
		MarketPath: filepath.Join(r.dataDir, "market.db"),
		CodalPath:  filepath.Join(r.dataDir, "codal.db"),
	}

	raw, err := os.ReadFile(filepath.Join(r.dataDir, PointerFile))
	if errors.Is(err, os.ErrNotExist) {
		return info, nil
	}
	if err != nil {
		return Info{}, fmt.Errorf("%w: read: %v", ErrInvalidPointer, err)
	}

	var p Pointer
	if err := json.Unmarshal(raw, &p); err != nil {
		return Info{}, fmt.Errorf("%w: unmarshal: %v", ErrInvalidPointer, err)
	}
	if strings.TrimSpace(p.SnapshotSetID) == "" {
		return Info{}, fmt.Errorf("%w: snapshot_set_id is empty", ErrInvalidPointer)
	}
	if strings.TrimSpace(p.GenerationDir) == "" {
		return Info{}, fmt.Errorf("%w: generation_dir is empty", ErrInvalidPointer)
	}
	if p.SchemaVersion < 1 {
		return Info{}, fmt.Errorf("%w: schema_version %d is invalid", ErrInvalidPointer, p.SchemaVersion)
	}

	genDir := p.GenerationDir
	if !filepath.IsAbs(genDir) {
		genDir = filepath.Join(r.dataDir, filepath.FromSlash(genDir))
	}
	// اشاره‌گر یک فایلِ محلی است، ولی مسیرش نباید از dataDir بیرون بزند:
	// نسل فقط از gens/ همین نصب خوانده می‌شود، نه از یک مسیرِ دلخواه.
	if !within(r.dataDir, genDir) {
		return Info{}, fmt.Errorf("%w: generation_dir %s escapes data dir", ErrInvalidPointer, genDir)
	}
	fi, err := os.Stat(genDir)
	if err != nil || !fi.IsDir() {
		return Info{}, fmt.Errorf("%w: generation_dir %s is not a directory", ErrInvalidPointer, genDir)
	}

	marketPath := filepath.Join(genDir, "market.db")
	if fi, err := os.Stat(marketPath); err != nil || fi.IsDir() {
		return Info{}, fmt.Errorf("%w: generation %s has no market.db", ErrInvalidPointer, p.SnapshotSetID)
	}
	codalPath := filepath.Join(genDir, "codal.db")
	if fi, err := os.Stat(codalPath); err != nil || fi.IsDir() {
		codalPath = ""
	}

	ptr := p
	info.Active = true
	info.Pointer = &ptr
	info.GenerationDir = genDir
	info.MarketPath = marketPath
	info.CodalPath = codalPath
	return info, nil
}

// within می‌گوید path داخل base است (بعد از پاک‌سازیِ مسیر).
func within(base, path string) bool {
	rel, err := filepath.Rel(base, path)
	if err != nil {
		return false
	}
	return rel == "." || (rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator)))
}

// CurrentPointer فایلِ اشاره‌گر روی دیسک را (حتی اگر instance هنوز آن را
// بارگذاری نکرده باشد) می‌خواند؛ برایِ وضعیتِ صادقانهٔ apply-بدون-reload.
func (r *Resolver) CurrentPointer() (*Pointer, error) {
	raw, err := os.ReadFile(filepath.Join(r.dataDir, PointerFile))
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var p Pointer
	if err := json.Unmarshal(raw, &p); err != nil {
		return nil, fmt.Errorf("%w: unmarshal: %v", ErrInvalidPointer, err)
	}
	return &p, nil
}
