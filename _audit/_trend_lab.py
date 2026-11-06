import sys

def classify_trend_dow(swings, tol=0.005):
    trend = "na"
    if not swings: return trend
    
    structural_high = None
    structural_low = None
    
    last_h = None
    last_l = None
    
    for s in swings:
        p = s["price"]
        k = s["kind"]
        
        if k == "high":
            if last_h is not None:
                if p > last_h * (1 + tol):
                    # HH
                    if trend != "up":
                        if structural_high is None or p > structural_high * (1 + tol):
                            if last_l is not None:
                                trend = "up"
                                structural_low = last_l
                    else:
                        # Continue up
                        if last_l is not None and (structural_low is None or last_l > structural_low):
                            structural_low = last_l
            last_h = p
                
        else: # low
            if last_l is not None:
                if p < last_l * (1 - tol):
                    # LL
                    if trend != "down":
                        if structural_low is None or p < structural_low * (1 - tol):
                            if last_h is not None:
                                trend = "down"
                                structural_high = last_h 
                    else:
                        # Continue down
                        if last_h is not None and (structural_high is None or last_h < structural_high):
                            structural_high = last_h
            last_l = p
                
    if trend == "na":
        highs = [s["price"] for s in swings if s["kind"] == "high"]
        lows = [s["price"] for s in swings if s["kind"] == "low"]
        if len(highs) >= 2 and len(lows) >= 2:
            hh = highs[-1] > highs[-2] * (1 + tol)
            hl = lows[-1] > lows[-2] * (1 + tol)
            lh = highs[-1] < highs[-2] * (1 - tol)
            ll = lows[-1] < lows[-2] * (1 - tol)
            if hh and hl: trend = "up"
            elif lh and ll: trend = "down"
            else: trend = "range"
    return trend, structural_low, structural_high

swings1 = [
    {"kind": "low", "price": 100, "idx": 0},
    {"kind": "high", "price": 200, "idx": 1},
    {"kind": "low", "price": 120, "idx": 2}, # HL
    {"kind": "high", "price": 250, "idx": 3}, # HH -> Up, structural low = 120
    {"kind": "low", "price": 180, "idx": 4}, # HL, but not structural yet
    {"kind": "high", "price": 230, "idx": 5}, # LH 
]

swings2 = swings1 + [
    {"kind": "low", "price": 170, "idx": 6}, # breaks 180, but 120 is the structural low!
]

swings3 = swings2 + [
    {"kind": "low", "price": 110, "idx": 7}, # breaks 120 -> CHoCH!
]

print("Test 1:", classify_trend_dow(swings1))
print("Test 2:", classify_trend_dow(swings2))
print("Test 3:", classify_trend_dow(swings3))
