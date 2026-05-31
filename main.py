"""
LCrack Dashboard — main.py
Genera site/ estático con dos pestañas:
  · Dashboard: tabla semáforo con todos los tickers (Cell 0 del notebook)
  · Graficador: gráfico multipanel matplotlib → PNG por ticker (Cell 1 del notebook)

Uso:
    python main.py
"""

import json
import warnings
import base64
import io
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import yfinance as yf
from ta.trend import MACD, EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator

warnings.filterwarnings("ignore")

# ============================================================
# TICKERS — exactamente los del notebook (Cell 0)
# ============================================================

TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOG", "META", "BRK-B", "TSLA", "JNJ", "V",
    "PG", "XOM", "UNH", "JPM", "HD", "LLY", "MA", "CVX", "ABBV", "KO", "PEP",
    "COST", "BAC", "CRM", "NFLX", "ABT", "MCD", "LMT", "EL", "NEE", "CAT", "MRK",
    "TPL", "ASML", "ADBE", "AVGO", "CSCO", "CMCSA", "AMD", "TXN", "QCOM", "AMAT", "LITE", "LRCX",
    "INTU", "VRTX", "ZS", "PLTR", "CSU.TO", "MU", "LVMUY", "SAP", "OR.PA", "TTE", "SATS", "ON",
    "MC.PA", "SIE.DE", "ENGI.PA", "AIR.PA", "ALV.DE", "EL.PA", "AI.PA", "BNP.PA",
    "SAN.PA", "KER.PA", "SU.PA", "NESN.SW", "LIN.DE", "VOW3.DE", "BMW.DE", "ADS.DE",
    "IFX.DE", "MUV2.DE", "FRE.DE", "DTE.DE", "RWE.DE", "ITX.MC", "BBVA.MC", "SAN.MC",
    "TEF.MC", "IBE.MC", "REP.MC", "FER.MC", "ACX.MC", "ACS.MC", "AENA.MC", "ANA.MC",
    "IAG.MC", "LOG.MC", "MAP.MC", "PUIG.MC", "NTGY.MC", "ELE.MC", "IDR.MC", "PDD",
    "NIO", "TCEHY", "BZUN", "FUTU", "MOMO", "MNSO", "TAL", "EDU", "WB", "XPEV",
    "GC=F", "SI=F", "BTC-USD", "ETH-USD", "XRP-USD"
]

MAX_WORKERS = 6

# ============================================================
# STYLE — igual que Cell 1
# ============================================================

STYLE = {
    "bg":        "#0d0f14",
    "panel":     "#13161e",
    "border":    "#1f2430",
    "bull":      "#26a65b",
    "bear":      "#e04040",
    "bull_fade": "#26a65b55",
    "bear_fade": "#e0404055",
    "mcg":       "#efb030",
    "ema200":    "#6060dd",
    "text":      "#c8cad0",
    "muted":     "#555a6a",
    "verde":     "#2ca85e",
    "marron":    "#a06432",
    "azul":      "#4488e0",
    "media_k":   "#ffffff",
    "pvi":       "#6090e0",
    "pvi_ema":   "#efb030",
    "macd_line": "#6090e0",
    "macd_sig":  "#efb030",
    "rsi":       "#a78bfa",
    "adx":       "#a78bfa",
    "pdi":       "#26a65b",
    "ndi":       "#e04040",
    "ao_up":     "#26a65b",
    "ao_dn":     "#e04040",
    "grid":      "#1a1e28",
    "zero":      "#2a2e3a",
}

plt.rcParams.update({
    "figure.facecolor":  STYLE["bg"],
    "axes.facecolor":    STYLE["panel"],
    "axes.edgecolor":    STYLE["border"],
    "axes.labelcolor":   STYLE["muted"],
    "xtick.color":       STYLE["muted"],
    "ytick.color":       STYLE["muted"],
    "text.color":        STYLE["text"],
    "grid.color":        STYLE["grid"],
    "grid.linewidth":    0.5,
    "font.family":       "monospace",
    "font.size":         9,
})

# ============================================================
# HELPERS — Cell 0 y Cell 1
# ============================================================

def clean_yf_df(df):
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    needed = ["Open", "High", "Low", "Close", "Volume"]
    for c in needed:
        if c not in df.columns:
            return pd.DataFrame()
    return df[needed].dropna().copy()


def download(ticker, period="2y", interval="1d"):
    df = yf.download(ticker, period=period, interval=interval,
                     auto_adjust=True, progress=False, multi_level_index=False)
    df = clean_yf_df(df)
    if df.empty or len(df) < 60:
        raise ValueError(f"Datos insuficientes para {ticker}")
    return df


def velas_desde_activacion(serie_bool):
    vals = serie_bool.fillna(False).values
    n = len(vals)
    if n == 0 or not vals[-1]:
        return 999
    count = 0
    for i in range(n - 1, -1, -1):
        if vals[i]:
            count += 1
        else:
            break
    return count


# ============================================================
# INDICADORES — copiados literalmente del notebook
# ============================================================

def mcginley_dynamic(close, period=25):
    md = close.copy().astype(float)
    k = 0.6
    for i in range(1, len(close)):
        prev = md.iloc[i - 1]
        if prev == 0 or pd.isna(prev):
            md.iloc[i] = close.iloc[i]
        else:
            md.iloc[i] = prev + ((close.iloc[i] - prev) /
                                  (k * period * (close.iloc[i] / prev) ** 4))
    return md

# alias usado en Cell 1
mcginley = mcginley_dynamic


def pvi_calc(close, volume):
    pvi = pd.Series(index=close.index, dtype=float)
    pvi.iloc[0] = 1000.0
    for i in range(1, len(close)):
        if volume.iloc[i] > volume.iloc[i - 1]:
            pct = (close.iloc[i] - close.iloc[i - 1]) / close.iloc[i - 1]
            pvi.iloc[i] = pvi.iloc[i - 1] * (1 + pct)
        else:
            pvi.iloc[i] = pvi.iloc[i - 1]
    return pvi


def nvi_calc(close, volume):
    nvi = pd.Series(index=close.index, dtype=float)
    nvi.iloc[0] = 1000.0
    for i in range(1, len(close)):
        if volume.iloc[i] < volume.iloc[i - 1]:
            pct = (close.iloc[i] - close.iloc[i - 1]) / close.iloc[i - 1]
            nvi.iloc[i] = nvi.iloc[i - 1] * (1 + pct)
        else:
            nvi.iloc[i] = nvi.iloc[i - 1]
    return nvi


def mfi_blai5(high, low, close, volume, length=14):
    src  = (high + low + close) / 3.0
    diff = src.diff()
    up   = (volume * np.where(diff > 0, src, 0)).rolling(length).sum()
    dn   = (volume * np.where(diff < 0, src, 0)).rolling(length).sum()
    rs   = up / dn.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

calc_mfi_blai5 = mfi_blai5  # alias Cell 0


def stoch_blai5(src, high, low, length=21, smooth=3):
    ll = low.rolling(length).min()
    hh = high.rolling(length).max()
    k  = 100 * (src - ll) / (hh - ll)
    return k.rolling(smooth).mean()

calc_stoch = stoch_blai5  # alias Cell 0


def koncorde(df, m=15):
    ohlc4  = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4.0
    close  = df["Close"]
    volume = df["Volume"]
    high   = df["High"]
    low    = df["Low"]

    pvi_s = pvi_calc(close, volume)
    nvi_s = nvi_calc(close, volume)
    pvim  = pvi_s.ewm(span=m, adjust=False).mean()
    nvim  = nvi_s.ewm(span=m, adjust=False).mean()

    oscp = (pvi_s - pvim) * 100 / (
        pvim.rolling(90).max() - pvim.rolling(90).min()
    ).replace(0, np.nan)
    azul = (nvi_s - nvim) * 100 / (
        nvim.rolling(90).max() - nvim.rolling(90).min()
    ).replace(0, np.nan)

    xmf     = mfi_blai5(high, low, close, volume, 14)
    basis   = ohlc4.rolling(25).mean()
    dev     = 2.0 * ohlc4.rolling(25).std()
    bollosc = ((ohlc4 - basis) / dev.replace(0, np.nan)) * 100
    xrsi    = RSIIndicator(close=ohlc4, window=14).rsi()
    stoc    = stoch_blai5(ohlc4, high, low, 21, 3)

    marron = (xrsi + xmf + bollosc + stoc / 3.0) / 2.0
    verde  = marron + oscp
    media  = marron.ewm(span=m, adjust=False).mean()

    out = pd.DataFrame(index=df.index)
    out["verde"]  = verde
    out["marron"] = marron
    out["azul"]   = azul
    out["media"]  = media
    return out

# alias usado en Cell 0
compute_blai5_koncorde = koncorde


