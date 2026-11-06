package db_test

import (
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestArchitectureNoDirectSQLOpen گیت معماری AST است که تضمین می‌کند:
// ۱. در تمام کدهای عملیاتی و پروداکشن (فایل‌های غیر تست)، فراخوانی مستقیم sql.Open یا sql.OpenDB
//    خارج از پکیج internal/db اکیداً ممنوع و صفر است.
// ۲. در فایل‌های تست نیز، اتصال مستقیم فقط به دیتابیس حافظه‌ای (:memory:) مجاز است و باز کردن
//    مستقیم فایل‌های واقعی (market.db, codal.db, user.db) با sql.Open ممنوع است و باید از db.Open استفاده شود.
// ۳. هیچ فایلی خارج از internal/db اجازهٔ نوشتن مستقیم با os.Create, os.OpenFile یا os.WriteFile
//    روی فایل‌های دیتابیس (.db, .db-wal, .db-shm) را ندارد.
func TestArchitectureNoDirectSQLOpen(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd failed: %v", err)
	}
	backendRoot := filepath.Clean(filepath.Join(wd, "..", ".."))
	if _, err := os.Stat(filepath.Join(backendRoot, "go.mod")); err != nil {
		backendRoot = wd
	}

	fset := token.NewFileSet()
	var prodViolations []string
	var testViolations []string
	var fileWriteViolations []string

	err = filepath.WalkDir(backendRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			name := d.Name()
			if name == ".git" || name == "vendor" || name == "node_modules" || name == "bin" {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(path, ".go") {
			return nil
		}

		rel, err := filepath.Rel(backendRoot, path)
		if err != nil {
			return nil
		}
		rel = filepath.ToSlash(rel)
		if strings.HasPrefix(rel, "internal/db/") && !strings.HasSuffix(rel, "arch_test.go") {
			return nil
		}

		isTestFile := strings.HasSuffix(rel, "_test.go")

		node, err := parser.ParseFile(fset, path, nil, parser.ParseComments)
		if err != nil {
			t.Logf("هشدار: خطا در پارس %s: %v", rel, err)
			return nil
		}

		ast.Inspect(node, func(n ast.Node) bool {
			call, ok := n.(*ast.CallExpr)
			if !ok {
				return true
			}

			// ۱. بررسی فراخوانی sql.Open یا sql.OpenDB
			if sel, ok := call.Fun.(*ast.SelectorExpr); ok {
				if id, ok := sel.X.(*ast.Ident); ok {
					if id.Name == "sql" && (sel.Sel.Name == "Open" || sel.Sel.Name == "OpenDB") {
						pos := fset.Position(call.Pos())
						if !isTestFile {
							// در کد پروداکشن تحت هیچ شرایطی مجاز نیست!
							prodViolations = append(prodViolations,
								pos.String()+": فراخوانی غیرمجاز sql."+sel.Sel.Name+" در کد پروداکشن خارج از internal/db")
						} else {
							// در کد تست فقط :memory: یا memdb مجاز است، باز کردن دیتابیس واقعی ممنوع است
							isMemory := false
							for _, arg := range call.Args {
								if lit, ok := arg.(*ast.BasicLit); ok {
									val := strings.ToLower(lit.Value)
									if strings.Contains(val, ":memory:") || strings.Contains(val, "mode=memory") {
										isMemory = true
									}
									if strings.Contains(val, "market.db") || strings.Contains(val, "codal.db") || strings.Contains(val, "user.db") {
										testViolations = append(testViolations,
											pos.String()+": باز کردن مستقیم دیتابیس واقعی با sql."+sel.Sel.Name+" در تست؛ باید از db.Open استفاده شود")
									}
								}
							}
							if !isMemory && len(call.Args) >= 2 {
								// اگر هیچ رشته‌ای حاوی memory نبود، ثبت جهت اطمینان
								if lit, ok := call.Args[1].(*ast.BasicLit); ok {
									if !strings.Contains(lit.Value, ":memory:") {
										testViolations = append(testViolations,
											pos.String()+": فراخوانی sql.Open بدون :memory: در فایل تست: "+lit.Value)
									}
								}
							}
						}
					}
				}
			}

			// ۲. بررسی ایجاد مستقیم یا دسترسی نوشتن به فایلهای .db با os.Create / os.OpenFile
			if sel, ok := call.Fun.(*ast.SelectorExpr); ok {
				if id, ok := sel.X.(*ast.Ident); ok && id.Name == "os" {
					if sel.Sel.Name == "Create" || sel.Sel.Name == "WriteFile" || sel.Sel.Name == "OpenFile" {
						for _, arg := range call.Args {
							if lit, ok := arg.(*ast.BasicLit); ok {
								val := strings.ToLower(lit.Value)
								if strings.Contains(val, "market.db") || strings.Contains(val, "codal.db") || strings.Contains(val, "user.db") ||
									strings.Contains(val, "-wal") || strings.Contains(val, "-shm") {
									pos := fset.Position(call.Pos())
									fileWriteViolations = append(fileWriteViolations,
										pos.String()+": دسترسی مستقیم به فایل دیتابیس با os."+sel.Sel.Name+" خارج از internal/db")
								}
							}
						}
					}
				}
			}

			return true
		})

		return nil
	})

	if err != nil {
		t.Fatalf("خطا در پیمایش فایل‌های Go: %v", err)
	}

	if len(prodViolations) > 0 {
		t.Errorf("خطای حیاتی معماری! فراخوانی مستقیم sql.Open در کدهای پروداکشن:\n%s",
			strings.Join(prodViolations, "\n"))
	}
	if len(testViolations) > 0 {
		t.Errorf("خطای معماری تست! باز کردن دیتابیس غیرحافظه‌ای در تست‌ها:\n%s",
			strings.Join(testViolations, "\n"))
	}
	if len(fileWriteViolations) > 0 {
		t.Errorf("خطای معماری دیسک! دسترسی نوشتن مستقیم به فایل دیتابیس:\n%s",
			strings.Join(fileWriteViolations, "\n"))
	}
}
