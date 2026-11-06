# ASCII-only splicer for tools/funnel_browser_probe.mts (run: python _audit/splice_probe.py [--check])
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / 'tools' / 'funnel_browser_probe.mts'
PRE = ROOT / '_audit' / 'probe_pre_splice.mts'
AUD = ROOT / '_audit'
CHECK_ONLY = '--check' in sys.argv

OLD_SHA = 'cfe0b6dbe97ac628dcc3373d5aa2e5737a2911cd2d0fb015b1ab59b9ab76e898'


def fail(msg):
    print('FAIL: ' + msg)
    sys.exit(1)


def sha256b(b):
    return hashlib.sha256(b).hexdigest()


def load_fragment(name):
    p = AUD / name
    if not p.exists():
        fail('fragment missing: ' + name)
    b = p.read_bytes()
    t = b.decode('utf-8')
    if b[:3] == b'\xef\xbb\xbf':
        fail(name + ': BOM present')
    if '\r' in t:
        fail(name + ': CR present')
    for i, ch in enumerate(t):
        o = ord(ch)
        if 0x06F0 <= o <= 0x06F9:
            fail(name + ': raw Persian digit at idx %d' % i)
        if 0x0660 <= o <= 0x0669:
            fail(name + ': raw Arabic digit at idx %d' % i)
        if o in (0x0643, 0x064A):
            fail(name + ': Arabic kaf/yeh at idx %d' % i)
        if o == 0x200C:
            fail(name + ': raw ZWNJ at idx %d' % i)
    out = t.replace('<Z>', '\u200c')
    out = re.sub(r'<D([0-9])>', lambda m: chr(0x06F0 + int(m.group(1))), out)
    left = re.search(r'<[A-Za-z][A-Za-z0-9]{0,2}>', out)
    if left:
        s = max(0, left.start() - 40)
        fail(name + ': leftover token-like text: ' + repr(out[s:left.end() + 40]))
    return out


# lock both copies of the unmodified probe
probe_b = PROBE.read_bytes()
pre_b = PRE.read_bytes()
if sha256b(probe_b) != OLD_SHA:
    fail('probe sha mismatch: ' + sha256b(probe_b))
if sha256b(pre_b) != OLD_SHA:
    fail('recovery copy sha mismatch: ' + sha256b(pre_b))

old_text = probe_b.decode('utf-8')
if '\r' in old_text:
    fail('old probe: CR present')
old = old_text.split('\n')
if len(old) != 1123 or old[-1] != '':
    fail('old probe line count/terminator: %d last=%r' % (len(old), old[-1]))

n1 = load_fragment('n1_header.mts').rstrip('\n')
n2 = load_fragment('n2_cfg.mts').rstrip('\n')
n4a = load_fragment('n4a_helpers.mts').rstrip('\n')
n4b = load_fragment('n4b_board.mts').rstrip('\n')
n4c = load_fragment('n4c_tm.mts').rstrip('\n')
n1_lines = n1.split('\n')
n2_lines = n2.split('\n')
n4_lines = (n4a + '\n' + n4b + '\n' + n4c).split('\n')

if len(n1_lines) != 30:
    fail('n1 line count: %d' % len(n1_lines))
if len(n2_lines) != 2:
    fail('n2 line count: %d' % len(n2_lines))
if not n4_lines[-1].strip() == ');':
    fail('n4 tail: %r' % n4_lines[-3:])

seg_a = old[30:33]
seg_b = old[33:84]
seg_c = old[84:540]
seg_d = old[540:552]
seg_e = old[552:554]
seg_f = old[1094:]
if len(seg_a) != 3 or len(seg_b) != 51 or len(seg_c) != 456 or len(seg_d) != 12 or len(seg_e) != 2 or len(seg_f) != 29:
    fail('segment lens: %d %d %d %d %d %d' % (len(seg_a), len(seg_b), len(seg_c), len(seg_d), len(seg_e), len(seg_f)))
if seg_a[0].strip() != '//':
    fail('seg_a[0]: ' + repr(seg_a[0]))
if 'JEV_CHROME' not in seg_a[1]:
    fail('seg_a[1]: ' + repr(seg_a[1]))
if '--url' not in seg_a[2]:
    fail('seg_a[2]: ' + repr(seg_a[2]))
if not seg_b[0].startswith('import { mkdirSync'):
    fail('seg_b[0]: ' + repr(seg_b[0]))
if not seg_b[1].startswith('import { pathToFileURL'):
    fail('seg_b[1]: ' + repr(seg_b[1]))
if "removeItem('bors-symbol')" not in seg_b[-1]:
    fail('seg_b[-1]: ' + repr(seg_b[-1]))
if not seg_c[0].lstrip().startswith('//'):
    fail('seg_c[0]: ' + repr(seg_c[0]))
if not seg_d[0].startswith('const censusOf'):
    fail('seg_d[0]: ' + repr(seg_d[0]))
if not seg_e[0].startswith('// '):
    fail('seg_e[0]: ' + repr(seg_e[0]))
if seg_e[1] != 'try {':
    fail('seg_e[1]: ' + repr(seg_e[1]))
if not seg_f[0].startswith('} catch'):
    fail('seg_f[0]: ' + repr(seg_f[0]))

new = n1_lines + seg_a + seg_b + n2_lines + seg_c + seg_d + seg_e + n4_lines + seg_f

base = 30 + 3 + 51 + 2 + 456 + 12 + 2
if new[33] != old[33]:
    fail('pos 33')
if new[84] != n2_lines[0] or new[85] != n2_lines[1]:
    fail('pos 84/85')
if new[86] != old[84] or new[87] != old[85]:
    fail('pos 86/87')
if new[542] != old[540] or new[553] != old[551]:
    fail('pos 542..553')
if new[554] != old[552] or new[555] != old[553]:
    fail('pos 554/555')
if new[base - 1] != seg_e[1]:
    fail('pos base-1')
if new[base + len(n4_lines)] != old[1094]:
    fail('pos after n4')
if new[-2] != 'await browser.close();' or new[-1] != '':
    fail('tail: %r %r' % (new[-2], new[-1]))

new_text = '\n'.join(new)
new_b = new_text.encode('utf-8')
n4_digits = sum(1 for ch in new_text if 0x06F0 <= ord(ch) <= 0x06F9)
n4_zwnj = new_text.count('\u200c')

print('splice ok: lines=%d n1=%d n2=%d n4=%d digits=%d zwnj=%d' % (len(new), len(n1_lines), len(n2_lines), len(n4_lines), n4_digits, n4_zwnj))
if CHECK_ONLY:
    print('check-only: no write')
    sys.exit(0)

PROBE.write_bytes(new_b)
print('WROTE tools/funnel_browser_probe.mts sha256=' + sha256b(new_b))
