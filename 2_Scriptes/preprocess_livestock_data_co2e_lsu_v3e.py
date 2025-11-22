
from __future__ import annotations
import argparse, re, sys
from pathlib import Path
import pandas as pd

# ---------- Taxonomy (case-insensitive) ----------
ALL_ANIMALS_LIST = [
    "All animals", "All animal", "All livestock", "Total animals", "Animals, all"
]
AGGREGATE_LIST = [
    # "Chickens" removed earlier; now remove "Mules and hinnies" as an aggregate option too
    "Camels and Llamas","Cattle","Mules and Asses","Poultry Birds",
    "Sheep and Goats","Swine"
]
ATOMIC_LIST = [
    "Asses","Buffalo","Camels","Swine, breeding","Swine, market","Turkeys",
    "Cattle, dairy","Cattle, non-dairy","Chickens, broilers","Chickens, layers",
    "Ducks","Goats","Horses","Sheep"
]

# EXCLUSIONS (matched case-insensitively on cleaned item label)
EXCLUDE_ITEMS = {s.lower() for s in [
    "Chickens",            # already excluded earlier
    "Mules and hinnies"    # NEW: remove completely from analysis
]}

EU = {"Austria","Belgium","Bulgaria","Croatia","Cyprus","Czechia","Czech Republic","Denmark","Estonia",
      "Finland","France","Germany","Greece","Hungary","Ireland","Italy","Latvia","Lithuania","Luxembourg",
      "Malta","Netherlands","Poland","Portugal","Romania","Slovakia","Slovenia","Spain","Sweden"}
EEA_PLUS_UK = EU.union({"Iceland","Liechtenstein","Norway","United Kingdom","UK"})
EUROPE_WIDE = {"Albania","Andorra","Armenia","Austria","Azerbaijan","Belarus","Belgium","Bosnia and Herzegovina","Bulgaria",
               "Croatia","Cyprus","Czechia","Czech Republic","Denmark","Estonia","Finland","France","Georgia","Germany","Greece",
               "Hungary","Iceland","Ireland","Italy","Kazakhstan","Kosovo","Latvia","Liechtenstein","Lithuania","Luxembourg",
               "Malta","Moldova","Monaco","Montenegro","Netherlands","North Macedonia","Norway","Poland","Portugal","Romania",
               "Russia","San Marino","Serbia","Slovakia","Slovenia","Spain","Sweden","Switzerland","Turkey","Ukraine",
               "United Kingdom","UK","Vatican City"}

def detect_year_cols(cols):
    return [c for c in cols if isinstance(c, str) and c.startswith("Y") and c[1:].isdigit()]

def normalize_element(e: str) -> str | None:
    if e is None: return None
    s = str(e).strip().lower()
    if re.search(r"(^stocks?$|\bstock\b)", s, re.I): return "Stocks"
    if re.search(r"\b(ch4|methane)\b", s, re.I):     return "CH4"
    if re.search(r"\b(n2o|nitrous)\b", s, re.I):     return "N2O"
    return None

def gwp_pair(name: str):
    return {"AR4":(25.0,298.0),"AR5":(28.0,265.0),"AR6_NOCCF":(27.2,273.0),"AR6_CCF":(29.8,273.0)}.get(name.strip().upper(), (27.2,273.0))

def item_kind(label: str) -> str:
    lab = str(label).strip(); low = lab.lower()
    if low in {x.lower() for x in ALL_ANIMALS_LIST}: return "all_animals"
    if low in {x.lower() for x in AGGREGATE_LIST}:   return "aggregate"
    if low in {x.lower() for x in ATOMIC_LIST}:      return "atomic"
    return "atomic"

def looks_like_cattle(name: str) -> bool:
    n = str(name).lower()
    return ("cattle" in n) or ("bovine" in n)

def default_lsu_weight(item: str) -> float:
    il = str(item).lower()
    if "dairy" in il and ("cattle" in il or "bovine" in il): return 1.0
    if "cattle" in il or "bovine" in il: return 0.8
    if "buffalo" in il: return 1.0
    if "sheep" in il or "goat" in il: return 0.1
    if "pig" in il or "swine" in il: return 0.3
    if "poultry" in il or "chicken" in il or "turkey" in il or "duck" in il: return 0.01
    if "horse" in il or "equid" in il: return 0.8
    return 1.0

