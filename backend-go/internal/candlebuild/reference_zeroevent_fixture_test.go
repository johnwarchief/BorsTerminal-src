package candlebuild

// پادا: 1198 real reference rows, zero measured events.
// type0 == type7 on every row, so the identity chain is the correct answer.

const zeroEventSymbol = "پادا"
const zeroEventCapture = "6aec345f817cd96a0dc8eb631cdfa206deee740afb077b5f4621dd1f821fb844"
const zeroEventRun = "phase49-3-cohort-6aec345f817c"

var zeroEventRows = []struct {
	date                           string
	open, high, low, close, volume float64
}{
	{"2021-11-30", 106610.0, 106050.0, 105000.0, 106050.0, 650.0},
	{"2022-02-12", 93100.0, 92900.0, 92300.0, 92801.0, 1044.0},
}
