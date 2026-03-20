import streamlit as st
import yfinance as yf
import anthropic

st.set_page_config(page_title="Short Squeeze Scanner", page_icon="🚨", layout="centered")
st.title("🚨 Short Squeeze Scanner")
st.caption("Scans for high short interest + unusual volume — potential squeeze candidates")

# ── Sidebar config ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("Anthropic API Key", type="password",
                            help="Get one free at console.anthropic.com")
    st.markdown("---")
    tickers_input = st.text_area(
        "Stocks to scan (one per line)",
        value="GME\nAMC\nMSTR\nRKLB\nNVDA\nSPY\nTSLA",
        height=180
    )
    min_score = st.slider("Alert threshold (score out of 100)", 0, 100, 55)
    st.markdown("---")
    st.markdown("**Score guide**")
    st.markdown("🔴 70+ = High squeeze risk")
    st.markdown("🟡 50–69 = Watch closely")
    st.markdown("🟢 Below 50 = Low risk")

# ── Helper functions ─────────────────────────────────────────────
def get_metrics(ticker):
    try:
        s = yf.Ticker(ticker)
        info = s.info
        hist = s.history(period="20d")
        if hist.empty or len(hist) < 6:
            return None
        avg_vol = hist["Volume"].mean()
        today_vol = hist["Volume"].iloc[-1]
        price_now = hist["Close"].iloc[-1]
        price_5d = hist["Close"].iloc[-5]
        return {
            "ticker": ticker,
            "short_pct_float": round((info.get("shortPercentOfFloat") or 0) * 100, 1),
            "short_ratio":     round(info.get("shortRatio") or 0, 1),
            "volume_ratio":    round(today_vol / avg_vol if avg_vol > 0 else 0, 1),
            "price_change_5d": round((price_now / price_5d - 1) * 100, 1),
            "current_price":   round(price_now, 2),
            "market_cap":      info.get("marketCap"),
        }
    except Exception as e:
        return None

def squeeze_score(m):
    s  = min(m["short_pct_float"] / 50 * 40, 40)   # up to 40 pts
    s += min(m["short_ratio"]     / 10 * 20, 20)   # up to 20 pts
    s += min(m["volume_ratio"]    / 5  * 25, 25)   # up to 25 pts
    s += min(max(m["price_change_5d"], 0) / 20 * 15, 15)  # up to 15 pts
    return round(s, 1)

def score_color(sc):
    if sc >= 70: return "🔴"
    if sc >= 50: return "🟡"
    return "🟢"

def get_ai_analysis(m, sc, key):
    client = anthropic.Anthropic(api_key=key)
    prompt = f"""You are a stock analyst. Analyze this short squeeze candidate briefly:

Ticker: {m['ticker']} | Price: ${m['current_price']}
Short % of float: {m['short_pct_float']}% | Days to cover: {m['short_ratio']}
Volume vs 20-day avg: {m['volume_ratio']}x | 5-day price change: {m['price_change_5d']}%
Squeeze score: {sc}/100

Reply in exactly 3 short bullet points:
- Squeeze thesis (why it could squeeze)
- Main risk
- Confidence level: Low / Medium / High — and one reason why"""

    r = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=250,
        messages=[{"role": "user", "content": prompt}]
    )
    return r.content[0].text

# ── Main scan button ─────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
run = col1.button("🔍  Run Scan Now", type="primary", use_container_width=True)
col2.button("🔄 Reset", use_container_width=True)

if run:
    tickers = [t.strip().upper() for t in tickers_input.strip().splitlines() if t.strip()]
    if not tickers:
        st.error("Add at least one ticker in the sidebar.")
        st.stop()

    st.divider()
    progress = st.progress(0, text="Starting scan...")
    all_results = []

    for i, ticker in enumerate(tickers):
        progress.progress((i + 1) / len(tickers), text=f"Scanning {ticker}…")
        m = get_metrics(ticker)
        if m:
            sc = squeeze_score(m)
            all_results.append((sc, m))

    progress.empty()
    all_results.sort(reverse=True)

    alerts  = [(sc, m) for sc, m in all_results if sc >= min_score]
    watched = [(sc, m) for sc, m in all_results if sc < min_score]

    # ── Alert cards ──
    if alerts:
        st.subheader(f"🚨 {len(alerts)} stock(s) above your threshold ({min_score})")
        for sc, m in alerts:
            with st.expander(
                f"{score_color(sc)}  **{m['ticker']}** — Score {sc}/100  |  "
                f"${m['current_price']}  |  Short: {m['short_pct_float']}%",
                expanded=True
            ):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Short % Float",  f"{m['short_pct_float']}%")
                c2.metric("Days to Cover",  f"{m['short_ratio']}")
                c3.metric("Volume vs Avg",  f"{m['volume_ratio']}x")
                c4.metric("5-day Change",   f"{m['price_change_5d']}%")

                if api_key:
                    with st.spinner("AI is analyzing…"):
                        try:
                            analysis = get_ai_analysis(m, sc, api_key)
                            st.info(analysis)
                        except Exception as e:
                            st.warning(f"AI error: {e}")
                else:
                    st.caption("💡 Add your Anthropic API key in the sidebar to get AI analysis.")
    else:
        st.success(f"✅ No stocks scored above {min_score} right now — market looks calm.")

    # ── Other stocks table ──
    if watched:
        st.divider()
        st.subheader("📊 All other scanned stocks")
        for sc, m in watched:
            st.write(
                f"{score_color(sc)} **{m['ticker']}** — "
                f"Score: **{sc}** | Short: {m['short_pct_float']}% | "
                f"Vol: {m['volume_ratio']}x | 5d: {m['price_change_5d']}% | "
                f"${m['current_price']}"
            )

    st.caption("⚠️ Not financial advice. Always do your own research before trading.")

streamlit
yfinance
anthropic
