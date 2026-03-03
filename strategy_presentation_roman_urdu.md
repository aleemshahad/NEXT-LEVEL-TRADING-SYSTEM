# 🧠 NEXT LEVEL TRADING SYSTEM - Strategy Working Flow (Roman Urdu)

Yeh presentation hamari trading strategy ke kaam karnay ka treeka (workflow) samjhati hai.

---

## 1. System Initialization (Aghaaz)
- Sab se pehle system **MT5 Terminal** se connect hota hai.
- `config.yaml` file se preset settings (Gold symbol, lot size, spacing) uthata hai.
- **Shared MT5Broker**: Humne ek shared broker interface banaya hai taake connection bar bar drop na ho aur trading fast chalay.

## 2. Direction Selection (Simt ka Intekhab)
User ke pas 3 bari options hoti hain:
- **BUY ONLY**: Jab market gir rahi ho to neechay se buy orders uthaye jatay hain.
- **SELL ONLY**: Jab market oper ja rahi ho to oper se sell orders lagaye jatay hain.
- **BOTH (Hedging)**: BUY aur SELL dono side ke grids ek sath chaltay hain. Is mein "Bias" (market trend) ka intezar nahi karna parta, system dono taraf mafa uthata hai.

## 3. Grid Placement (Jaal Bichana)
- **Precise Batching**: System current price ke oper ya neechay **20 orders** ka ek pura "Batch" laga deta hai.
- **Trigger Logic**: Jab current batch ke **15 orders trades mein badal jatay hain**, to system foran agla batch tayar kar deta hai taake munafo ka silsila na rutkay.
- **Expansion aur Rolling**: Agar market mazeed agay nikal jaye to naye orders add hotay hain, aur agar wapis aaye to orders market ke sath "Roll" kartay hain.

## 4. Ultra-Speed Trailing (Bijli jaisi Raftar)
- **0.1s Loop**: System har second mein 10 baar market check karta hai. Gold (XAUUSD) jaisi tezz market ke liye yeh bohat zaroori hai taake trailing foran react karey.
- **Individual Trail Close**: Har trade ka apna profit target hota hai. Jab ek trade munafo mein ja kar wapis murey, to wahi trade **Immediate** close ho jati hai.
- **Immediate Level Recycling**: Trade close hotay hi system **usi entry price** par foran naya order laga deta hai taake grid kabhi khali na ho.

## 5. Smart Trailing aur Clean Dashboard
- **Automatic Locking**: $1 profit par $0.5 lock, aur $25+ par 80% munafo mehfooz.
- **Clean Terminal**: System sirf zaruri updates (jaisa ke trade close hona) dikhata hai, faltu messages ko stop kar diya gaya hai taake aap ka terminal saaf rahay aur aap trading par focus kar sakain.

---

### 🚀 Summary:
Hamara system ab **Ultra-High Speed (0.1s)** aur **Enhanced Batching** par chal raha hai. Yeh range market se bhi mafa nikalta hai aur profit lock kar ke balance ko mehfooz rakhta hai.
