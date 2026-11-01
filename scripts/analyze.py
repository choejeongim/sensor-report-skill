#!/usr/bin/env python3
"""센서 CSV를 읽어 요약 통계를 JSON으로 출력한다. 사용: python3 analyze.py 파일.csv [--profile 프로필.json]"""
import csv, json, sys, statistics as st
from datetime import datetime

TIME_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M"]

def parse_time(s):
    for f in TIME_FORMATS:
        try:
            return datetime.strptime(s.strip(), f)
        except ValueError:
            pass
    return None

def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None

def in_window(t, start, end):
    m = t.hour * 60 + t.minute
    a = int(start[:2]) * 60 + int(start[3:])
    b = int(end[:2]) * 60 + int(end[3:])
    return (a <= m < b) if a <= b else (m >= a or m < b)

def profile_report(prof, rows, times, num_cols):
    """프로필(대상·기준·일과)이 있으면 수면 시간대별 분석을 만든다."""
    res = {"profile": prof["name"], "note": prof.get("note"), "targets": prof["targets"], "chosen_columns": {}, "periods": {}}
    chosen = {}
    for key, hints in prof["column_hints"].items():
        chosen[key] = next((c for c in hints if c in num_cols), None)
    res["chosen_columns"] = chosen
    names = [w["name"] for w in prof["schedule"]] + ["깨어 있는 시간"]
    buckets = {n: [] for n in names}
    for t, r in zip(times, rows):
        if not t:
            continue
        label = next((w["name"] for w in prof["schedule"] if in_window(t, w["start"], w["end"])), "깨어 있는 시간")
        buckets[label].append(r)
    for name, rs in buckets.items():
        if not rs:
            continue
        info = {"count": len(rs)}
        for key, col in chosen.items():
            if not col:
                continue
            v = [to_float(r[col]) for r in rs if to_float(r[col]) is not None]
            if not v:
                continue
            tg = prof["targets"][key]
            info[key] = {"mean": round(st.mean(v), 1), "min": min(v), "max": max(v)}
            if key == "co2":
                info[key]["pct_good"] = round(100 * sum(x < tg["good_max"] for x in v) / len(v), 1)
                info[key]["pct_high"] = round(100 * sum(x >= tg["high_min"] for x in v) / len(v), 1)
                if "ideal_max" in tg:
                    info[key]["pct_ideal"] = round(100 * sum(x < tg["ideal_max"] for x in v) / len(v), 1)
            else:
                info[key]["pct_in_range"] = round(100 * sum(tg["min"] <= x <= tg["max"] for x in v) / len(v), 1)
                info[key]["pct_above"] = round(100 * sum(x > tg["max"] for x in v) / len(v), 1)
                info[key]["pct_below"] = round(100 * sum(x < tg["min"] for x in v) / len(v), 1)
                if "ideal_max" in tg:
                    info[key]["pct_at_or_below_ideal_max"] = round(100 * sum(x <= tg["ideal_max"] for x in v) / len(v), 1)
        res["periods"][name] = info
    return res

def main(path, profile_path=None):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(json.dumps({"error": "데이터 행이 없습니다"}, ensure_ascii=False)); return
    cols = list(rows[0].keys())
    time_col = next((c for c in cols if c.lower() in ("time", "timestamp", "datetime", "date", "시간", "시각")), None)
    if time_col is None:
        time_col = next((c for c in cols if parse_time(rows[0][c] or "")), None)
    dev_col = next((c for c in cols if c.lower() in ("device", "장치", "위치", "location")), None)
    # 테스트 행 제외
    if dev_col:
        rows = [r for r in rows if (r[dev_col] or "").strip().lower() != "test"]
    times = [parse_time(r[time_col]) if time_col else None for r in rows]
    num_cols = [c for c in cols if c not in (time_col, dev_col)
                and sum(to_float(r[c]) is not None for r in rows) >= 0.8 * len(rows)]
    out = {"file": path, "rows": len(rows), "columns": num_cols, "device": None, "period": None,
           "gaps": [], "stats": {}, "warnings": []}
    if dev_col:
        out["device"] = sorted({r[dev_col] for r in rows})
    valid_t = [t for t in times if t]
    if valid_t:
        out["period"] = {"start": str(min(valid_t)), "end": str(max(valid_t)),
                         "hours": round((max(valid_t) - min(valid_t)).total_seconds() / 3600, 2)}
        srt = sorted(valid_t)
        out["gaps"] = [{"from": str(a), "to": str(b), "minutes": round((b - a).total_seconds() / 60, 1)}
                       for a, b in zip(srt, srt[1:]) if (b - a).total_seconds() > 300][:5]
    for c in num_cols:
        pairs = [(t, to_float(r[c])) for t, r in zip(times, rows) if to_float(r[c]) is not None]
        vals = [v for _, v in pairs]
        s = {"count": len(vals), "min": min(vals), "mean": round(st.mean(vals), 2), "max": max(vals),
             "first": vals[0], "last": vals[-1]}
        if len(vals) > 1:
            s["stdev"] = round(st.pstdev(vals), 2)
        if valid_t and pairs and pairs[0][0]:
            pk = max(pairs, key=lambda p: p[1])
            s["max_at"] = str(pk[0])
        out["stats"][c] = s
    co2 = next((c for c in num_cols if "co2" in c.lower()), None)
    if co2:
        vals = [to_float(r[co2]) for r in rows if to_float(r[co2]) is not None]
        n = len(vals)
        out["co2_levels"] = {
            "under_1000_pct": round(100 * sum(v < 1000 for v in vals) / n, 1),
            "1000_1500_pct": round(100 * sum(1000 <= v < 1500 for v in vals) / n, 1),
            "over_1500_pct": round(100 * sum(v >= 1500 for v in vals) / n, 1),
            "below_400_count": sum(v < 400 for v in vals)}
        if out["co2_levels"]["below_400_count"]:
            out["warnings"].append("CO2 400ppm 미만 값이 있어요. 센서 재시작 직후 같은 잘못된 값일 수 있어요.")
        half = n // 2
        if n >= 20:
            out["co2_trend"] = {"first_half_mean": round(st.mean(vals[:half]), 1),
                                "second_half_mean": round(st.mean(vals[half:]), 1)}
    if out["rows"] < 30:
        out["warnings"].append("데이터가 30개 미만이라 경향을 말하기엔 적어요.")
    if profile_path:
        prof = json.load(open(profile_path, encoding="utf-8"))
        out["profile_report"] = profile_report(prof, rows, times, num_cols)
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    args = sys.argv[1:]
    profile = None
    if "--profile" in args:
        i = args.index("--profile")
        profile = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        sys.exit("사용법: python3 analyze.py 파일.csv [--profile profiles/baby_13m.json]")
    main(args[0], profile)
