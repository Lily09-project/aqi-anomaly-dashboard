# aqi-anomaly-dashboard: interface design

Reference: [mintlify design analysis](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/mintlify/DESIGN.md), curated by VoltAgent. This is an independent adaptation; no affiliation, brand assets or proprietary fonts.

Single light reading workspace. Mint active states, white surfaces and a fixed palette (see `web/src/styles/tokens.css`; new tokens may only alias existing values).

2026-11 relayout, "weather app × lab notebook": the home page opens on a "now → next 24 hours" board (one AQI-coloured hour strip per location, P50 fill with a P90 top stripe). Analysis pages read as numbered chapters: a one-sentence takeaway computed from the data, then the chart, then a "how to read" margin note. Navigation is a 248px notebook index rail at 1200px and wider, a sticky top bar from 641px to 1199px, and a bottom tab bar on phones.

Use local system fonts (each platform's built-in CJK face first) in two weights only, 400 and 700, 16px body and 14px secondary text. No entrance animation on page content. Keep semantic data colors distinct from decorative accents. Preserve data labels, warnings, keyboard focus, chart tables, cancellation and existing route contracts. No external font or asset requests. Mobile controls retain at least 44px height. All pages reflow at 200% text; wide data tables scroll inside named keyboard-accessible regions.

The source collection is MIT licensed. Token and component adaptations retain its notice in THIRD_PARTY_DESIGN_NOTICES.txt.