def blai5_signals(kdf):
    kdf      = kdf.copy()
    valid    = kdf[["verde", "marron", "azul", "media"]].notna().all(axis=1)
    area_max = kdf[["verde", "marron", "azul"]].max(axis=1)
    area_min = kdf[["verde", "marron", "azul"]].min(axis=1)
    inside   = valid & (kdf["media"] >= area_min) & (kdf["media"] <= area_max)

    punto_media, velas_konk = [], []
    estado, conteo = None, 0
    for i in range(len(kdf)):
        if not valid.iloc[i]:
            punto_media.append(False); velas_konk.append(0); continue
        if inside.iloc[i]:
            if estado != "inside": estado, conteo = "inside", 1
            else: conteo += 1
            punto_media.append(True)
        else:
            if estado != "outside": estado, conteo = "outside", 1
            else: conteo += 1
            punto_media.append(False)
        velas_konk.append(conteo)

    kdf["punto_media_verde"] = punto_media
    kdf["velas_konk"]        = velas_konk
    return kdf


def calculate_bbwp(close, bb_len=13, lookback=252):
    basis = close.rolling(bb_len).mean()
    dev   = close.rolling(bb_len).std(ddof=0)
    bbw   = 2.0 * dev / basis.replace(0, np.nan)
    arr   = bbw.values
    n     = len(arr)
    bbwp  = np.full(n, np.nan)
    for i in range(bb_len, n):
        cur = arr[i]
        if np.isnan(cur):
            continue
        start  = max(0, i - lookback)
        window = arr[start:i]
        valid  = window[~np.isnan(window)]
        if len(valid) < 5:
            continue
        bbwp[i] = np.sum(valid <= cur) / len(valid) * 100.0
    return pd.Series(bbw, index=close.index), pd.Series(bbwp, index=close.index)


def bbwp_signal(bbwp_pct, bbwp_series):
    if pd.isna(bbwp_pct):
        return "⚪", "normal", "→", "nan%"
    if bbwp_pct < 20:
        punto = "🟢"; zona = "compresion"
    elif bbwp_pct > 80:
        punto = "🔴"; zona = "expansion"
    else:
        punto = "⚪"; zona = "normal"
    reciente = bbwp_series.dropna().iloc[-3:]
    if len(reciente) >= 2:
        slope = reciente.iloc[-1] - reciente.iloc[0]
        pendiente = "↑" if slope > 3 else ("↓" if slope < -3 else "→")
    else:
        pendiente = "→"
    return punto, zona, pendiente, f"{bbwp_pct:.1f}%"


def awesome_osc(high, low):
    med = (high + low) / 2.0
    return med.rolling(5).mean() - med.rolling(34).mean()

calcular_ao = awesome_osc  # alias Cell 0


def clasificar_bitman(df):
    if df is None or df.empty or len(df) < 60:
        return pd.DataFrame()
    out = df.copy()
    adx_ind = ADXIndicator(high=out["High"], low=out["Low"], close=out["Close"], window=14)
    out["ADX"]       = adx_ind.adx()
    out["ADX_Slope"] = out["ADX"].diff().rolling(3).mean()
    out["AO"]        = awesome_osc(out["High"], out["Low"])
    out["AO_Color"]  = np.where(out["AO"] > out["AO"].shift(1), "verde", "rojo")

    slope_mean_abs = out["ADX_Slope"].abs().rolling(20).mean()
    weak_thr       = (slope_mean_abs * 0.25).fillna(np.nan)

    out["ADX_Giro"]        = False
    out["Bitman_Color"]    = out["AO_Color"]
    out["Bitman_Etiqueta"] = "INDEFINICIÓN"
    out["Bitman_Velas"]    = 0

    last_turn_idx = None
    current_color = "verde"
    counter       = 0

    for i in range(len(out)):
        adx_slope_now = out["ADX_Slope"].iloc[i]
        ao_color_now  = out["AO_Color"].iloc[i]

        if (pd.isna(adx_slope_now) or pd.isna(weak_thr.iloc[i]) or
                abs(adx_slope_now) <= weak_thr.iloc[i]):
            counter += 1
            out.iloc[i, out.columns.get_loc("Bitman_Etiqueta")] = "INDEFINICIÓN"
            out.iloc[i, out.columns.get_loc("Bitman_Color")]    = ao_color_now
            out.iloc[i, out.columns.get_loc("Bitman_Velas")]    = counter
            continue

        adx_dir    = "impulso" if adx_slope_now > 0 else "retroceso"
        prev_slope = out["ADX_Slope"].iloc[i - 1] if i > 0 else np.nan
        prev_weak  = weak_thr.iloc[i - 1] if i > 0 else np.nan
        giro = (i > 0 and not pd.isna(prev_slope) and
                np.sign(prev_slope) != np.sign(adx_slope_now) and
                (pd.isna(prev_weak) or abs(prev_slope) > prev_weak))

        if giro:
            out.iloc[i, out.columns.get_loc("ADX_Giro")] = True
            last_turn_idx = i
            counter       = 1
            ao_w    = out["AO_Color"].iloc[max(0, i - 4): i + 1]
            changes = ao_w[ao_w != ao_w.shift(1)].dropna()
            if len(changes) >= 1:
                current_color = changes.iloc[-1]
        else:
            if last_turn_idx is not None and 0 < (i - last_turn_idx) <= 4:
                ao_w    = out["AO_Color"].iloc[last_turn_idx: i + 1]
                changes = ao_w[ao_w != ao_w.shift(1)].dropna()
                if len(changes) > 0:
                    current_color = changes.iloc[-1]
            counter = (i - last_turn_idx + 1) if last_turn_idx is not None else counter + 1

        etiqueta = ("IMPULSO ALCISTA"   if adx_dir == "impulso"   and current_color == "verde" else
                    "IMPULSO BAJISTA"   if adx_dir == "impulso"   and current_color == "rojo"  else
                    "RETROCESO ALCISTA" if adx_dir == "retroceso" and current_color == "verde" else
                    "RETROCESO BAJISTA")

        out.iloc[i, out.columns.get_loc("Bitman_Color")]    = current_color
        out.iloc[i, out.columns.get_loc("Bitman_Etiqueta")] = etiqueta
        out.iloc[i, out.columns.get_loc("Bitman_Velas")]    = counter

    return out


def detectar_divergencia(df, oscilador=None, lookback=50, order=2, max_gap=15):
    price = df["Close"].copy()
    if oscilador is None:
        ind = RSIIndicator(close=price, window=14).rsi()
    else:
        ind = oscilador.reindex(price.index) if hasattr(oscilador, "index") else oscilador.copy()

    n        = len(price)
    out_tipo = ["ninguna"] * n
    out_flag = ["⚪"] * n

    def find_pivots(series, kind="low", tol=0.003):
        pivots = []
        for i in range(order, n - order):
            val = series.iloc[i]
            if pd.isna(val):
                continue
            window = series.iloc[i - order: i + order + 1]
            if kind == "low":
                if val <= window.min() * (1 + tol) and val <= series.iloc[i-1] and val <= series.iloc[i+1]:
                    pivots.append(i)
            else:
                if val >= window.max() * (1 - tol) and val >= series.iloc[i-1] and val >= series.iloc[i+1]:
                    pivots.append(i)
        if not pivots:
            return pivots
        dedup = [pivots[0]]
        for p in pivots[1:]:
            if p - dedup[-1] <= order:
                if kind == "low":
                    dedup[-1] = p if series.iloc[p] < series.iloc[dedup[-1]] else dedup[-1]
                else:
                    dedup[-1] = p if series.iloc[p] > series.iloc[dedup[-1]] else dedup[-1]
            else:
                dedup.append(p)
        return dedup

    def nearest_pivot(base_idx, candidates):
        best, best_dist = None, 10**9
        for c in candidates:
            d = abs(c - base_idx)
            if d <= max_gap and d < best_dist:
                best, best_dist = c, d
        return best

    price_lows  = find_pivots(price, "low")
    price_highs = find_pivots(price, "high")
    ind_lows    = find_pivots(ind,   "low")
    ind_highs   = find_pivots(ind,   "high")

    for j in range(1, len(price_lows)):
        p1, p2 = price_lows[j-1], price_lows[j]
        if p2 - p1 > lookback:
            continue
        i1 = nearest_pivot(p1, ind_lows)
        i2 = nearest_pivot(p2, ind_lows)
        if i1 is None or i2 is None or i1 == i2:
            continue
        if price.iloc[p2] < price.iloc[p1] and ind.iloc[i2] > ind.iloc[i1]:
            out_tipo[p2] = "alcista"
            out_flag[p2] = "🟢"

    for j in range(1, len(price_highs)):
        p1, p2 = price_highs[j-1], price_highs[j]
        if p2 - p1 > lookback:
            continue
        i1 = nearest_pivot(p1, ind_highs)
        i2 = nearest_pivot(p2, ind_highs)
        if i1 is None or i2 is None or i1 == i2:
            continue
        if price.iloc[p2] > price.iloc[p1] and ind.iloc[i2] < ind.iloc[i1]:
            out_tipo[p2] = "bajista"
            out_flag[p2] = "🔴"

    result = df.copy()
    result["divergencia_tipo"] = out_tipo
    result["divergencia"]      = out_flag
    return result

# alias usado en Cell 0
detectar_divergencia_simple = detectar_divergencia


