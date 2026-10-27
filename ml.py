"""Price forecasting with machine learning.
Concepts used: feature engineering (log returns, moving-average gaps, seasonality), gradient boosting regression,
recursive multi-step forecasting, walk-forward (time-series) validation against a naive baseline,
horizon-widening prediction intervals, and feature-importance explanations.
The model predicts next month's log return (not the price), so it handles rising prices that trees can't extrapolate."""
import math, os, random, time
from datetime import date
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

CROPS = {"mustard": (6200, 420), "wheat": (2500, 120), "rice": (3100, 150), "soybean": (4800, 330), "maize": (2200, 200)}
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
NAMES = ["last month's change", "2-month change", "3-month change", "6-month change", "yearly change",
         "price vs 12-month average", "price vs 3-month average", "time of year", "time of year"]
_cache = {}

def month_list(n):
    d = date.today(); y, m = d.year, d.month; out = []
    for _ in range(n):
        out.append((y, m)); m -= 1
        if m == 0: m, y = 12, y - 1
    return out[::-1]

def series(crop):
    """Real data: put data/<crop>.csv with header 'month,price' and rows like 2024-05,6420 (INR/quintal, monthly)."""
    f = os.path.join(DATA, crop + ".csv")
    if os.path.exists(f):
        rows = [l.strip().split(",") for l in open(f).read().strip().splitlines()[1:] if l.strip()]
        return [(int(r[0][:4]), int(r[0][5:7]), float(r[1])) for r in rows], "real mandi data"
    base, amp = CROPS[crop]; rnd = random.Random(crop)
    return [(y, m, base * (.78 + .0037 * t) + amp * math.sin((m - 3) / 12 * 2 * math.pi) + rnd.gauss(0, amp * .15))
            for t, (y, m) in enumerate(month_list(60))], "simulated data"

def feats(p, m):
    r = lambda k: math.log(p[-k] / p[-k - 1])
    return [r(1), r(2), r(3), r(6), r(12), math.log(p[-1] / (sum(p[-12:]) / 12)), math.log(p[-1] / (sum(p[-3:]) / 3)),
            math.sin(2 * math.pi * m / 12), math.cos(2 * math.pi * m / 12)]

def dataset(p, ms, lo, hi):
    X = [feats(p[:t], ms[t]) for t in range(lo, hi)]
    y = [math.log(p[t] / p[t - 1]) for t in range(lo, hi)]
    return np.array(X), np.array(y)

def new_model():
    return GradientBoostingRegressor(n_estimators=80, max_depth=2, learning_rate=.05, subsample=.8, random_state=0)

def walk_forward(p, ms, k=12):
    """Retrain before each of the last k months, predict it, compare with the truth and with 'same as last month'."""
    err, naive, lerr = [], [], []
    for t in range(len(p) - k, len(p)):
        X, y = dataset(p, ms, 13, t)
        pred = p[t - 1] * math.exp(new_model().fit(X, y).predict([feats(p[:t], ms[t])])[0])
        err.append(abs(pred - p[t])); naive.append(abs(p[t - 1] - p[t])); lerr.append(math.log(pred / p[t]))
    return float(np.mean(err)), float(np.mean(naive)), float(np.std(lerr))

def forecast(crop, months=6):
    hit = _cache.get(crop)
    if hit and time.time() - hit[0] < 3600: return hit[1]
    s, src = series(crop); ms = [x[1] for x in s]; p = [x[2] for x in s]
    X, y = dataset(p, ms, 13, len(p)); model = new_model().fit(X, y)
    mae, naive, sd = walk_forward(p, ms)
    imp = {}
    for n, v in zip(NAMES, model.feature_importances_): imp[n] = imp.get(n, 0) + float(v)
    drivers = [n for n, _ in sorted(imp.items(), key=lambda a: -a[1])[:3]]
    hist, fy, fm, out = p[:], s[-1][0], s[-1][1], []
    for k in range(1, months + 1):
        fm += 1
        if fm == 13: fm, fy = 1, fy + 1
        hist.append(hist[-1] * math.exp(model.predict([feats(hist, fm)])[0]))
        w = 1.28 * sd * math.sqrt(k)
        out.append({"month": f"{fy}-{fm:02d}", "price": round(hist[-1]), "low": round(hist[-1] * math.exp(-w)), "high": round(hist[-1] * math.exp(w))})
    now = round(p[-1]); best = max(out, key=lambda a: a["price"]); gain = best["price"] - now
    advice = ("Sell now. No month in the forecast beats today's price." if gain <= 0 else
              f"Best expected month to sell: {best['month']} (about {gain:,} INR/quintal above today). Weigh storage cost and spoilage.")
    res = {"crop": crop, "current": now, "advice": advice, "forecast": out,
           "history": [{"month": f"{y}-{m:02d}", "price": round(v)} for y, m, v in s[-24:]],
           "note": f"Based on {src}. Typical 1-month error: {mae:,.0f} INR/quintal (a 'same as last month' guess errs by {naive:,.0f}). Main drivers: {', '.join(drivers)}.",
           "metrics": {"mae": round(mae), "naive_mae": round(naive), "data": src}}
    _cache[crop] = (time.time(), res)
    return res
