import { describe, expect, it } from 'vitest';
import { faSectorName } from '@features/fundamental/lib/faOrthography';

/**
 * R-UNSLOP-7 · مرزِ نمایشِ نامِ صنعت.
 * نمونه‌ها عینِ رشته‌هایِ زندهٔ TSETMC از `/api/screener` هستند (۴۶ صنعتِ جهانِ ۷۸۷ ردیفی).
 */
describe('faSectorName — املاءِ فارسی در مرزِ نمایش', () => {
  it('Arabic orthography becomes Persian', () => {
    expect(faSectorName('خدمات فني و مهندسي')).toBe('خدمات فنی و مهندسی');
    expect(faSectorName('فلزات اساسي')).toBe('فلزات اساسی');
    expect(faSectorName('ماشين آلات و تجهيزات')).toBe('ماشین آلات و تجهیزات');
    expect(faSectorName('كاشي و سراميك')).toBe('کاشی و سرامیک');
  });

  it('the three broken strings of the audit read as Persian', () => {
    expect(faSectorName('بيمه وصندوق بازنشستگي به جزتامين اجتماعي'))
      .toBe('بیمه و صندوق بازنشستگی به جزِ تأمین اجتماعی');
    expect(faSectorName('عرضه برق، گاز، بخاروآب گرم')).toBe('عرضه برق، گاز، بخار و آب گرم');
    expect(faSectorName('توليد محصولات كامپيوتري الكترونيكي ونوري'))
      .toBe('تولید محصولات کامپیوتری الکترونیکی و نوری');
  });

  it('missing spaces after a comma and glued plurals are repaired', () => {
    expect(faSectorName('خرده فروشي،باستثناي وسايل نقليه موتوري'))
      .toBe('خرده فروشی، باستثنای وسایل نقلیه موتوری');
    expect(faSectorName('بانكها و موسسات اعتباري')).toBe('بانک‌ها و موسسات اعتباری');
    expect(faSectorName('فعاليتهاي كمكي به نهادهاي مالي واسط'))
      .toBe('فعالیت‌های کمکی به نهاد‌های مالی واسط');
  });

  it('adds no letter that is not a spelling repair (measured on the live corpus)', () => {
    const corpus = [
      'استخراج زغال سنگ', 'استخراج ساير معادن', 'استخراج کانه هاي فلزي',
      'استخراج نفت گاز و خدمات جنبي جز اکتشاف', 'اطلاعات و ارتباطات',
      'انبوه سازي، املاك و مستغلات', 'انتشار، چاپ و تکثير', 'رايانه و فعاليت‌هاي وابسته به آن',
      'ساخت دستگاه‌ها و وسايل ارتباطي', 'ساخت محصولات فلزي', 'ساير محصولات كاني غيرفلزي',
      'سرمايه گذاريها', 'سيمان، آهك و گچ', 'شرکتهاي چند رشته اي صنعتي',
      'فراورده هاي نفتي، كك و سوخت هسته اي', 'فعاليت مهندسي، تجزيه، تحليل و آزمايش فني',
      'قند و شكر', 'لاستيك و پلاستيك', 'محصولات چوبي', 'محصولات شيميايي', 'محصولات كاغذي',
      'مخابرات', 'منسوجات', 'مواد و محصولات دارويي', 'هتل و رستوران', 'خودرو و ساخت قطعات',
    ];
    const strip = (s: string) => s.replace(/[يى]/g, 'ی').replace(/ك/g, 'ک').replace(/[\s‌،]/g, '');
    for (const raw of corpus) {
      const out = faSectorName(raw);
      expect(/[يكى]/.test(out), out).toBe(false);
      // جز املا و فاصله، هیچ حرفِ دیگری درآمیخته یا کم نشده است.
      expect(strip(out)).toBe(strip(raw));
      // بی‌اثر روی رشتهٔ درستِ فارسی و هم‌بارِ خودش.
      expect(faSectorName(out)).toBe(out);
    }
  });

  it('already-Persian names come out untouched', () => {
    for (const clean of ['فلزات اساسی', 'خودرو و ساخت قطعات', 'محصولات غذایی و آشامیدنی به جز قند و شکر']) {
      expect(faSectorName(clean)).toBe(clean);
    }
  });

  it('empty and null stay empty, never a fabricated name', () => {
    expect(faSectorName('')).toBe('');
    expect(faSectorName(null)).toBe('');
    expect(faSectorName(undefined)).toBe('');
  });
});
