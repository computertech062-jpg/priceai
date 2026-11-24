"""خوێندنەوە و پاککردنەوەی داتا."""
from pathlib import Path

import numpy as np
import pandas as pd

from . import features as F

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REAL_DATA = DATA_DIR / "phones.csv"          # داتای ڕاستەقینەی تۆ
SAMPLE_DATA = DATA_DIR / "sample_phones.csv"  # داتای نموونەیی


def default_dataset_path():
    """ئەگەر data/phones.csv هەبێت ئەوە بەکاردێت، ئەگەرنا داتای نموونەیی."""
    return REAL_DATA if REAL_DATA.exists() else SAMPLE_DATA


def is_sample(path):
    return Path(path).resolve() == SAMPLE_DATA.resolve()


def load_dataset(path=None):
    path = Path(path or default_dataset_path())
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    missing = [c for c in F.ALL + [F.TARGET] if c not in df.columns]
    if missing:
        raise ValueError(
            f"ئەم ستوونانە لە {path.name} دا نین: {missing}. "
            "بڕوانە scripts/prepare_dataset.py بۆ گونجاندنی داتاکەت."
        )

    for c in F.NUMERIC + [F.TARGET]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in F.BINARY:
        df[c] = df[c].map(to_binary)
    for c in F.CATEGORICAL:
        s = df[c].astype("string").str.strip()
        df[c] = s.astype(object).where(s.notna() & (s != ""), np.nan)

    if "model" not in df.columns:
        df["model"] = df["brand"].fillna("Phone") + " #" + df.index.astype(str)
    if "chipset" not in df.columns:
        df["chipset"] = ""
    df["model"] = df["model"].astype(str).str.strip()
    df["chipset"] = df["chipset"].fillna("").astype(str).str.strip()

    before = len(df)
    df = df[df[F.TARGET].notna() & (df[F.TARGET] > 0)]
    df = df.drop_duplicates(subset=["brand", "model"] + F.ALL)
    df = df.reset_index(drop=True)
    df.attrs["dropped"] = before - len(df)
    df.attrs["path"] = str(path)
    return df


def to_binary(v):
    if pd.isna(v):
        return np.nan
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("1", "yes", "true", "y", "بەڵێ", "هەیە"):
            return 1
        if s in ("0", "no", "false", "n", "نەخێر", "نییە", ""):
            return 0
        return np.nan
    return int(bool(v))


def to_frame(rows):
    """لیستێک لە dict ـی تایبەتمەندییەکان دەکاتە DataFrame بە جۆری دروست."""
    df = pd.DataFrame([{c: r.get(c) for c in F.ALL} for r in rows], columns=F.ALL)
    for c in F.NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    for c in F.BINARY:
        df[c] = df[c].map(to_binary).astype(float)
    for c in F.CATEGORICAL:
        df[c] = df[c].astype(object).where(df[c].notna(), np.nan)
    return df