# ============================================================
# SEMÁFORO — Cell 0 exacto
# ============================================================

def azul_z_score(kdf, window=60):
    azul = kdf["azul"].dropna()
    if len(azul) < window + 4:
        return 0.0
    slope = azul.iloc[-1] - azul.iloc[-4]
    std   = azul.rolling(window).std().iloc[-1]
    if pd.isna(std) or std == 0:
        return 0.0
    return slope / std


def calcular_velas_señal(close, volume, kdf, macd_line, macd_signal_line, bitman_df):
    gap         = macd_line - macd_signal_line
    accel       = gap.diff()
    macd_activo = (gap > 0) & (accel > 0)
    v_macd      = velas_desde_activacion(macd_activo)

    azul        = kdf["azul"].fillna(0)
    azul_slope  = azul - azul.shift(3).fillna(0)
    azul_activo = (azul > 0) & (azul_slope > 0)
    v_azul      = velas_desde_activacion(azul_activo)

    media_activo = pd.Series(kdf["punto_media_verde"].values, index=kdf.index)
    v_media      = velas_desde_activacion(media_activo)

    pvi_s       = pvi_calc(close, volume)
    pvi_ema     = pvi_s.ewm(span=25, adjust=False).mean()
    pvi_gap     = pvi_s - pvi_ema
    pvi_activo  = (pvi_s > pvi_ema) & (pvi_gap.diff() > 0)
    v_pvi       = velas_desde_activacion(pvi_activo)

    _, bbwp_s   = calculate_bbwp(close, bb_len=13, lookback=252)
    bbwp_comp   = bbwp_s < 20
    indices_comp = np.where(bbwp_comp.fillna(False).values)[0]
    if len(indices_comp) == 0:
        v_bbwp_comp = 999
    else:
        v_bbwp_comp = len(bbwp_s) - 1 - indices_comp[-1]

    if bitman_df is not None and not bitman_df.empty:
        bitman_activo = pd.Series(
            (bitman_df["Bitman_Etiqueta"] == "IMPULSO ALCISTA").values,
            index=bitman_df.index
        )
        v_bitman = velas_desde_activacion(bitman_activo)
    else:
        v_bitman = 999

    return {
        "v_macd":      v_macd,
        "v_azul":      v_azul,
        "v_media":     v_media,
        "v_pvi":       v_pvi,
        "v_bbwp_comp": v_bbwp_comp,
        "v_bitman":    v_bitman,
    }


def semaforo(data, velas):
    macd_gap   = data["macd_gap"]
    macd_accel = data["macd_accel"]

    if macd_gap >= 0 and macd_accel > 0:
        c1 = "🟢"; c1_txt = f"MACD 🟢 acelerando ({velas['v_macd']}v)"
    elif macd_gap >= 0:
        c1 = "⚪"; c1_txt = "MACD ⚪ decelerando"
    else:
        c1 = "🔴"; c1_txt = "MACD 🔴 negativo"

    azul_verde = data["konk_azul_verde"]
    azul_slope = data.get("azul_slope", 0.0)
    if azul_verde and azul_slope > 0:
        c2 = "🟢"; c2_txt = f"Azul K 🟢 positivo↑ ({velas['v_azul']}v)"
    elif azul_verde:
        c2 = "⚪"; c2_txt = "Azul K ⚪ positivo plano"
    else:
        c2 = "🔴"; c2_txt = "Azul K 🔴 negativo"

    if data["konk_punto_verde"]:
        c3 = "🟢"; c3_txt = f"Media K 🟢 en área ({velas['v_media']}v)"
    else:
        c3 = "🔴"; c3_txt = "Media K 🔴 fuera"

    bbwp_pct       = data.get("bbwp_pct", 50.0)
    bbwp_pendiente = data.get("bbwp_pendiente", "→")
    v_bbwp_comp    = velas["v_bbwp_comp"]
    bbwp_comp_txt  = f" (compresión hace {v_bbwp_comp}v)" if v_bbwp_comp < 40 else ""

    if bbwp_pct > 60:
        c4 = "🟢"; c4_txt = f"BBWP 🟢 alto {bbwp_pct:.0f}%{bbwp_comp_txt}"
    elif bbwp_pct < 40 and bbwp_pendiente == "↑":
        c4 = "🟢"; c4_txt = f"BBWP 🟢 cargando {bbwp_pct:.0f}%↑"
    elif bbwp_pct < 40:
        c4 = "🔴"; c4_txt = f"BBWP 🔴 compresión plana {bbwp_pct:.0f}%"
    else:
        c4 = "⚪"; c4_txt = f"BBWP ⚪ zona media {bbwp_pct:.0f}%"

    pvi_activo = data.get("pvi_activo", False)
    pvi_accel  = data.get("pvi_accel",  False)
    if pvi_activo and pvi_accel:
        c8 = "🟢"; c8_txt = f"PVI 🟢 sobre EMA25 y acelerando ({velas['v_pvi']}v)"
    elif pvi_activo:
        c8 = "⚪"; c8_txt = "PVI ⚪ sobre EMA25 decelerando"
    else:
        c8 = "🔴"; c8_txt = "PVI 🔴 bajo EMA25"

    if data.get("cerca_mcg25") or data.get("cerca_e200"):
        c5 = "🟠"; c5_txt = "🟠 precio en zona soporte MCG25/EMA200"
    else:
        precio = data.get("precio", 0)
        e200   = data.get("e200", 0)
        c5     = "⚪" if precio > e200 else "🔴"
        c5_txt = "sobre EMA200" if precio > e200 else "🔴 bajo EMA200 — precaución"

    b_etiq  = data.get("bitman_etiqueta", "")
    b_velas = data.get("bitman_velas", 999)
    v_bfresh = velas["v_bitman"]

    if b_etiq == "IMPULSO ALCISTA":
        c6 = "🟢"; c6_txt = f"Bitman 🟢 impulso alcista (ciclo {b_velas}v / fresco {v_bfresh}v)"
    elif b_etiq == "RETROCESO ALCISTA":
        c6 = "⚪"; c6_txt = f"Bitman ⚪ retroceso alcista ({b_velas}v)"
    elif "BAJISTA" in b_etiq:
        c6 = "🔴"; c6_txt = f"Bitman 🔴 {b_etiq.lower()} ({b_velas}v)"
    else:
        c6 = "⚪"; c6_txt = f"Bitman ⚪ indefinición ({b_velas}v)"

    azul_z = data.get("azul_z", 0.0)
    if azul_z > 1.5:
        c7 = "⚡"; c7_txt = f"⚡ Azul pendiente fuerte (z={azul_z:.1f}) — movimiento violento probable"
    else:
        c7 = "⚪"; c7_txt = ""

    verde_val     = data.get("konk_verde_val", 0.0)
    azul_val      = data.get("konk_azul_val",  0.0)
    atención_konk = (verde_val < 0) and (azul_val > 0)

    div       = data.get("divergencia_tipo",  "ninguna")
    div_velas = data.get("divergencia_velas", 999)

    n_activas = sum([c1 == "🟢", c2 == "🟢", c3 == "🟢", c4 == "🟢", c8 == "🟢"])
    n_rojas   = sum([c1 == "🔴", c2 == "🔴", c3 == "🔴", c4 == "🔴", c8 == "🔴"])

    confluencia_fresca = (
        velas["v_macd"] <= 5 and
        velas["v_media"] <= 5 and
        c1 == "🟢" and
        c3 == "🟢"
    )

    señal_tardia  = (n_activas >= 4 and not confluencia_fresca)
    inicio_desact = (n_activas >= 3 and n_rojas >= 1 and (c1 == "🔴" or c3 == "🔴"))
    mayoria_desact = n_rojas >= 3

    if atención_konk and n_activas < 4:
        decision  = "⚠️ ATENCIÓN KONKORDE"; score_str = "K!"
    elif n_activas == 5 and confluencia_fresca and c6 == "🟢":
        decision  = "🚀 COMPRA 100%";       score_str = "5/5 + B"
    elif n_activas >= 4 and confluencia_fresca:
        decision  = "🟡 COMPRA 50%";        score_str = f"{n_activas}/5"
    elif n_activas >= 4 and señal_tardia:
        decision  = "⏰ LLEGAS TARDE";      score_str = f"tarde {n_activas}/5"
    elif inicio_desact:
        decision  = "⚠️ VIGILAR SALIDA";   score_str = f"sal {n_activas}/5"
    elif mayoria_desact:
        decision  = "🔴 VENTA";             score_str = f"{n_activas}/5"
    elif n_activas == 3:
        decision  = "👀 VIGILAR";           score_str = "3/5"
    elif n_activas <= 1 and n_rojas >= 3:
        decision  = "⛔ NI DE COÑA";       score_str = f"{n_activas}/5"
    else:
        decision  = "⛔ SIN SETUP";        score_str = f"{n_activas}/5"

    razones = [c1_txt, c2_txt, c3_txt, c4_txt, c8_txt, c5_txt, c6_txt]
    if c7 == "⚡":
        razones.append(c7_txt)
    if v_bbwp_comp < 30:
        razones.append(f"BBWP tuvo compresión hace {v_bbwp_comp}v — energía acumulada")
    if div == "alcista":
        if div_velas <= 5:    razones.append(f"🟢 Div alcista RSI FRESCA ({div_velas}v)")
        elif div_velas <= 20: razones.append(f"🟢 Div alcista RSI válida ({div_velas}v)")
        elif div_velas <= 50: razones.append(f"Div alcista RSI contexto ({div_velas}v)")
    elif div == "bajista" and div_velas <= 20:
        razones.append(f"🔴 Div bajista RSI ({div_velas}v) — cautela")
    precio = data.get("precio", 0)
    e200   = data.get("e200", 0)
    if precio < e200:
        razones.append("🔴 Precio bajo EMA200 — contexto bajista")
    if atención_konk:
        razones.append("⚠️ Verde K negativa + Azul K positivo — señal independiente potente")

    return {
        "decision": decision, "score": score_str,
        "c1": c1, "c2": c2, "c3": c3, "c4": c4, "c8": c8,
        "c5": c5, "c6": c6, "c7": c7,
        "atención_konk": atención_konk,
        "razones": " | ".join(r for r in razones if r),
    }


