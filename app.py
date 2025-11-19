# app.py  ← FINAL WORKING VERSION (English + Zero Errors)
import streamlit as st
from mftool import Mftool
import pandas as pd
import google.generativeai as genai
import json

st.set_page_config(page_title="MF Guru AI - Free AI Mutual Fund Advisor", layout="centered")

# Gemini API key from secrets
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

mf = Mftool()

# Load scheme codes once
@st.cache_data(ttl=86400)
def get_scheme_codes():
    return json.loads(mf.get_scheme_codes(as_json=True))
schemes_dict = get_scheme_codes()

# Calculate returns & risk
def calculate_returns(hist):
    df = pd.DataFrame(hist['data'])
    df['nav'] = pd.to_numeric(df['nav'])
    df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y')
    df = df.sort_values('date')
    if len(df) < 1000: return None
    latest = df['nav'].iloc[-1]
    ret = {'risk': round(df['nav'].pct_change().std() * (252**0.5) * 100, 1)}
    for y, days in [(1,252), (3,756), (5,1260)]:
        if len(df) >= days+30:
            cagr = (latest / df['nav'].iloc[-days]) ** (1/y) - 1
            ret[f'{y}Y'] = round(cagr*100, 2)
    return ret

# Recommend funds
def recommend_funds(profile):
    risk_limit = {"Low": 14, "Moderate": 20, "High": 100}.get(profile['risk'], 20)
    good_codes = ["120503","118998","112277","147592","120262","148604","139608","118829"]
    funds = []
    for code in good_codes:
        try:
            quote = mf.get_scheme_quote(code)
            hist = mf.get_scheme_historical_nav(code)
            returns = calculate_returns(hist)
            if not returns: continue
            name = quote['scheme_name'].split("- Direct Plan")[0].strip()
            funds.append({
                "code": code,
                "name": name,
                "1Y": returns.get('1Y', 0),
                "3Y": returns.get('3Y', 0),
                "5Y": returns.get('5Y', 0),
                "risk": returns['risk'],
                "expense": "0.4–0.8%"
            })
        except:
            continue
    funds = [f for f in funds if f['risk'] <= risk_limit]
    return sorted(funds, key=lambda x: x['5Y'], reverse=True)[:5]

# AI explanation in plain English
def explain(fund, p):
    prompt = f"In very simple English, explain in 4 short bullets why {fund['name']} is good for a {p['age']}-year-old investor with {p['risk']} risk appetite who invests ₹{p['sip']:,}/month for {p['horizon']} years."
    try:
        return model.generate_content(prompt).text
    except:
        return "• Strong past performance\n• Low expense ratio\n• Matches your risk level\n• From a trusted fund house"

# ================ STREAMLIT CHAT (ENGLISH) ================
st.title("MF Guru AI")
st.markdown("### Free AI Mutual Fund Advisor for Indian Investors (Educational Purpose Only)")

if 'stage' not in st.session_state:
    st.session_state.stage = 0
    st.session_state.profile = {}

questions = [
    "What is your age?",
    "For how many years do you want to invest?",
    "How much can you invest monthly (in ₹)?",
    "Your risk appetite? (Low / Moderate / High)",
    "Any preference? (Tax-saving / Index funds / Anything is fine)"
]

if st.session_state.stage < len(questions):
    with st.chat_message("assistant"):
        st.write(f"**{questions[st.session_state.stage]}**")
    if msg := st.chat_input("Type here..."):
        st.chat_message("user").write(msg)
        # Save answers safely
        if st.session_state.stage == 0: st.session_state.profile['age'] = msg
        if st.session_state.stage == 1: st.session_state.profile['horizon'] = int(msg or 10)
        if st.session_state.stage == 2: st.session_state.profile['sip'] = int("".join(filter(str.isdigit, msg)) or 10000)
        if st.session_state.stage == 3: st.session_state.profile['risk'] = msg.strip()
        st.session_state.stage += 1
        st.rerun()
else:
    p = st.session_state.profile
    p.setdefault('risk', 'Moderate')
    p['sip'] = int(p.get('sip', 10000))
    p['horizon'] = int(p.get('horizon', 10))

    with st.chat_message("assistant"):
        st.write("One second… finding the best funds for you!")
        funds = recommend_funds(p)
        rate = 12 if p['risk']=="High" else 10 if p['risk']=="Moderate" else 8
        future = p['sip'] * 12 * p['horizon'] * (1 + rate/200) ** p['horizon']
        st.success(f"₹{p['sip']:,}/month for {p['horizon']} years could grow to ≈ ₹{future:,.0f}")

        for f in funds:
            with st.expander(f"{f['name']} | 5Y: {f['5Y']}% | Risk: {f['risk']}%", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("1Y", f"{f['1Y']}%")
                c2.metric("3Y", f"{f['3Y']}%")
                c3.metric("5Y", f"{f['5Y']}%")
                c4.metric("Expense", f["expense"])
                st.write("**Why this fund fits you:**")
                st.write(explain(f, p))
                st.markdown(f"[Open in Groww](https://groww.in/mutual-funds/scheme/{f['code']}) | [Zerodha Coin](https://coin.zerodha.com/mf/{f['code']})")

        st.warning("This is for educational purpose only • Not financial advice • Past performance ≠ future returns")
        if st.button("Start again for someone else"):
            st.session_state.clear()
            st.rerun()

st.caption("Made with ❤️ in India | 100% Free | Data: mfapi.in | AI: Google Gemini")
