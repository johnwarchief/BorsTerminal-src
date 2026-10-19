// shared/lib/useNavHistorySync.ts — پلِ router → تاریخچۀِ درون‌برنامه
//
// تنها کارِ این فایل: هر بار که نشانی عوض شد، همان تغییر را باِ نوعش
// (`PUSH`/`REPLACE`/`POP`) درِ `navHistoryStore` ثبت کند. نوعِ ناوبری ازِ
// `useNavigationType()` می‌آید — رابطِ عمومیِ خودِ react-router، نه یکِ کلکِ
// خصوصی (به جزئیاتِ مستندنشده به‌عنوانِ تنها منبع حقیقت تکیه نشود).
//
// `pathname + search` ثبت می‌شود، نه pathname تنها: `/master?stage=3` با
// `/master` دو صفحۀِ متفاوت‌اند و برگشت باید همان query را پس بدهد.
import { useEffect } from 'react';
import { useLocation, useNavigationType } from 'react-router';
import { useNavHistoryStore, type NavKind } from '@shared/stores/navHistoryStore';

/** `SUBMIT`/`NONE` (فرم یا مقدارِ اولِ روتر) برایِ ما یکِ ورودِ معمولی است. */
function asKind(t: string): NavKind {
  return t === 'REPLACE' ? 'REPLACE' : t === 'POP' ? 'POP' : 'PUSH';
}

export function useNavHistorySync() {
  const location = useLocation();
  const navType = useNavigationType();
  const record = useNavHistoryStore((s) => s.record);
  const path = `${location.pathname}${location.search}`;
  useEffect(() => { record(path, asKind(String(navType))); }, [path, navType, record]);
}