# ============================================================
# DASHBOARD — Cell 0: get_sovereign_dashboard (adaptado para
#   devolver dict en vez de sólo imprimir)
# ============================================================

def analyze_ticker(t):
    try:
        df = yf.download(t, period="2y", interval="1d",
                         auto_adjust=True, progress=False,
                         multi_level_index=False)
        df = clean_yf_df(df)
        if df.empty or len(df) < 150:
            return None

        close  = df["Close"]
        volume = df["Volume"]
        precio = close.iloc[-1]

        mcg25     = mcginley_dynamic(close, period=25)
        mcg25_val = mcg25.iloc[-1]
        e200_val  = EMAIndicator(close=close, window=200).ema_indicator().iloc[-1]

        offset_mcg  = 0.012
        offset_e200 = 0.015
        cerca_mcg   = mcg25_val * (1 - offset_mcg)  <= precio <= mcg25_val * (1 + offset_mcg)
        cerca_e200  = e200_val  * (1 - offset_e200) <= precio <= e200_val  * (1 + offset_e200)

        status_mcg  = "🟡" if cerca_mcg  else ("🟢" if precio > mcg25_val else "🔴")
        status_e200 = "🟡" if cerca_e200 else ("🟢" if precio > e200_val  else "🔴")
        trend_str   = f"MD25:{status_mcg} E200:{status_e200}"

        rsi = RSIIndicator(close=close).rsi()
        cruce_30_up   = (rsi > 30) & (rsi.shift(1) <= 30)
        cruce_70_down = (rsi < 70) & (rsi.shift(1) >= 70)
        is_active, velas_rsi = False, 0
        for i in range(len(rsi)):
            if cruce_30_up.iloc[i]:
                is_active = True; velas_rsi = 1
            elif is_active:
                if cruce_70_down.iloc[i] or velas_rsi >= 10:
                    is_active = False; velas_rsi = 0
                else:
                    velas_rsi += 1
        rsi_icon = "🟢" if is_active else "🔴"
        rsi_str  = f"{rsi_icon} {velas_rsi}v {'➕' if rsi.iloc[-1] > 50 else '➖'}"

        macd_obj         = MACD(close=close)
        macd_line        = macd_obj.macd()
        macd_signal_line = macd_obj.macd_signal()
        macd_diff        = macd_obj.macd_diff()
        gap              = macd_line - macd_signal_line
        gap_vol          = gap.abs().rolling(20).mean()
        accel            = (gap.diff() / gap_vol).fillna(0).iloc[-1]
        macd_gap_v       = gap.iloc[-1]
        estado_macd      = "Sep" if (gap.iloc[-1] * accel) >= 0 else "Jun"
        macd_icon        = "🟢" if macd_diff.iloc[-1] > 0 else "🔴"
        signo_linea      = "➕" if macd_line.iloc[-1] >= 0 else "➖"
        macd_str         = f"{macd_icon} {signo_linea} {accel:.2f} {estado_macd}"

        kdf = koncorde(df, m=15)
        if kdf.empty:
            return None
        kdf = blai5_signals(kdf)

        azul_verde    = kdf["azul"].iloc[-1] > 0
        azul_val_now  = float(kdf["azul"].iloc[-1])
        verde_val_now = float(kdf["verde"].iloc[-1])
        punto_verde   = kdf["punto_media_verde"].iloc[-1]
        velas_konk_v  = int(kdf["velas_konk"].iloc[-1])
        azul_icon     = "🟢" if azul_verde  else "🔴"
        punto_icon    = "🟢" if punto_verde else "🔴"
        konk_str      = f"{azul_icon}{punto_icon} {velas_konk_v}v"

        azul_z_val   = azul_z_score(kdf)
        azul_slope_v = 1.0 if (
            len(kdf["azul"].dropna()) >= 4 and
            kdf["azul"].iloc[-1] - kdf["azul"].iloc[-4] > 0
        ) else -1.0

        bitman_df    = clasificar_bitman(df)
        if bitman_df.empty:
            return None
        bitman_row     = bitman_df.iloc[-1]
        bitman_etiq    = bitman_row["Bitman_Etiqueta"]
        bitman_velas_v = int(bitman_row["Bitman_Velas"])
        bitman_alcista = bitman_etiq in ("IMPULSO ALCISTA", "RETROCESO ALCISTA")
        emoji_bitman   = "📈" if bitman_alcista else ("📉" if "BAJISTA" in bitman_etiq else "⬜")

        div_df = detectar_divergencia(df)
        hits   = div_df[div_df["divergencia_tipo"] != "ninguna"]
        if not hits.empty:
            div_tipo  = hits.iloc[-1]["divergencia_tipo"]
            div_idx   = div_df.index.get_loc(hits.index[-1])
            div_velas = len(div_df) - 1 - div_idx
        else:
            div_tipo  = "ninguna"
            div_velas = 999

        if div_tipo != "ninguna":
            emoji     = "🟢" if div_tipo == "alcista" else "🔴"
            emoji_ctx = "🟡" if div_tipo == "alcista" else "🟠"
            if div_velas <= 5:    div_str = f"{emoji} {div_tipo.upper()} FRESCA ({div_velas}v)"
            elif div_velas <= 20: div_str = f"{emoji} {div_tipo.upper()} válida ({div_velas}v)"
            elif div_velas <= 50: div_str = f"{emoji_ctx} {div_tipo.upper()} ctx ({div_velas}v)"
            else:                 div_str = f"⚪ {div_tipo} caduc ({div_velas}v)"
        else:
            div_str = "⚪"

        _, bbwp_s = calculate_bbwp(close, bb_len=13, lookback=252)
        bbwp_last = bbwp_s.iloc[-1]
        punto_bbwp, bbwp_zona, pendiente_bbwp, nivel_bbwp = bbwp_signal(bbwp_last, bbwp_s)
        bbwp_str = f"{punto_bbwp} {pendiente_bbwp} {nivel_bbwp}"

        pvi_s      = pvi_calc(close, volume)
        pvi_ema    = pvi_s.ewm(span=25, adjust=False).mean()
        pvi_gap    = pvi_s - pvi_ema
        pvi_activo = bool(pvi_s.iloc[-1] > pvi_ema.iloc[-1])
        pvi_accel  = bool(pvi_gap.diff().iloc[-1] > 0)

        velas_señal = calcular_velas_señal(
            close, volume, kdf, macd_line, macd_signal_line, bitman_df
        )

        pvi_icon  = "🟢" if (pvi_activo and pvi_accel) else ("⚪" if pvi_activo else "🔴")
        pvi_v     = velas_señal["v_pvi"]
        pvi_v_str = f"{pvi_v}v" if pvi_v < 999 else "—"
        pvi_str   = f"{pvi_icon} {pvi_v_str}"

        def fv(v):
            return f"{v}v" if v < 999 else "—"

        velas_str = (
            f"M:{fv(velas_señal['v_macd'])} "
            f"Az:{fv(velas_señal['v_azul'])} "
            f"Me:{fv(velas_señal['v_media'])} "
            f"B:{fv(velas_señal['v_bitman'])}"
        )

        bitman_str = (
            f"{bitman_etiq} "
            f"(ciclo {bitman_velas_v}v / fresco {fv(velas_señal['v_bitman'])}) "
            f"{emoji_bitman}"
        )

        input_data = {
            "precio":            precio,
            "e200":              e200_val,
            "cerca_mcg25":       cerca_mcg,
            "cerca_e200":        cerca_e200,
            "bitman_etiqueta":   bitman_etiq,
            "bitman_velas":      bitman_velas_v,
            "konk_azul_verde":   azul_verde,
            "konk_azul_val":     azul_val_now,
            "konk_verde_val":    verde_val_now,
            "konk_punto_verde":  punto_verde,
            "konk_velas":        velas_konk_v,
            "azul_z":            azul_z_val,
            "azul_slope":        azul_slope_v,
            "macd_gap":          macd_gap_v,
            "macd_accel":        accel,
            "pvi_activo":        pvi_activo,
            "pvi_accel":         pvi_accel,
            "divergencia_tipo":  div_tipo,
            "divergencia_velas": div_velas,
            "bbwp_pct":          float(bbwp_last) if not pd.isna(bbwp_last) else 50.0,
            "bbwp_zona":         bbwp_zona,
            "bbwp_pendiente":    pendiente_bbwp,
        }

        analisis = semaforo(input_data, velas_señal)

        return {
            "ticker":    t,
            "tendencia": trend_str,
            "rsi":       rsi_str,
            "macd":      macd_str,
            "koncorde":  konk_str,
            "pvi":       pvi_str,
            "bitman":    bitman_str,
            "div":       div_str,
            "bbwp":      bbwp_str,
            "velas":     velas_str,
            "score":     analisis["score"],
            "señal":     analisis["decision"],
            "razones":   analisis["razones"],
            "last_price": round(float(precio), 4),
            "last_date":  str(df.index[-1].date()),
        }

    except Exception as e:
        print(f"  ❌ {t}: {e}")
        return None


