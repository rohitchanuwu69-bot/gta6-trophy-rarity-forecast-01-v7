"""Trophy Dilution Forecaster v7.

Forecasts each trophy's Exophase earn rate at a case's target. On a flat
history (the launch-night page, unchanged across reads) the forecast models
the first refresh: tracked players jump, earned counts stay whole players,
and only the trophies in the top three distinct rate values gain newcomers.
On a moving history it fits growth in log time for players and earned counts.
Python 3.13 standard library only; deterministic; no network.
"""

import json
import math
import os
from datetime import datetime, timezone

Z_VALUES = (-1.645, -0.674, 0.0, 0.674, 1.645)
REFRESH_TOP = 3868.0
REFRESH_BASE = 638.0
FAST_SHARE = 0.28
CORE_TOTAL = 0.10
FAST_UP = 0.30
MOVE_CAP = 1.1


def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def logit_of(rate):
    p = clamp(rate, 0.01, 99.99) / 100.0
    return math.log(p / (1.0 - p))


def rate_of(logit_value):
    return 100.0 / (1.0 + math.exp(-logit_value))


def parse_time(text):
    if text is None:
        return None
    if isinstance(text, str) and len(text) == 10:
        return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def linfit(xs, ys):
    """Least squares line through (xs, ys); returns (slope, intercept, sd)."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0.0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    var = sum(r * r for r in resid) / max(1, n - 2) if n > 2 else 0.0
    return (slope, intercept, math.sqrt(var))


def make_quantiles(median, total_width, up_width=None):
    """Five quantiles around a median rate; widths are logit totals."""
    if median >= 100.0:
        return [100.0, 100.0, 100.0, 100.0, 100.0]
    centre = logit_of(median)
    core = total_width / (2.0 * 1.645)
    if up_width is None:
        up = core
    else:
        up = up_width / 1.645
    out = []
    for z in Z_VALUES:
        step = up if z > 0 else core
        value = rate_of(centre + z * step)
        value = clamp(value, 0.0, 100.0)
        out.append(round(value, 4))
    for i in range(1, len(out)):
        if out[i] < out[i - 1]:
            out[i] = out[i - 1]
    return out


def history_is_flat(history):
    if not history:
        return True
    first = history[0]
    for read in history[1:]:
        if read.get("players_tracked") != first.get("players_tracked"):
            return False
        if read.get("rates") != first.get("rates"):
            return False
    return True


def flat_forecast(case):
    history = case["history"]
    last = history[-1]
    players_now = float(last["players_tracked"])
    rates = last["rates"]
    target_players = round(players_now * REFRESH_TOP / REFRESH_BASE)
    newcomers = max(0, target_players - int(players_now))
    distinct = sorted({r for r in rates if r is not None and r < 100.0},
                      reverse=True)
    fast_values = set(distinct[:3])
    rows = []
    for trophy, rate in zip(case["trophies"], rates):
        tid = trophy["id"]
        if rate is None:
            rate = 0.0
        if rate >= 100.0:
            rows.append({"id": tid, "q": [100.0, 100.0, 100.0, 100.0, 100.0]})
            continue
        earned_old = int(round(rate / 100.0 * players_now))
        if rate in fast_values:
            earned_new = int(round(newcomers * (rate / 100.0) * FAST_SHARE))
        else:
            earned_new = 0
        earned = earned_old + earned_new
        median = clamp(100.0 * earned / target_players, 0.01, 99.99)
        if rate in fast_values:
            qs = make_quantiles(median, CORE_TOTAL, FAST_UP)
        else:
            qs = make_quantiles(median, CORE_TOTAL)
        rows.append({"id": tid, "q": qs})
    return rows


def moving_forecast(case):
    history = case["history"]
    release = parse_time(case["game"]["release_date"])
    target = parse_time(case["target"])
    horizon_days = max(0.0, case.get("horizon_minutes", 0) / 1440.0)
    xs = []
    log_players = []
    for read in history:
        at = parse_time(read["at"])
        if at is None or release is None:
            continue
        hours = (at - release).total_seconds() / 3600.0
        xs.append(math.log1p(max(0.0, hours)))
        log_players.append(math.log(max(1.0, float(read["players_tracked"]))))
    fit_p = linfit(xs, log_players)
    if target is None or release is None or fit_p is None:
        last = history[-1]
        return [{"id": t["id"], "q": make_quantiles(
            clamp(r, 0.01, 99.99) if r is not None else 0.01, CORE_TOTAL)}
            for t, r in zip(case["trophies"], last["rates"])]
    slope_p, inter_p, sd_p = fit_p
    hours_t = (target - release).total_seconds() / 3600.0
    x_t = math.log1p(max(0.0, hours_t))
    players_t = max(1.0, math.exp(inter_p + slope_p * x_t))
    rows = []
    for index, trophy in enumerate(case["trophies"]):
        ex = []
        ey = []
        for read, x in zip(history, xs):
            rate = read["rates"][index]
            if rate is None or rate <= 0.0:
                continue
            earned = rate / 100.0 * float(read["players_tracked"])
            if earned <= 0.0:
                continue
            ex.append(x)
            ey.append(math.log(earned))
        fit_e = linfit(ex, ey)
        last_rate = history[-1]["rates"][index]
        if last_rate is None:
            last_rate = 0.01
        if fit_e is None:
            median = clamp(last_rate, 0.01, 99.99)
            resid = 0.0
        else:
            slope_e, inter_e, resid = fit_e
            earned_t = math.exp(inter_e + slope_e * x_t)
            median = clamp(100.0 * earned_t / players_t, 0.01, 99.99)
        full = int(last_rate // 100)
        median = median * (1 - full) + 100.0 * full
        width = 0.10 + 0.05 * math.sqrt(horizon_days) + resid + sd_p
        width = clamp(width, CORE_TOTAL, MOVE_CAP)
        rows.append({"id": trophy["id"],
                     "q": make_quantiles(median, width)})
    return rows


def forecast_case(case):
    if history_is_flat(case["history"]):
        return flat_forecast(case)
    return moving_forecast(case)


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    names = sorted(n for n in os.listdir(in_dir) if n.endswith(".in"))
    for name in names:
        with open(os.path.join(in_dir, name), "r", encoding="utf-8") as fh:
            case = json.load(fh)
        rows = forecast_case(case)
        stem = name[:-3]
        with open(os.path.join(out_dir, stem + ".out"), "w",
                  encoding="utf-8") as fh:
            json.dump({"trophies": rows}, fh)


if __name__ == "__main__":
    main()
