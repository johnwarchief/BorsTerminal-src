// نگهبانِ نشتِ حالتِ بازپخش با عوض‌شدنِ نماد (کار #44، دورِ E).
// مکان‌نمای بازپخش ایندکسِ سریِ *همان* نمادی است که کاربر روشنش کرد؛ استور
// سراسری است، پس با نمادِ تازه یا با بالا‌آمدنِ دوبلِ چارت رویِ نمادِ دیگر، سریِ
// تازه از ایندکسِ نمادِ قبلی برش می‌خورد. `rehome` همان نشت را می‌بندد.
import { useReplayStore } from '@features/technical/stores/replayStore';
import { beforeEach, describe, expect, it } from 'vitest';

beforeEach(() => {
  useReplayStore.setState({ active: false, cursor: 0, playing: false, owner: null });
});

describe('بازپخش و نمادِ صاحبِ مکان‌نما', () => {
  it('روشن‌کردنِ بازپخش درِ نماد A و رفتن به B ⇒ بازپخش خاموش می‌شود', () => {
    const st = useReplayStore.getState();
    st.start(40);
    st.rehome('A');                      // همان نشستِ A
    expect(useReplayStore.getState().active).toBe(true);
    expect(useReplayStore.getState().cursor).toBe(40);

    useReplayStore.getState().rehome('B');
    const after = useReplayStore.getState();
    expect(after.active).toBe(false);
    expect(after.playing).toBe(false);
    expect(after.owner).toBe('B');
  });

  it('همان نماد ⇒ بازپخش دست‌نخورده می‌ماند (کنترلِ مثبت)', () => {
    const st = useReplayStore.getState();
    st.start(12);
    st.rehome('A');
    st.rehome('A');
    const after = useReplayStore.getState();
    expect(after.active).toBe(true);
    expect(after.cursor).toBe(12);
  });

  it('بی‌بازپخش، rehome هیچ وضعیتی را نمی‌سازد و فقط صاحب را یادداشت می‌کند', () => {
    useReplayStore.getState().rehome('فولاد');
    const after = useReplayStore.getState();
    expect(after.active).toBe(false);
    expect(after.cursor).toBe(0);
    expect(after.owner).toBe('فولاد');
  });

  it('stop صاحبِ مکان‌نما را رها می‌کند تا نمادِ بعدی از نو شروع کند', () => {
    const st = useReplayStore.getState();
    st.start(5);
    st.rehome('A');
    st.stop();
    expect(useReplayStore.getState().owner).toBeNull();
    useReplayStore.getState().rehome('B');
    expect(useReplayStore.getState().active).toBe(false);
  });
});