# ============================================================
# GRAFICADOR — Cell 1: plot_dashboard → devuelve PNG en base64
# ============================================================

def build_signals_graficador(df, mcg25, ema200, konc_df, pvi_s, pvi_ema,
                              macd_line, macd_hist, rsi_s, adx_s,
                              bitman=None, div_df=None):
    sigs = []

    def sig(label, bull, neutral=False):
        if neutral:
            return {"label": label, "state": "neutral"}
        return {"label": label, "state": "bull" if bull else "bear"}

    p = df["Close"].iloc[-1]
    sigs.append(sig(f"precio {'>' if p >= mcg25.iloc[-1] else '<'} MCG25",   p >= mcg25.iloc[-1]))
    sigs.append(sig(f"precio {'>' if p >= ema200.iloc[-1] else '<'} EMA200", p >= ema200.iloc[-1]))
    r = rsi_s.iloc[-1]
    sigs.append(sig(f"RSI {r:.1f}", r > 50, neutral=(45 < r < 55)))
    sigs.append(sig(f"MACD hist {'↑' if macd_hist.iloc[-1] >= 0 else '↓'}", macd_hist.iloc[-1] >= 0))
    sigs.append(sig(f"MACD línea {'≥0' if macd_line.iloc[-1] >= 0 else '<0'}", macd_line.iloc[-1] >= 0))
    sigs.append(sig(f"Azul Konc {'↑' if konc_df['azul'].iloc[-1] >= 0 else '↓'}", konc_df["azul"].iloc[-1] >= 0))
    sigs.append(sig(f"Verde {'>' if konc_df['verde'].iloc[-1] >= konc_df['marron'].iloc[-1] else '<'} Marrón",
                    konc_df["verde"].iloc[-1] >= konc_df["marron"].iloc[-1]))
    sigs.append(sig(f"PVI {'>' if pvi_s.iloc[-1] >= pvi_ema.iloc[-1] else '<'} EMA25",
                    pvi_s.iloc[-1] >= pvi_ema.iloc[-1]))
    a = adx_s.iloc[-1]
    sigs.append(sig(f"ADX {a:.1f} {'fuerte' if a > 25 else 'débil'}", a > 25, neutral=(18 < a < 25)))

    if bitman is not None and not bitman.empty:
        b_etiq  = bitman["Bitman_Etiqueta"].iloc[-1]
        b_velas = int(bitman["Bitman_Velas"].iloc[-1])
        b_bull  = b_etiq in ("IMPULSO ALCISTA", "RETROCESO ALCISTA")
        b_neut  = b_etiq == "INDEFINICIÓN"
        sigs.append(sig(f"Bitman {b_etiq[:8]} ({b_velas}v)", b_bull, neutral=b_neut))

    if div_df is not None:
        div_tipo = div_df["divergencia_tipo"].iloc[-1]
        if div_tipo == "alcista":
            sigs.append({"label": "Div RSI alcista", "state": "bull"})
        elif div_tipo == "bajista":
            sigs.append({"label": "Div RSI bajista", "state": "bear"})

    return sigs


def score_signals(sigs):
    bulls = sum(1 for s in sigs if s["state"] == "bull")
    bears = sum(1 for s in sigs if s["state"] == "bear")
    total = bulls + bears
    pct   = round(bulls / total * 100) if total else 0
    if pct >= 80:   label = "CONFLUENCIA MÁXIMA"
    elif pct >= 60: label = "SETUP SÓLIDO"
    elif pct >= 40: label = "SEÑALES MIXTAS"
    else:           label = "PRESIÓN BAJISTA"
    return pct, label, bulls, len(sigs)


def align_series(s, index):
    return s.reindex(index).values


