package codal

import (
	"math"
	"testing"
)

func TestNormalizeUnit(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected float64
	}{
		// Persian Million
		{"persian_million_rials", "میلیون ریال", 1000000.0},
		{"persian_million_bare", "میلیون", 1000000.0},
		{"persian_million_zwnj", "میلیون\u200cریال", 1000000.0},
		{"persian_million_arabic_yeh", "ميليون ريال", 1000000.0},
		{"persian_million_arabic_bare", "ميليون", 1000000.0},
		{"persian_million_spaces", "  میلیون   ریال  ", 1000000.0},
		{"persian_million_in_parentheses", "(میلیون ریال)", 1000000.0},
		{"persian_million_digits", "۱۰^۶ ریال", 1000000.0},

		// English Million
		{"english_million_title", "Million Rials", 1000000.0},
		{"english_million_lower", "million rials", 1000000.0},
		{"english_million_upper", "MILLION RIALS", 1000000.0},
		{"english_million_bare", "million", 1000000.0},
		{"english_m_rials", "M Rials", 1000000.0},
		{"english_m_rials_lower", "m rials", 1000000.0},
		{"english_m_dot_rials", "M. Rials", 1000000.0},
		{"english_m_rial_singular", "m rial", 1000000.0},
		{"english_mrials_nospace", "mrials", 1000000.0},

		// Persian Thousand
		{"persian_thousand_rials", "هزار ریال", 1000.0},
		{"persian_thousand_bare", "هزار", 1000.0},
		{"persian_thousand_zwnj", "هزار\u200cریال", 1000.0},
		{"persian_thousand_arabic_yeh", "هزار ريال", 1000.0},
		{"persian_thousand_spaces", "  هزار   ریال  ", 1000.0},
		{"persian_thousand_digits", "۱۰^۳ ریال", 1000.0},

		// English Thousand
		{"english_thousand_title", "Thousand Rials", 1000.0},
		{"english_thousand_lower", "thousand rials", 1000.0},
		{"english_thousand_upper", "THOUSAND RIALS", 1000.0},
		{"english_thousand_bare", "thousand", 1000.0},
		{"english_k_rials", "k rials", 1000.0},
		{"english_k_dot_rials", "k. rials", 1000.0},

		// Persian Billion
		{"persian_billion_rials", "میلیارد ریال", 1000000000.0},
		{"persian_billion_bare", "میلیارد", 1000000000.0},
		{"persian_billion_zwnj", "میلیارد\u200cریال", 1000000000.0},
		{"persian_billion_arabic_yeh", "ميليارد ريال", 1000000000.0},
		{"persian_billion_spaces", "  میلیارد   ریال  ", 1000000000.0},
		{"persian_billion_digits", "۱۰^۹ ریال", 1000000000.0},

		// English Billion
		{"english_billion_title", "Billion Rials", 1000000000.0},
		{"english_billion_lower", "billion rials", 1000000000.0},
		{"english_billion_upper", "BILLION RIALS", 1000000000.0},
		{"english_billion_bare", "billion", 1000000000.0},
		{"english_b_rials", "b rials", 1000000000.0},
		{"english_b_dot_rials", "b. rials", 1000000000.0},

		// Rial / Default / Unknown
		{"rial_bare", "ریال", 1.0},
		{"rial_arabic", "ريال", 1.0},
		{"english_rials", "Rials", 1.0},
		{"english_rial_lower", "rial", 1.0},
		{"empty_string", "", 1.0},
		{"whitespace_only", "   ", 1.0},
		{"zwnj_only", "\u200c", 1.0},
		{"unknown_string", "unknown_unit", 1.0},
		{"commodity_unit_ton", "تن", 1.0},
		{"commodity_unit_count", "عدد", 1.0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := NormalizeUnit(tt.input)
			if math.Abs(got-tt.expected) > 1e-9 {
				t.Errorf("NormalizeUnit(%q) = %f, want %f", tt.input, got, tt.expected)
			}
		})
	}
}
