"""Regression tests for the board-class digit alias bug (v9.10.4).

TSETMC appends one trailing digit to distinguish the market-board class of the
SAME issuer (مبين / مبين3). CODAL stores financials only under the undigitised
name, so symbol_aliases() had to learn to strip exactly one trailing digit —
otherwise 396 of 1439 stocks looked like they had no fundamental data at all.

Safety property this guards: the rule must never fire on a multi-digit tail
(صشرق512 is a genuinely different symbol, not صشرق5 + 1).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import fts_engine


def test_single_trailing_digit_resolves_to_base():
    al = fts_engine.symbol_aliases('مبين3')
    assert 'مبين' in al, al
    assert al[0] == 'مبين3', 'the symbol itself must stay first (deterministic order)'


def test_multi_digit_tail_is_untouched():
    # 512 is part of the symbol, not a board-class marker
    al = fts_engine.symbol_aliases('صشرق512')
    assert all(a.endswith('512') for a in al), al
    assert 'صشرق5' not in al, 'must not strip a digit from a multi-digit tail'


def test_plain_symbol_unchanged():
    al = fts_engine.symbol_aliases('فولاد')
    assert al[0] == 'فولاد'
    assert len(al) == 1, al


def test_arabic_persian_variants_still_work():
    # the pre-existing behaviour must survive the new rule
    assert 'مبین3' in fts_engine.symbol_aliases('مبين3')
    assert 'داريك' in fts_engine.symbol_aliases('داریك')


def test_too_short_symbol_does_not_strip():
    # a 2-char base would be left with 1 char — not a real symbol
    al = fts_engine.symbol_aliases('آ3')
    assert all(len(a) >= 2 for a in al), al


def test_sym_in_uses_the_base():
    pred, params = fts_engine.sym_in('symbol', 'گنگين2')
    assert 'گنگين' in params, params
    assert pred.startswith('symbol IN (')


def test_empty_symbol_is_safe():
    pred, params = fts_engine.sym_in('symbol', '')
    assert pred == '1=0', pred
    assert params == []


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in fns:
        fn()
        print('  PASS %s' % fn.__name__)
    print('\n%d/%d passed' % (len(fns), len(fns)))