def format_xaxis(ax, index, n_labels=8):
    step   = max(1, len(index) // n_labels)
    ticks  = list(range(0, len(index), step))
    labels = [index[i].strftime("%d %b") for i in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=7)


def panel_style(ax, ylabel="", yticks=5, zero_line=False):
    ax.set_ylabel(ylabel, fontsize=8, labelpad=4)
    ax.yaxis.set_major_locator(plt.MaxNLocator(yticks, prune="both"))
    ax.tick_params(axis="both", labelsize=7)
    ax.grid(True, axis="y", linewidth=0.4)
    ax.grid(True, axis="x", linewidth=0.2, alpha=0.4)
    if zero_line:
        ax.axhline(0, color=STYLE["zero"], linewidth=0.8, zorder=1)
    for spine in ax.spines.values():
        spine.set_edgecolor(STYLE["border"])


def render_chart(ticker, period="2y", interval="1d"):
    """
    Genera el gráfico multipanel exactamente como Cell 1.
    Devuelve imagen PNG en base64 o None si falla.
    """
    try:
        df = download(ticker, period, interval)
    except Exception as e:
        plt.close("all")
        return None, str(e)

    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    volume = df["Volume"]

    mcg25   = mcginley(close, 25)
    ema200  = EMAIndicator(close=close, window=200).ema_indicator()
    adx_ind = ADXIndicator(high=high, low=low, close=close, window=14)
    adx_s   = adx_ind.adx()
    pdi_s   = adx_ind.adx_pos()
    ndi_s   = adx_ind.adx_neg()
    ao_s    = awesome_osc(high, low)
    bitman  = clasificar_bitman(df)
    div_df  = detectar_divergencia(df)
    _, bbwp_s = calculate_bbwp(close, bb_len=13, lookback=252)
    konc    = koncorde(df, m=15)
    pvi_s   = pvi_calc(close, volume)
    pvi_ema = pvi_s.ewm(span=25, adjust=False).mean()
    macd_obj  = MACD(close=close, window_fast=12, window_slow=26, window_sign=9)
    macd_line = macd_obj.macd()
    macd_sig  = macd_obj.macd_signal()
    macd_hist = macd_obj.macd_diff()
    rsi_s   = RSIIndicator(close=close, window=14).rsi()

    sigs = build_signals_graficador(df, mcg25, ema200, konc, pvi_s, pvi_ema,
                                    macd_line, macd_hist, rsi_s, adx_s, bitman, div_df)
    pct, score_label, bull_n, total_n = score_signals(sigs)

    fig = plt.figure(figsize=(16, 20), facecolor=STYLE["bg"])
    fig.subplots_adjust(left=0.07, right=0.97, top=0.95, bottom=0.03, hspace=0.06)
    heights = [5, 2, 2.2, 1.4, 1.6, 1.8, 1.6]
    gs      = gridspec.GridSpec(7, 1, figure=fig, height_ratios=heights, hspace=0.06)
    axes    = [fig.add_subplot(gs[i]) for i in range(7)]
    for i in range(6):
        axes[i].tick_params(labelbottom=False)

    last_price = close.iloc[-1]
    prev_price = close.iloc[-2]
    chg        = last_price - prev_price
    pct_chg    = chg / prev_price * 100
    chg_color  = STYLE["bull"] if chg >= 0 else STYLE["bear"]
    sign       = "+" if chg >= 0 else ""

    fig.text(0.07, 0.965, ticker, fontsize=18, fontweight="bold", color=STYLE["text"], va="bottom")
    fig.text(0.19, 0.965, f"{last_price:.2f}", fontsize=16, fontweight="bold", color=STYLE["text"], va="bottom")
    fig.text(0.30, 0.965, f"{sign}{chg:.2f}  ({sign}{pct_chg:.2f}%)", fontsize=12, color=chg_color, va="bottom")
    score_color = STYLE["bull"] if pct >= 60 else (STYLE["bear"] if pct < 40 else STYLE["mcg"])
    fig.text(0.97, 0.965, f"{score_label}  ·  {bull_n}/{total_n}  ({pct}%)",
             fontsize=11, color=score_color, ha="right", va="bottom", style="italic")

    n_max   = min(252, len(df))
    df_plot = df.iloc[-n_max:]
    idx     = df_plot.index
    xs      = np.arange(len(idx))

    def sv(s):
        return align_series(s, idx)

    # Panel 0 — Velas + McGinley25 + EMA200
    ax0 = axes[0]
    w   = 0.4
    for i, (_, row) in enumerate(df_plot.iterrows()):
        col = STYLE["bull"] if row["Close"] >= row["Open"] else STYLE["bear"]
        ax0.plot([i, i], [row["Low"], row["High"]], color=col, lw=0.8, zorder=2)
        ax0.add_patch(plt.Rectangle(
            (i - w, min(row["Open"], row["Close"])),
            2 * w, max(abs(row["Close"] - row["Open"]), 0.001),
            color=col, zorder=3))
    ax0.plot(xs, sv(mcg25),  color=STYLE["mcg"],   lw=1.4, label="MCG 25",  zorder=4)
    ax0.plot(xs, sv(ema200), color=STYLE["ema200"], lw=1.4, label="EMA 200", zorder=4)
    ax0.set_xlim(-1, len(idx))
    ax0.legend(loc="upper left", fontsize=8, frameon=False,
               labelcolor=[STYLE["mcg"], STYLE["ema200"]])
    panel_style(ax0, ylabel="Precio")
    ax0.set_title("Velas  ·  McGinley 25  ·  EMA 200",
                  fontsize=9, color=STYLE["muted"], loc="right", pad=4)
    format_xaxis(ax0, idx)
    ax0.tick_params(labelbottom=True)

    # Panel 1 — ADX + AO
    ax1  = axes[1]
    ax1r = ax1.twinx()
    ao_vals   = sv(ao_s)
    ao_prev   = np.roll(ao_vals, 1); ao_prev[0] = ao_vals[0]
    ao_colors = [STYLE["ao_up"] if ao_vals[i] >= ao_prev[i] else STYLE["ao_dn"]
                 for i in range(len(ao_vals))]
    ax1r.bar(xs, ao_vals, color=ao_colors, alpha=0.7, width=0.8, zorder=2)
    ax1r.axhline(0, color=STYLE["zero"], lw=0.7)
    ax1r.tick_params(labelsize=7, colors=STYLE["muted"])
    ax1r.set_ylabel("AO", fontsize=7, color=STYLE["muted"])
    ax1r.spines["right"].set_edgecolor(STYLE["border"])
    ax1.plot(xs, sv(adx_s), color=STYLE["adx"], lw=1.4, label="ADX", zorder=3)
    ax1.plot(xs, sv(pdi_s), color=STYLE["pdi"], lw=0.9, ls="--", label="+DI", zorder=3)
    ax1.plot(xs, sv(ndi_s), color=STYLE["ndi"], lw=0.9, ls="--", label="-DI", zorder=3)
    ax1.axhline(25, color=STYLE["muted"], lw=0.6, ls=":")
    ax1.legend(loc="upper left", fontsize=7, frameon=False,
               labelcolor=[STYLE["adx"], STYLE["pdi"], STYLE["ndi"]])
    panel_style(ax1, ylabel="ADX")
    ax1.set_title("ADX  ·  +DI / -DI  ·  Awesome Oscillator",
                  fontsize=9, color=STYLE["muted"], loc="right", pad=4)

    # Panel 2 — Blai5 Koncorde
    ax2 = axes[2]
    ax2.fill_between(xs, sv(konc["verde"]),  alpha=0.45, color=STYLE["verde"],  label="Verde",  zorder=2)
    ax2.fill_between(xs, sv(konc["marron"]), alpha=0.35, color=STYLE["marron"], label="Marrón", zorder=2)
    ax2.fill_between(xs, sv(konc["azul"]),   alpha=0.35, color=STYLE["azul"],   label="Azul",   zorder=2)
    ax2.plot(xs, sv(konc["verde"]),  color=STYLE["verde"],   lw=1.0, zorder=3)
    ax2.plot(xs, sv(konc["marron"]), color=STYLE["marron"],  lw=1.0, zorder=3)
    ax2.plot(xs, sv(konc["azul"]),   color=STYLE["azul"],    lw=1.0, zorder=3)
    ax2.plot(xs, sv(konc["media"]),  color=STYLE["media_k"], lw=1.6, label="Media", zorder=4)
    ax2.axhline(0, color=STYLE["zero"], lw=0.7)
    ax2.legend(loc="upper left", fontsize=7, frameon=False,
               labelcolor=[STYLE["verde"], STYLE["marron"], STYLE["azul"], STYLE["media_k"]])
    panel_style(ax2, ylabel="Koncorde")
    ax2.set_title("Blai5 Koncorde  ·  Verde / Marrón / Azul / Media",
                  fontsize=9, color=STYLE["muted"], loc="right", pad=4)

    # Panel 3 — BBWP 13/252
    ax3    = axes[3]
    bbwp_v = sv(bbwp_s)
    ax3.fill_between(xs, bbwp_v, 20,
                     where=(~np.isnan(bbwp_v)) & (bbwp_v < 20),
                     alpha=0.20, color=STYLE["azul"], zorder=1)
    ax3.fill_between(xs, bbwp_v, 80,
                     where=(~np.isnan(bbwp_v)) & (bbwp_v > 80),
                     alpha=0.20, color=STYLE["bear"], zorder=1)
    bbwp_arr = bbwp_v.copy()
    for i in range(1, len(xs)):
        if np.isnan(bbwp_arr[i]) or np.isnan(bbwp_arr[i-1]):
            continue
        mid_val = (bbwp_arr[i] + bbwp_arr[i-1]) / 2
        lc = STYLE["azul"] if mid_val < 20 else (STYLE["bear"] if mid_val > 80 else STYLE["muted"])
        ax3.plot([xs[i-1], xs[i]], [bbwp_arr[i-1], bbwp_arr[i]], color=lc, lw=1.5, zorder=3)
    ax3.axhline(80, color=STYLE["bear"],  lw=0.7, ls="--", alpha=0.6)
    ax3.axhline(20, color=STYLE["azul"],  lw=0.7, ls="--", alpha=0.6)
    ax3.axhline(50, color=STYLE["muted"], lw=0.5, ls=":",  alpha=0.4)
    ax3.set_ylim(-2, 102)
    ax3.yaxis.set_ticks([0, 20, 50, 80, 100])
    panel_style(ax3, ylabel="BBWP")
    ax3.set_title("BBWP 13/252  ·  🟢 compresión < 20  ·  🔴 expansión > 80",
                  fontsize=9, color=STYLE["muted"], loc="right", pad=4)

    # Panel 4 — PVI + EMA 25
    ax4   = axes[4]
    pvi_v = sv(pvi_s)
    pvi_e = sv(pvi_ema)
    ax4.fill_between(xs, pvi_v, pvi_e, where=(pvi_v >= pvi_e), alpha=0.18, color=STYLE["bull"])
    ax4.fill_between(xs, pvi_v, pvi_e, where=(pvi_v <  pvi_e), alpha=0.18, color=STYLE["bear"])
    ax4.plot(xs, pvi_v, color=STYLE["pvi"],     lw=1.4, label="PVI")
    ax4.plot(xs, pvi_e, color=STYLE["pvi_ema"], lw=1.4, ls="--", label="EMA 25")
    ax4.legend(loc="upper left", fontsize=7, frameon=False,
               labelcolor=[STYLE["pvi"], STYLE["pvi_ema"]])
    panel_style(ax4, ylabel="PVI")
    ax4.set_title("PVI  ·  EMA 25", fontsize=9, color=STYLE["muted"], loc="right", pad=4)

    # Panel 5 — MACD
    ax5       = axes[5]
    hist_v    = sv(macd_hist)
    hist_prev = np.roll(hist_v, 1); hist_prev[0] = hist_v[0]
    bar_colors = []
    for i in range(len(hist_v)):
        v, p = hist_v[i], hist_prev[i]
        if np.isnan(v):
            bar_colors.append(STYLE["muted"]); continue
        if v >= 0:
            bar_colors.append(STYLE["bull"] if v >= p else STYLE["bull_fade"])
        else:
            bar_colors.append(STYLE["bear"] if v <= p else STYLE["bear_fade"])
    ax5.bar(xs, hist_v, color=bar_colors, width=0.8, alpha=0.9, zorder=2)
    ax5.plot(xs, sv(macd_line), color=STYLE["macd_line"], lw=1.3, label="MACD",  zorder=3)
    ax5.plot(xs, sv(macd_sig),  color=STYLE["macd_sig"],  lw=1.3, ls="--", label="Señal", zorder=3)
    ax5.axhline(0, color=STYLE["zero"], lw=0.7)
    ax5.legend(loc="upper left", fontsize=7, frameon=False,
               labelcolor=[STYLE["macd_line"], STYLE["macd_sig"]])
    panel_style(ax5, ylabel="MACD")
    ax5.set_title("MACD  12 / 26 / 9", fontsize=9, color=STYLE["muted"], loc="right", pad=4)

    # Panel 6 — RSI + divergencias
    ax6   = axes[6]
    rsi_v = sv(rsi_s)
    ax6.fill_between(xs, rsi_v, 70, where=(rsi_v > 70), alpha=0.25, color=STYLE["bull"])
    ax6.fill_between(xs, rsi_v, 30, where=(rsi_v < 30), alpha=0.25, color=STYLE["bear"])
    ax6.plot(xs, rsi_v, color=STYLE["rsi"], lw=1.4)
    for level, col, ls in [(70, STYLE["bear"], "--"), (50, STYLE["muted"], ":"), (30, STYLE["bull"], "--")]:
        ax6.axhline(level, color=col, lw=0.7, ls=ls)
    if div_df is not None:
        div_tipos = align_series(div_df["divergencia_tipo"], idx)
        div_rsi_v = align_series(RSIIndicator(close=close, window=14).rsi(), idx)
        for xi_d, (dt, rv) in enumerate(zip(div_tipos, div_rsi_v)):
            if dt == "alcista":
                ax6.annotate("▲", xy=(xi_d, rv), fontsize=8, color=STYLE["bull"],
                             ha="center", va="top", xytext=(0, -8), textcoords="offset points")
            elif dt == "bajista":
                ax6.annotate("▼", xy=(xi_d, rv), fontsize=8, color=STYLE["bear"],
                             ha="center", va="bottom", xytext=(0, 8), textcoords="offset points")
    ax6.set_ylim(0, 100)
    ax6.yaxis.set_ticks([30, 50, 70])
    panel_style(ax6, ylabel="RSI", yticks=3)
    format_xaxis(ax6, idx)
    ax6.tick_params(labelbottom=True)
    ax6.set_title("RSI  14  ·  ▲ div alcista  ▼ div bajista",
                  fontsize=9, color=STYLE["muted"], loc="right", pad=4)

    for ax in axes:
        ax.set_xlim(-1, len(idx))

    # Recuadro informativo
    _mcg_val  = mcg25.iloc[-1]
    _e200_val = ema200.iloc[-1]
    _precio   = close.iloc[-1]
    _rsi_val  = rsi_s.iloc[-1]
    _azul_verde  = konc["azul"].iloc[-1] > 0
    _area_max    = konc[["verde", "marron", "azul"]].max(axis=1)
    _area_min    = konc[["verde", "marron", "azul"]].min(axis=1)
    _media_val   = konc["media"].iloc[-1]
    _punto_verde = (not pd.isna(_media_val) and
                    _area_min.iloc[-1] <= _media_val <= _area_max.iloc[-1])
    _ak = "🟢" if _azul_verde  else "🔴"
    _pk = "🟢" if _punto_verde else "🔴"
    _pvi_str = "🟢 PVI>" if pvi_s.iloc[-1] > pvi_ema.iloc[-1] else "🔴 PVI<"
    if bitman is not None and not bitman.empty:
        _b_etiq  = bitman["Bitman_Etiqueta"].iloc[-1]
        _b_velas = int(bitman["Bitman_Velas"].iloc[-1])
        _b_emoji = ("📈" if _b_etiq in ("IMPULSO ALCISTA", "RETROCESO ALCISTA")
                    else ("📉" if "BAJISTA" in _b_etiq else "⬜"))
        _bitman_str = f"{_b_etiq} ({_b_velas}v) {_b_emoji}"
    else:
        _bitman_str = "N/D"
    if div_df is not None:
        _hits = div_df[div_df["divergencia_tipo"] != "ninguna"]
        if not _hits.empty:
            _dlast  = _hits.iloc[-1]["divergencia_tipo"]
            _didx   = div_df.index.get_loc(_hits.index[-1])
            _dvelas = len(div_df) - 1 - _didx
            _de     = "🟢" if _dlast == "alcista" else "🔴"
            if _dvelas <= 5:    _div_str = f"{_de} {_dlast.upper()} FRESCA ({_dvelas}v)"
            elif _dvelas <= 20: _div_str = f"{_de} {_dlast.upper()} válida ({_dvelas}v)"
            elif _dvelas <= 50: _div_str = f"{'🟡' if _dlast=='alcista' else '🟠'} {_dlast.upper()} contexto ({_dvelas}v)"
            else:               _div_str = f"⚪ {_dlast} caducada ({_dvelas}v)"
        else:
            _div_str = "⚪ sin divergencia"
    else:
        _div_str = "⚪"
    _bbwp_val = bbwp_s.dropna().iloc[-1] if len(bbwp_s.dropna()) > 0 else np.nan
    if not np.isnan(_bbwp_val):
        _bbwp_punto   = "🟢" if _bbwp_val < 20 else ("🔴" if _bbwp_val > 80 else "⚪")
        _bbwp_box_str = f"{_bbwp_punto} {_bbwp_val:.1f}%  (13/252)"
    else:
        _bbwp_box_str = "⚪ n/d"
    _mcg_sym  = "🟡" if abs(_precio / _mcg_val  - 1) < 0.012 else ("🟢" if _precio > _mcg_val  else "🔴")
    _e200_sym = "🟡" if abs(_precio / _e200_val - 1) < 0.015 else ("🟢" if _precio > _e200_val else "🔴")
    _lines = [
        f"Tendencia  MCG25:{_mcg_sym}  EMA200:{_e200_sym}   RSI:{_rsi_val:.1f}",
        f"Koncorde   Azul:{_ak}  Punto:{_pk}",
        f"PVI        {_pvi_str} EMA25",
        f"BBWP       {_bbwp_box_str}",
        f"Bitman     {_bitman_str}",
        f"Div RSI    {_div_str}",
        f"SCORE      {score_label}  ·  {bull_n}/{total_n}  ({pct}%)",
    ]
    _box_x, _box_y = 0.07, 0.870
    _box_h         = 0.095
    _box_w         = 0.27
    _box_ax = fig.add_axes([_box_x, _box_y - _box_h, _box_w, _box_h], frameon=True)
    _box_ax.set_facecolor(STYLE["panel"])
    for spine in _box_ax.spines.values():
        spine.set_edgecolor(STYLE["border"])
        spine.set_linewidth(0.8)
    _box_ax.set_xticks([]); _box_ax.set_yticks([])
    for li, line in enumerate(_lines):
        _col = score_color if li == 6 else STYLE["text"]
        _box_ax.text(0.03, 0.94 - li * 0.135, line,
                     transform=_box_ax.transAxes,
                     fontsize=7, color=_col, va="top", family="monospace")

    # Barra de señales
    sig_y = 0.01; sig_h = 0.016; x0 = 0.07
    gap_w = (0.97 - x0) / len(sigs)
    for i, s in enumerate(sigs):
        col = (STYLE["bull"] if s["state"] == "bull" else
               STYLE["bear"] if s["state"] == "bear" else STYLE["muted"])
        xi  = x0 + i * gap_w
        fig.text(xi + (gap_w - 0.003) / 2, sig_y + sig_h / 2,
                 s["label"], fontsize=7.5, color=col,
                 ha="center", va="center",
                 bbox=dict(boxstyle="round,pad=0.3", facecolor=STYLE["panel"],
                           edgecolor=col + "66", linewidth=0.8))

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=STYLE["bg"])
    plt.close("all")  # libera memoria — crítico en GitHub Actions
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    return b64, None


