package chart

// Real Rahavard type0 rows whose open sits outside [low, high], copied
// from the pinned capture (bars sha256 272336c036d6...).
// The reference series must reach the chart verbatim.

var referenceLiteralRows = []struct {
	symbol, date                   string
	open, high, low, close, volume float64
}{
	{"ومعادن", "1999-02-14", 1014.0, 1015.0, 1015.0, 1015.0, 280000.0},
	{"پادا", "2021-11-30", 106610.0, 106050.0, 105000.0, 106050.0, 650.0},
	{"پادا", "2022-02-12", 93100.0, 92900.0, 92300.0, 92801.0, 1044.0},
}

// پادا carries 1198 reference rows and zero measured
// events: its coverage must come from the reference series itself.
const referenceZeroEventSymbol = "پادا"
const referenceZeroEventCapture = "6aec345f817cd96a0dc8eb631cdfa206deee740afb077b5f4621dd1f821fb844"
const referenceZeroEventRun = "phase49-3-cohort-6aec345f817c"
