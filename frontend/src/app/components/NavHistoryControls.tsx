// app/components/NavHistoryControls.tsx — دو دکمۀِ بازگشت/بعدی درِ نوارِ بالا
//
// چرا این‌ها درِ `Topbar` می‌نشینند و نه یکِ نوارِ تازه: مأموریت صریح است — بی‌ردیفِ
// تازه، بی‌افزایشِ ارتفاعِ نوارِ بالا. خودِ `<nav>`ِ «موقعیت در برنامه» همین حالا
// می‌گوید «کجا هستم»؛ این جفت فقط همان‌جا «ازِ کجا آمدم» را اضافه می‌کند، بی‌آنکه
// ارتفاعِ `h-11 md:h-9` عوض شود.
//
// چرا حرکت باِ `navigate(-1)` و نه `navigate(backTo)`: تاریخچۀِ درونِ برنامه
// آینه‌ای ازِ تاریخچۀِ خودِ router است (هر PUSH یکِ entryِ واقعی می‌سازد). پریدن
// به آدرسِ مقصد آن entry را دوباره جلو می‌فرستد و زنجیرۀِ forward را می‌شکند؛
// `navigate(-1)` همان POP را می‌سازد که `navHistoryStore` باِ نامِ «همسایه»
// می‌شناسد. پسِ `title` ازِ مدلِ داخلی است (نامِ مقصد را نشان می‌دهد) ولی
// اقدام ازِ مسیرِ بومیِ مرورگر می‌رود.
//
// جهت درِ فارسی: درِ چیدمانِ راست‌به‌چپ خواندن ازِ راست شروع می‌شود، پسِ «قبلی»
// سوِ راست وِ «بعدی» سوِ چپ است. `ChevronIcon` به‌طورِ پیش‌فرض به چپ اشاره می‌کند،
// پسِ بازگشت `rotate-180` می‌گیرد (همان کاری که `Sidebar.tsx:108` باِ حالتِ جمع‌شده
// می‌کند).
import { useNavigate } from 'react-router';
import { ChevronIcon } from '@shared/components/Icons';
import { useNavGates } from '@shared/stores/navHistoryStore';

// کفِ لمس درِ گوشی: همان `size-10` که دکمهٔ جست‌وجویِ کنارِ همین نوار می‌گیرد
// (`Topbar.tsx`، `max-md:min-h-[40px]`) — ارتفاعِ `h-11` خودِ نوار درِ گوشی ۴۴px
// است، پسِ ۴۰px بی‌افزایشِ ارتفاعِ نوار جا می‌شود.
const BTN =
  'flex size-7 shrink-0 items-center justify-center rounded-md border border-transparent ' +
  'text-text-secondary transition-colors hover:bg-bg-card hover:text-accent-blue ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-blue ' +
  'disabled:pointer-events-none disabled:opacity-35 max-md:size-10';

export function NavHistoryControls() {
  const navigate = useNavigate();
  const { canBack, canForward, backTo, forwardTo } = useNavGates();

  // کلیکِ بی‌نتیجه نباید رخ دهد: دکمه درِ حالتِ غیرفعال واقعاً `disabled` است،
  // نه فقط کم‌رنگ (آزمونِ «بی‌امکان ⇒ بی‌حرکت» همین را می‌سنجد).
  return (
    <div className="flex shrink-0 items-center gap-0.5" role="group" aria-label="تاریخچۀِ ناوبری">
      <button
        type="button"
        data-testid="nav-back"
        disabled={!canBack}
        onClick={() => navigate(-1)}
        aria-label="بازگشت به صفحهٔ قبلی"
        title={backTo ? `بازگشت به ${backTo}` : 'صفحهٔ قبلی‌ای در تاریخچه نیست'}
        className={BTN}
      >
        <ChevronIcon size={13} className="rotate-180" />
      </button>
      <button
        type="button"
        data-testid="nav-forward"
        disabled={!canForward}
        onClick={() => navigate(1)}
        aria-label="رفتن به صفحهٔ بعدی"
        title={forwardTo ? `رفتن به ${forwardTo}` : 'صفحهٔ بعدی‌ای در تاریخچه نیست'}
        className={BTN}
      >
        <ChevronIcon size={13} />
      </button>
    </div>
  );
}