# ============================================================
# HTML
# ============================================================

ORDEN_SEÑAL = {
    "⚠️ ATENCIÓN KONKORDE": 0,
    "🚀 COMPRA 100%":        1,
    "🟡 COMPRA 50%":         2,
    "👀 VIGILAR":            3,
    "⏰ LLEGAS TARDE":       4,
    "⚠️ VIGILAR SALIDA":    5,
    "🔴 VENTA":              6,
    "⛔ SIN SETUP":          7,
    "⛔ NI DE COÑA":         8,
}


def build_html(rows):
    # Ya no necesitamos rows_json aquí porque cargaremos el JSON desde un archivo
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LCrack Sovereign</title>
<style>
/* ... (tu CSS se mantiene igual) ... */
:root{{
  --bg:#0d0f14;--panel:#13161e;--panel2:#1a1e28;--border:#1f2430;
  --text:#c8cad0;--muted:#555a6a;
  --bull:#26a65b;--bear:#e04040;--warn:#efb030;
}}
*{box-sizing:border-box;margin:0;padding:0}
body{{font-family:monospace,monospace;background:var(--bg);color:var(--text);min-height:100vh}}
.app{{max-width:1700px;margin:auto;padding:20px}}
h1{{font-size:22px;font-weight:900;margin-bottom:4px}}
.sub{{color:var(--muted);font-size:12px;margin-bottom:16px}}
.tabs{{display:flex;gap:4px;margin-bottom:16px;border-bottom:1px solid var(--border)}}
.tab-btn{{padding:9px 18px;background:transparent;border:none;color:var(--muted);
  font-size:13px;font-weight:700;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}}
.tab-btn.active{{color:#60a5fa;border-bottom-color:#60a5fa}}
.tab-pane{{display:none}}.tab-pane.active{{display:block}}
.card{{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px}}
.filters{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;align-items:center}}
.filters input,.filters select{{
  background:var(--panel2);border:1px solid var(--border);color:var(--text);
  border-radius:6px;padding:7px 10px;font-size:12px;font-family:monospace}}
.tbl-wrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:var(--panel2);color:var(--muted);text-align:left;padding:8px 10px;
  font-size:10px;text-transform:uppercase;letter-spacing:.05em;position:sticky;top:0}}
