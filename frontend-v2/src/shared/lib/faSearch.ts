/** یکسان‌سازیِ جستجو: ي/ك عربی، نیم‌فاصله و فاصله‌های تکراری */
export function normalizeFa(input: string): string {
  return input
    .replace(/ي/g, 'ی')
    .replace(/ك/g, 'ک')
    .replace(/\u200c/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}
