// shared/ui/cn.ts -- ادغامِ کلاس، قراردادِ shadcn
//
// `clsx` شرط‌ها را به رشته تبدیل می‌کند و `twMerge` تضادهایِ تیلویند را حل
// می‌کند: در `cn('px-2', 'px-4')` فقط `px-4` می‌ماند. بی‌این، کلاسی که
// مصرف‌کننده از بیرون می‌دهد با کلاسِ پیش‌فرضِ کامپوننت می‌جنگد و برنده‌اش
// به ترتیبِ فایلِ CSS بستگی پیدا می‌کند — یعنی قابلِ پیش‌بینی نیست.
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
