// Package securefile فایل‌هایِ حاملِ راز (توکنِ پل) را فقط برایِ کاربرِ جاری
// قابلِ‌خواندن می‌کند. روی ویندوز DACL صریح و غیرارثی می‌نشیند؛ ACCESS_MASKِ
// فایل‌هایِ NTFS در Go با os.FileMode قابلِ‌اثبات نیست، پس ACL مرجع است.
package securefile