td{{border-top:1px solid rgba(255,255,255,.05);padding:8px 10px;vertical-align:top}}
tr:hover td{{background:rgba(255,255,255,.03)}}
.ticker{{font-weight:900;font-size:14px;cursor:pointer;color:#60a5fa}}
.ticker:hover{{text-decoration:underline}}
.razones{{font-size:10px;color:var(--muted);margin-top:3px;max-width:600px}}
/* Señal colors */
.s0{{color:#efb030}}.s1{{color:var(--bull)}}.s2{{color:#a3e635}}
.s3{{color:#60a5fa}}.s4{{color:#f59e0b}}.s5{{color:#fb923c}}
.s6{{color:var(--bear)}}.s7{{color:var(--muted)}}.s8{{color:var(--bear)}}
/* Graficador */
.g-search-wrap{{display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap}}
#g-input{{font-size:15px;font-weight:900;padding:9px 12px;border-radius:8px;
  background:var(--panel2);border:1px solid var(--border);color:var(--text);
  width:160px;text-transform:uppercase;font-family:monospace}}
.btn{{background:rgba(37,99,235,.35);border:1px solid rgba(96,165,250,.4);
  color:#fff;border-radius:6px;padding:8px 14px;font-weight:800;cursor:pointer;font-family:monospace}}
.chips{{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px}}
.chip{{padding:3px 9px;border-radius:999px;font-size:11px;font-weight:700;cursor:pointer;
  background:var(--panel2);border:1px solid var(--border);color:var(--muted);font-family:monospace}}
.chip:hover{{border-color:#60a5fa;color:#60a5fa}}
#g-img{{max-width:100%;border-radius:8px;margin-top:8px}}
#g-loading{{color:var(--muted);font-size:12px;padding:8px 0}}
</style>
</head>
<body>
<div class="app">
  <h1>LCrack Sovereign</h1>
  <div class="sub" id="subtitle">Cargando datos...</div>
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('dashboard',this)">📊 Dashboard</button>
    <button class="tab-btn" onclick="switchTab('graficador',this)">📈 Graficador</button>
  </div>

  <div id="tab-dashboard" class="tab-pane active">
    <div class="card">
      <div class="filters">
        <input id="d-q" placeholder="Buscar ticker..." oninput="renderDashboard()" style="width:160px">
        <select id="d-señal" onchange="renderDashboard()">
          <option value="">Todas las señales</option>
          <option value="COMPRA 100">🚀 Compra 100%</option>
          <option value="COMPRA 50">🟡 Compra 50%</option>
          <option value="VIGILAR SALIDA">⚠️ Vigilar salida</option>
          <option value="VIGILAR">👀 Vigilar</option>
          <option value="VENTA">🔴 Venta</option>
          <option value="TARDE">⏰ Tarde</option>
          <option value="KONKORDE">⚠️ Konkorde</option>
          <option value="SIN SETUP">⛔ Sin setup</option>
        </select>
        <select id="d-sort" onchange="renderDashboard()">
          <option value="señal">Orden señal</option>
          <option value="ticker">Ticker A-Z</option>
        </select>
      </div>
      <div class="tbl-wrap"><div id="d-table"></div></div>
    </div>
  </div>

  <div id="tab-graficador" class="tab-pane">
    <div class="card">
      <div class="g-search-wrap">
        <input id="g-input" placeholder="AAPL" onkeydown="if(event.key==='Enter')loadChart()" oninput="filterChips()">
        <button class="btn" onclick="loadChart()">Analizar</button>
        <span style="color:var(--muted);font-size:11px">Tickers del universo escaneado</span>
      </div>
      <div id="g-chips" class="chips"></div>
      <div id="g-loading"></div>
      <img id="g-img" style="display:none">
    </div>
  </div>
</div>

<script>
// Cargamos los datos de forma asíncrona
var ROWS = [];
var ORDEN = {json.dumps(ORDEN_SEÑAL, ensure_ascii=False)};

fetch('./data.json')
  .then(response => response.json())
  .then(data => {{
      ROWS = data;
      init();
  }})
  .catch(err => {{
      document.getElementById('subtitle').textContent = 'Error cargando datos';
      console.error(err);
  }});

function switchTab(id, btn) {{
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
}}

function señalClass(s) {{
  var orden = ORDEN[s];
  if (orden === undefined) return 's7';
  return 's' + orden;
}}

function init() {{
  var n = ROWS.filter(r => r.señal).length;
  document.getElementById('subtitle').textContent =
    'Última actualización: ' + (ROWS[0] && ROWS[0].generated_at ? ROWS[0].generated_at : '—') +
    ' · ' + ROWS.length + ' activos analizados';
  renderDashboard();
  buildChips();
}}

function renderDashboard() {{
  var q  = (document.getElementById('d-q').value || '').toUpperCase();
  var sf = document.getElementById('d-señal').value || '';
  var so = document.getElementById('d-sort').value;

  var data = ROWS.filter(r => {{
    if (q && !r.ticker.includes(q)) return false;
    if (sf && !(r.señal || '').includes(sf)) return false;
    return true;
  }});

  if (so === 'ticker') data.sort((a,b) => a.ticker.localeCompare(b.ticker));
  else data.sort((a,b) => (ORDEN[a.señal]||9) - (ORDEN[b.señal]||9) || a.ticker.localeCompare(b.ticker));

  var html = '<table><thead><tr>'
    + '<th>Ticker</th><th>Señal</th><th>Score</th><th>Tendencia</th>'
    + '<th>RSI</th><th>MACD</th><th>Koncorde</th><th>PVI</th>'
    + '<th>Bitman</th><th>Div</th><th>BBWP</th><th>Velas⏱</th><th>Precio</th>'
    + '</tr></thead><tbody>';

  data.forEach(r => {{
    var sc = señalClass(r.señal);
    html += '<tr>'
      + '<td><span class="ticker" onclick="openGraficador(\'' + r.ticker + '\')">' + r.ticker + '</span></td>'
      + '<td class="' + sc + '">' + (r.señal||'—') + '</td>'
      + '<td>' + (r.score||'—') + '</td>'
      + '<td>' + (r.tendencia||'—') + '</td>'
      + '<td>' + (r.rsi||'—') + '</td>'
      + '<td>' + (r.macd||'—') + '</td>'
      + '<td>' + (r.koncorde||'—') + '</td>'
      + '<td>' + (r.pvi||'—') + '</td>'
      + '<td style="font-size:11px">' + (r.bitman||'—') + '</td>'
      + '<td>' + (r.div||'—') + '</td>'
      + '<td>' + (r.bbwp||'—') + '</td>'
      + '<td style="font-size:10px;color:var(--muted)">' + (r.velas||'—') + '</td>'
      + '<td>' + (r.last_price !== undefined ? r.last_price : '—') + '</td>'
      + '</tr>'
      + '<tr><td colspan="13" class="razones">' + (r.razones||'') + '</td></tr>';
  }});

  html += '</tbody></table>';
  document.getElementById('d-table').innerHTML = data.length ? html
    : '<p style="padding:16px;color:var(--muted)">Sin resultados.</p>';
}}

function openGraficador(ticker) {{
  document.getElementById('g-input').value = ticker;
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-graficador').classList.add('active');
  document.querySelectorAll('.tab-btn')[1].classList.add('active');
  loadChart();
}}

function buildChips() {{
  var el = document.getElementById('g-chips');
  el.innerHTML = ROWS.map(r => {{
    var top = ORDEN[r.señal] !== undefined && ORDEN[r.señal] <= 2;
    return '<span class="chip' + (top ? ' has-signal' : '') + '" onclick="selectChip(\'' + r.ticker + '\')">' + r.ticker + '</span>';
  }}).join('');
}}

function filterChips() {{
  var q = document.getElementById('g-input').value.toUpperCase();
  document.querySelectorAll('#g-chips .chip').forEach(c => {{
    c.style.display = (!q || c.textContent.includes(q)) ? '' : 'none';
  }});
}}

function selectChip(t) {{
  document.getElementById('g-input').value = t;
  loadChart();
}}

async function loadChart() {{
  var ticker = document.getElementById('g-input').value.trim().toUpperCase();
  if (!ticker) return;
  var loading = document.getElementById('g-loading');
  var img     = document.getElementById('g-img');
  loading.textContent = 'Cargando gráfico de ' + ticker + '...';
  img.style.display = 'none';
  try {{
    // Usamos ruta relativa pura para asegurar compatibilidad en gh-pages
    var resp = await fetch('data/charts/' + ticker.replace('=','').replace('-','_') + '.b64');
    if (!resp.ok) throw new Error('No disponible');
    var b64 = await resp.text();
    img.src = 'data:image/png;base64,' + b64.trim();
    img.style.display = 'block';
    loading.textContent = '';
  }} catch(e) {{
    loading.textContent = '❌ ' + ticker + ': gráfico no disponible — ' + e.message;
  }}
}}
</script>
</body>
</html>
"""