def is_livestock_total_element(label: str) -> bool:
    if label is None: return False
    s = str(label)
    return bool(re.search(r"livestock", s, re.I) and re.search(r"total", s, re.I))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to raw CSV (e.g., ...\\1_Donnees\\Emissions_*.csv)")
    ap.add_argument("--output", default="", help="Output CSV path. Default: <input_folder>\\livestock_PREPARED_long.csv")
    ap.add_argument("--gwp", default="AR6_NOCCF", help="AR4|AR5|AR6_NOCCF|AR6_CCF")
    ap.add_argument("--split-cattle", default="true", help="true|false (LSU only)")
    ap.add_argument("--dairy-share", type=float, default=35.0, help="% dairy within Cattle (LSU split)")
    ap.add_argument("--only-livestock-total", default="true", help="true|false — keep only CH4/N2O 'Livestock total'")
    args = ap.parse_args()

    split_cattle = str(args.split_cattle).strip().lower() in {"1","true","yes","y"}
    only_lt = str(args.only_livestock_total).strip().lower() in {"1","true","yes","y"}
    dairy_frac = max(0.0, min(1.0, (args.dairy_share or 0.0)/100.0))
    GWP_CH4, GWP_N2O = gwp_pair(args.gwp)

    inp = Path(args.input)
    if not inp.exists():
        sys.exit(f"Input not found: {inp}")
    outp = Path(args.output) if args.output else (inp.parent / "livestock_PREPARED_long.csv")
    outp.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(inp)

    required = {"Area","Item","Element"}
    missing = required.difference(df.columns)
    if missing:
        sys.exit(f"ERROR: CSV missing columns: {', '.join(sorted(missing))}")

    for c in ["Area","Item","Element"]:
        df[c] = df[c].astype(str).str.strip()

    # EXCLUDE specific Items entirely ("Chickens", "Mules and hinnies")
    df = df[~df["Item"].str.strip().str.lower().isin(EXCLUDE_ITEMS)].copy()

    year_cols = detect_year_cols(df.columns)
    if not year_cols:
        sys.exit("ERROR: No year columns found (expected 'Y2010', 'Y2018', etc.)")

    df["ElementNorm"] = df["Element"].apply(normalize_element)
    df = df[df["ElementNorm"].notna()].copy()

    if only_lt:
        mask_gases = df["ElementNorm"].isin(["CH4","N2O"])
        lt_mask = df["Element"].apply(is_livestock_total_element)
        df = df[(~mask_gases) | (mask_gases & lt_mask)].copy()

    df["item_kind"] = df["Item"].apply(item_kind)
    df["is_all_animals"] = df["item_kind"].eq("all_animals")
    df["is_atomic"] = df["item_kind"].eq("atomic")

    long = df.melt(id_vars=["Area","Item","Element","ElementNorm","item_kind","is_all_animals","is_atomic"],
                   value_vars=year_cols, var_name="Year", value_name="Value")
    long["Year"] = long["Year"].str[1:].astype(int)

    prepared = []

    # Stocks
    stocks = long[long["ElementNorm"]=="Stocks"][["Area","Item","Year","Value","item_kind","is_all_animals","is_atomic"]].copy()
    if not stocks.empty:
        s = stocks.copy(); s["Metric"]="Stocks"; prepared.append(s)

    # CH4_CO2e
    ch4 = long[long["ElementNorm"]=="CH4"][["Area","Item","Year","Value","item_kind","is_all_animals","is_atomic"]].copy()
    if not ch4.empty:
        ch4["Value"] = ch4["Value"] * GWP_CH4
        ch4e = ch4.groupby(["Area","Item","Year","item_kind","is_all_animals","is_atomic"], as_index=False)["Value"].sum()
        ch4e["Metric"]="CH4_CO2e"
        prepared.append(ch4e)

    # N2O_CO2e
    n2o = long[long["ElementNorm"]=="N2O"][["Area","Item","Year","Value","item_kind","is_all_animals","is_atomic"]].copy()
    if not n2o.empty:
        n2o["Value"] = n2o["Value"] * GWP_N2O
        n2oe = n2o.groupby(["Area","Item","Year","item_kind","is_all_animals","is_atomic"], as_index=False)["Value"].sum()
        n2oe["Metric"]="N2O_CO2e"
        prepared.append(n2oe)

    # Total_CO2e
    if not ch4.empty or not n2o.empty:
        ch4e_sum = ch4.groupby(["Area","Item","Year","item_kind","is_all_animals","is_atomic"], as_index=False)["Value"].sum().rename(columns={"Value":"CH4_CO2e"})
        n2oe_sum = n2o.groupby(["Area","Item","Year","item_kind","is_all_animals","is_atomic"], as_index=False)["Value"].sum().rename(columns={"Value":"N2O_CO2e"})
        tot = pd.merge(ch4e_sum, n2oe_sum, on=["Area","Item","Year","item_kind","is_all_animals","is_atomic"], how="outer").fillna(0.0)
        tot["Value"] = tot["CH4_CO2e"] + tot["N2O_CO2e"]
        tot = tot.drop(columns=["CH4_CO2e","N2O_CO2e"])
        tot["Metric"]="Total_CO2e"
        prepared.append(tot)

    # LSU from Stocks (with optional cattle split)
    if not stocks.empty:
        sb = stocks.rename(columns={"Value":"Stocks"}).copy()
        if split_cattle:
            mask = sb["Item"].apply(looks_like_cattle)
            cattle = sb[mask].copy()
            non_cattle = sb[~mask].copy()
            if not cattle.empty:
                dairy = cattle.copy(); dairy["Stocks"] *= dairy_frac
                dairy["Item"] = dairy["Item"].astype(str).str.replace(r"(?i)cattle", "Cattle (dairy)", regex=True)
                other = cattle.copy(); other["Stocks"] *= (1.0 - dairy_frac)
                other["Item"] = other["Item"].astype(str).str.replace(r"(?i)cattle", "Cattle (other)", regex=True)
                dairy["item_kind"] = "atomic"; dairy["is_atomic"] = True; dairy["is_all_animals"] = False
                other["item_kind"] = "atomic"; other["is_atomic"] = True; other["is_all_animals"] = False
                sb = pd.concat([non_cattle, dairy, other], ignore_index=True)

        sb["LSU_weight"] = sb["Item"].apply(default_lsu_weight)
        sb["Value"] = sb["Stocks"] * sb["LSU_weight"]
        lsu = sb[["Area","Item","Year","Value","item_kind","is_all_animals","is_atomic"]].copy()
        lsu["Metric"]="LSU"
        prepared.append(lsu)

    if not prepared:
        sys.exit("Nothing to write.")

    out = pd.concat(prepared, ignore_index=True)
    out = out.sort_values(["Area","Item","Year","Metric"]).reset_index(drop=True)

    # ---- Append group totals (per Item, Year, Metric) ----
    def group_totals(df_long: pd.DataFrame, members: set[str], label: str) -> pd.DataFrame:
        sub = df_long[df_long["Area"].isin(members)].copy()
        if sub.empty:
            return sub
        g = (sub.groupby(["Item","Year","Metric","item_kind","is_all_animals","is_atomic"], as_index=False)["Value"]
                .sum())
        g.insert(0, "Area", label)
        return g

    areas_available = set(out["Area"].unique().tolist())
    eu = areas_available.intersection(EU)
    eea = areas_available.intersection(EEA_PLUS_UK)
    eur = areas_available.intersection(EUROPE_WIDE)

    add = []
    if eu:  add.append(group_totals(out, eu,  "EU (group total)"))
    if eea: add.append(group_totals(out, eea, "EU/EEA+UK (group total)"))
    if eur: add.append(group_totals(out, eur, "Europe (group total)"))
    if add:
        out = pd.concat([out] + add, ignore_index=True).sort_values(["Area","Item","Year","Metric"]).reset_index(drop=True)

    out[["Area","Item","Year","Metric","Value","item_kind","is_all_animals","is_atomic"]].to_csv(outp, index=False)
    print(f"Wrote prepared dataset (v3e, excludes 'Mules and hinnies' & 'Chickens') to: {outp}")

if __name__ == "__main__":
    main()
