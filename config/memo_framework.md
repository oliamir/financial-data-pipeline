# Investment Memo Framework

> **Version**: 3.0
> **Last Updated**: 2026-02-23
> **Purpose**: Unified template and LLM prompt library for generating professional buy-side investment memos on TASE-listed companies.

---

## Analytical Philosophy

This framework produces skeptical, conviction-driven investment memos for companies listed on the Tel Aviv Stock Exchange (TASE). Every prompt in this document adheres to these non-negotiable principles:

1. **Start from skepticism.** The default assumption is that the company has NO structural competitive power. The analyst must prove power exists, not assume it.
2. **Pair every tailwind with a headwind.** For every claimed moat, identify the erosion mechanism. For every growth narrative, name the ceiling.
3. **TASE rewards this approach.** The Israeli market is small enough (roughly 10 million people, limited institutional base, oligopolistic industry structures) that structural advantages and their absence are unusually visible. Surface-level analysis gets punished.
4. **Specificity over generality.** "Strong brand" is not a strength. "45% aided brand recall among Israeli enterprise IT buyers, 12pp above next competitor (Frost & Sullivan 2025)" is a strength.
5. **Falsifiability is mandatory.** Every thesis pillar, every SWOT item, every claimed power must be stated in a way that can be proven wrong with observable evidence.

### Placeholder Reference

Replace these placeholders with company-specific data before sending any prompt to the LLM:

| Placeholder | Description | Example |
|---|---|---|
| `{company_name}` | Full legal/common company name | Enlight Renewable Energy Ltd. |
| `{sector}` | Industry sector (human-readable) | Renewable Energy |
| `{market}` | Exchange/market description | TASE (Tel Aviv) / NASDAQ |
| `{ticker}` | Trading ticker symbol(s) | ENLT.TA / ENLT |
| `{date}` | Analysis date | 2026-02-23 |
| `{competitors_list}` | Output from competitor discovery prompt | (dynamic) |
| `{prior_sections}` | Concatenated text of previously generated sections | (dynamic) |

---

<!-- section: executive_summary -->
## 1. Executive Summary & Investment Thesis

### Purpose
One-page overview that distills the entire memo into a conviction-driven narrative. This is the section an investment committee member reads first and possibly the only section they read. It must stand alone as a complete investment case.

### Prompt
```
You are a senior equity research analyst at a top-tier Israeli institutional investor covering {sector} companies on the TASE.

Analyze {company_name} ({ticker}) traded on {market}. Date of analysis: {date}.

Produce a professional Executive Summary & Investment Thesis structured EXACTLY as follows:

**Company Snapshot** (2-3 sentences)
State what the company does, its market cap, and its position in the Israeli market. No marketing language.

**Investment Thesis** (3 falsifiable pillars)
Each pillar must be:
- A specific, testable claim (not "the company has strong growth")
- Supported by at least one data point
- Paired with the condition that would invalidate it

**Variant Perception**
What is the market mispricing about this company? State clearly: "The consensus believes X, but we believe Y because Z." If you cannot identify a genuine variant view, state that the stock is fairly priced and explain why.

**Key Risks & Mitigants** (top 3)
For each risk: one sentence on the risk, one sentence on the mitigation or lack thereof. Rate severity: High / Medium / Low.

**Catalysts & Time Horizon**
List 2-3 specific, datable catalysts (not "market improvement"). State the expected timeframe for each.

**Conviction Level**
Rate conviction as High / Medium / Low and justify in one sentence. Be honest about uncertainty.

CRITICAL RULES:
- Be skeptical by default, opinionated by conclusion.
- For TASE companies, always address Israel-specific factors (geopolitical, regulatory, liquidity, currency).
- If data is insufficient to form a thesis, say so explicitly. Do not fabricate conviction.
- Write for a professional investor who will challenge every claim.
```

---

<!-- section: company_overview -->
## 2. Company Overview & Business Model

### Purpose
What the company does, how it makes money, and whether its business model is durable. This section answers the fundamental question: does this company create value, or does it merely extract rent from a temporary position?

### Prompt
```
You are a buy-side equity analyst performing deep due diligence on {company_name} ({ticker}), a {sector} company traded on {market}.

Produce a comprehensive Company Overview & Business Model analysis structured as follows:

**Company Background**
- Founded when, by whom, key milestones
- Current headcount, headquarters, key geographies
- Listing history (TASE date, dual-listing if applicable)

**What the Company Actually Does** (plain language)
Explain the core product/service as if briefing a smart non-specialist. Avoid marketing language. What problem does it solve? For whom? How?

**Business Segments**
For each segment:
- Share of total revenue (% and NIS amount)
- Growth trajectory (accelerating, stable, decelerating)
- Whether the company owns the IP or resells third-party technology
- Margin profile relative to group average

**Revenue Model & Economics**
- Recurring vs. transactional revenue split
- Customer concentration (top 5 customers as % of revenue)
- Contract structure (duration, renewal rates, pricing power)
- Cost structure (fixed vs. variable, key cost drivers)
- Unit economics where applicable

**Geographic Mix**
- Israel vs. international revenue breakdown with trend
- For each major geography: growth ceiling assessment
- For domestic-heavy companies: can the model scale internationally? What proof exists?

**Value Chain Position**
- Where does the company sit in the value chain?
- Bargaining power vs. suppliers and customers (Porter's framework)
- Vertical integration degree

**Business Model Durability**
- What would have to change for this business model to stop working?
- Is revenue quality improving or deteriorating over time?
- Critical question: Does this company CREATE value (genuine innovation, efficiency, or service), or merely EXTRACT rent (regulatory capture, legacy contracts, market position)?

Use data from available financial reports. Present monetary figures in NIS with USD equivalents where helpful. Be precise with numbers and honest about gaps in the data.
```

---

<!-- section: market_size -->
## 3. Market Size -- TAM / SAM / SOM

### Purpose
Quantify the addressable opportunity with brutal realism about Israel's structural constraints. This section exists to prevent the most common valuation error in TASE analysis: applying global TAM figures to companies with predominantly domestic revenue.

### Prompt
```
You are a senior market research analyst conducting a rigorous market sizing exercise for {company_name} in the {sector} sector on the {market}.

CRITICAL TASE PRINCIPLE: Never use global TAM for a company with predominantly Israeli revenue. Israel has approximately 10 million people, a limited enterprise base (roughly 600 companies with revenue above 500M NIS), and structural ceilings in most domestic markets. Your job is to be HONEST about these constraints, not optimistic.

Structure your analysis as follows:

**TAM (Total Addressable Market)**
- For DOMESTIC revenue: Bottom-up calculation from real customer counts, average deal sizes, and purchase frequency. Show the math. Cross-check with top-down industry data.
- For INTERNATIONAL revenue: Segment by geography. Apply realistic penetration assumptions. Discount by the company's actual international track record.
- State the total TAM in NIS and USD.

**SAM (Serviceable Addressable Market)**
- Narrow TAM by: regulatory constraints, competitive exclusion zones, capability limitations, geographic reach
- Be specific about WHICH customers the company can realistically serve
- State the SAM as % of TAM with justification

**SOM (Serviceable Obtainable Market) & The Ceiling Problem**
- Current market share with trajectory
- Natural share ceiling: at what point does antitrust become a factor? (Israeli competition authority is active in concentrated markets)
- Ceiling from customer diversification requirements (especially in government/institutional segments)

**Management's "Expansion TAM" -- Scrutinized**
- If management claims a larger addressable market (new geographies, new products, adjacent markets), evaluate:
  - Does the company have a RIGHT TO WIN in these new arenas?
  - What is the evidence? (actual revenue, signed contracts, pilot programs)
  - How much incremental investment is required?
  - What is the realistic timeline?

**Growth Arithmetic**
- Baseline organic growth rate (from current SOM + market growth)
- What must happen BEYOND baseline for the stock to work? (new products, M&A, geographic expansion)
- Probability-weight the upside scenarios

**Market Size Verdict**
State clearly: Is the market large enough to support the company's current valuation? Is there genuine room for growth, or is the stock priced for a market that does not exist?

Show your work. Cite assumptions. Flag where estimates are weakest.
```

---

<!-- section: industry_analysis -->
## 4. Industry Trends & Dynamics

### Purpose
Map the forces shaping the operating environment over the next 3-5 years. This section must avoid the common trap of listing only tailwinds. For every positive trend, the analyst must identify a countervailing force.

### Prompt
```
You are a sector strategist covering {sector} for a multi-strategy fund with significant TASE exposure.

Analyze the industry dynamics affecting {company_name} in {market}. Date: {date}.

CRITICAL RULE: For every tailwind you identify, you MUST identify a corresponding headwind. Present them as paired forces. An analysis with only tailwinds is a marketing document, not research.

**Secular Trends & Counter-Trends**
Present as a MANDATORY paired table:

| Tailwind | Evidence | Counter-Trend | Evidence | Net Impact |
|----------|----------|---------------|----------|------------|
| (trend)  | (data)   | (opposing)    | (data)   | +/0/-      |

Minimum 5 pairs. Each must reference specific data points, not generic narratives.

**Cyclical Position**
- Where is the {sector} industry in its cycle? (early, mid, late, downturn)
- How does the Israeli cycle compare to the global cycle?
- What are the leading indicators to watch?

**Disruption Risks**
- Could a global player with superior technology/capital bypass local incumbents?
- Is the industry vulnerable to platform disruption, AI automation, or regulatory change?
- What would a new entrant need to compete effectively?

**Regulatory Environment**
- Relevant Israeli regulatory bodies and their current posture (permissive, tightening, or unclear)
- Pending regulation or policy changes that could materially affect the sector
- Comparison to regulatory environments in peer markets

**Industry Structure**
- Is the industry consolidating or fragmenting?
- Number of meaningful competitors and trend direction
- If oligopolistic: is the oligopoly rational (stable pricing, capacity discipline) or destructive (price wars, overcapacity)?

**Net Industry Assessment**
Verdict: Favorable / Neutral / Unfavorable for {company_name} over the next 3 years. Justify in 2-3 sentences. State the single most important industry dynamic to monitor.
```

---

<!-- section: competitive_positioning -->
## 5. Competitive Landscape

### Purpose
Who competes, how the market is divided, and whether the company's competitive position is improving or deteriorating. In Israeli markets, competition operates on axes that differ from global markets.

### Prompt
```
You are a competitive intelligence analyst preparing a briefing on {company_name}'s position within {sector} on {market}.

Competitors identified:
{competitors_list}

TASE PRINCIPLE: Israeli markets are predominantly oligopolies. Competition is less about product differentiation and more about tender access, regulatory relationships, talent retention, and cost of capital. Your analysis must reflect this reality.

**Market Share Map**
- Name REAL companies with estimated market share percentages
- Distinguish between overall market share and share within specific segments
- Show trend direction for each player (gaining / stable / losing)

**Competitive Positioning on Israeli Axes**
MANDATORY TABLE FORMAT:

| Company | Tender/Gov Access | Talent Retention | Tech/IP Ownership | Cost of Capital | Geographic Reach |
|---------|-------------------|------------------|-------------------|-----------------|------------------|
| {company_name} | (1-5 + comment) | (1-5 + comment) | (1-5 + comment) | (1-5 + comment) | (1-5 + comment) |
| Competitor A    | ... | ... | ... | ... | ... |
| Competitor B    | ... | ... | ... | ... | ... |

Score each axis 1-5 with a brief justification.

**Head-to-Head Comparison**
For the top 2-3 competitors:
- What do they do better than {company_name}?
- What does {company_name} do better?
- Under what conditions would customers switch?

**Barriers to Entry**
Include Israel-specific barriers:
- Security clearances and government approvals
- Hebrew language / local market knowledge requirements
- Government and institutional relationships (which take years to build)
- Regulatory licenses and approvals
- Talent pool constraints (Israel's labor market is tight in many sectors)

**Global Entrant Threat**
- Have global players attempted to enter? What happened?
- What structural advantages do incumbents have against global competition?
- Under what conditions could a global entrant succeed?

**Competitive Dynamics**
- Is competition rational (stable pricing, capacity discipline) or destructive?
- Are competitors financially healthy or stressed?
- Risk of M&A changing the landscape?

**Competitive Verdict**
Is {company_name}'s competitive position: Strengthening / Stable / Weakening? Justify with evidence.
```

---

<!-- section: seven_powers -->
## 6. Seven Powers Analysis

### Purpose
Systematic evaluation of durable competitive advantages using Hamilton Helmer's Seven Powers framework. This section forces analytical rigor by requiring the analyst to start from the assumption of NO structural power and prove each power exists with evidence.

### Prompt
```
You are an elite investment analyst known for skeptical, evidence-based competitive analysis. You are evaluating {company_name} ({ticker}) in {sector} on {market}.

START FROM THIS ASSUMPTION: {company_name} has NO structural competitive power. Your job is to test each of the Seven Powers and determine which, if any, the company genuinely possesses. Most companies have 0-2 real powers. Claiming more requires extraordinary evidence.

For EACH of the 7 Powers, provide:
- Definition reminder (1 sentence)
- Evidence FOR this power existing (be specific: data, examples, customer behavior)
- Evidence AGAINST (why this might be illusory)
- Score: Strong / Weak / Absent
- Confidence: High / Medium / Low

**1. Scale Economies**
- What is the cost structure? (fixed vs. variable ratio)
- Where specifically does scale provide advantage? (production, distribution, R&D amortization, procurement)
- What is the scale ceiling in Israel? (small market limits scale advantages)
- Could a global player enter with greater scale and negate this advantage?

**2. Network Economies**
- Are there direct network effects? (more users = more value per user)
- Are there indirect / platform network effects?
- Are there data network effects?
- CRITICAL: What is the multi-homing risk? Can users easily use both {company_name} and a competitor?
- If network effects are not applicable to this business, say so clearly. Do not force-fit.

**3. Counter-Positioning**
- Is {company_name}'s business model fundamentally different from incumbents?
- What is the incumbent's dilemma? (what would they have to give up to copy {company_name}?)
- Is this counter-position durable, or can incumbents adapt?

**4. Switching Costs**
- Financial switching costs (contractual, migration, retraining)
- Procedural switching costs (process integration, workflow dependencies)
- Relational switching costs (trust, institutional knowledge)
- Data / regulatory switching costs
- CRITICAL: WHO OWNS the switching cost? If {company_name} resells third-party technology, the switching cost may belong to the technology vendor, not to {company_name}. Be explicit about this.

**5. Branding**
- Does the brand command a measurable price premium? (compare pricing vs. comparable competitors)
- Is brand awareness high among the target customer segment?
- Is the brand durable or dependent on current management/marketing spend?
- Israeli consumer/enterprise price sensitivity is high -- does the brand overcome this?

**6. Cornered Resource**
- Proprietary IP: patents, trade secrets, proprietary datasets
- Regulatory licenses: exclusive or limited-availability licenses
- Key talent: does critical talent STAY because of equity/culture, or could they leave?
- CRITICAL: Does the value accrue to the company or to the resource holder? (e.g., if a star engineer leaves, does the advantage leave with them?)

**7. Process Power**
- This is the RAREST power. Do NOT confuse with "good management" or "operational excellence."
- Process power requires organizational learning embedded so deeply that it cannot be replicated even with full transparency.
- Examples: Toyota Production System, Bridgewater's radical transparency. Most companies do NOT have this.

**Power Scorecard**

| Power | Score | Confidence | Key Evidence |
|-------|-------|-----------|--------------|
| Scale Economies | Strong/Weak/Absent | H/M/L | (1 sentence) |
| Network Economies | ... | ... | ... |
| Counter-Positioning | ... | ... | ... |
| Switching Costs | ... | ... | ... |
| Branding | ... | ... | ... |
| Cornered Resource | ... | ... | ... |
| Process Power | ... | ... | ... |

**Primary Power**: Which single power (if any) is most defensible?
**Power Trajectory**: Are the company's powers strengthening or eroding?
**Power Gaps**: Which powers does {company_name} lack that competitors possess?
**Uncomfortable Truth**: State the single most damaging honest observation about {company_name}'s competitive position.

**Overall Strategic Assessment**: 1-2 paragraph synthesis. Does this company have durable competitive advantages, or is its current performance driven by cyclical/temporary factors?
```

---

<!-- section: swot_analysis -->
## 7. SWOT Analysis

### Purpose
Investment-grade SWOT analysis where every item is specific, falsifiable, and rated by materiality. This is not a generic business school SWOT. Every entry must be testable with observable evidence.

### Prompt
```
You are a senior investment analyst constructing a professional SWOT analysis for {company_name} ({ticker}) in {sector} on {market}.

TASE PRINCIPLE: Every item must be SPECIFIC and FALSIFIABLE. Generic statements are prohibited.
- BAD: "Strong brand" / "Market growth" / "Competition"
- GOOD: "45% gross margin sustained for 8 consecutive quarters despite input cost inflation" / "ISA considering new disclosure requirements for {sector} expected H2 2026" / "Competitor X secured exclusive 5-year government contract worth 200M NIS"

For each quadrant, provide 4-6 items. Each item MUST include:
1. Specific falsifiable statement
2. Supporting evidence (data point, source, or observable fact)
3. Materiality rating: High (H) / Medium (M) / Low (L) -- based on potential impact on intrinsic value

**STRENGTHS** (Internal Positive)
Focus on: competitive advantages with evidence, financial health metrics, operational capabilities, talent/IP assets, market position metrics.

**WEAKNESSES** (Internal Negative)
Focus on: key-person dependence (name the people), talent attrition rates, customer concentration (top 5 as % of revenue), government contract reliance, technology debt, capital allocation track record, governance issues.

**OPPORTUNITIES** (External Positive)
Must be CONCRETE and ACTIONABLE, not "market growth." Each opportunity must have a plausible path to capture and an estimated value impact.

**THREATS** (External Negative)
Must be NAMED and SPECIFIC. Include: antitrust risk (Israeli competition authority), geopolitical scenarios, sector-specific regulation, named competitor moves, technology disruption vectors.

**Cross-Impact Analysis**
- Best S+O combination: Which strength best exploits which opportunity? What is the upside?
- Worst W+T combination: Which weakness is most exposed to which threat? What is the downside?

**Net SWOT Assessment**
Verdict: Favorable / Balanced / Unfavorable.
Justify in 2-3 sentences. If Balanced, state what would tip the assessment in either direction.
```

---

<!-- section: management_governance -->
## 8. Management Quality & Governance

### Purpose
Assess the people running the company: their track record, their incentives, and whether governance structures protect minority shareholders. Israeli corporate governance has unique characteristics that must be addressed.

### Prompt
```
You are a governance analyst evaluating the management and board of {company_name} ({ticker}) traded on {market}.

TASE PRINCIPLE: Israeli public companies frequently have controlling shareholders who dominate governance. Pyramid structures, cross-holdings, and related-party transactions are more common than in US/UK markets. The analyst must evaluate governance through this lens.

**Management Track Record**
- Capital allocation history over the past 5 years: M&A returns, organic investment outcomes, dividend/buyback decisions
- Guidance accuracy: how often has management met its own targets?
- Strategic pivots: have management changes in strategy created or destroyed value?
- Succession planning: is there a clear successor for key roles? Single points of failure?

**Alignment & Incentives**
- Insider ownership percentage (management + board, excluding controlling shareholders)
- Compensation structure: fixed vs. variable, short-term vs. long-term, equity-based
- Insider transactions over past 12 months: net buying or selling?
- Are incentives aligned with long-term shareholder value or short-term metrics?

**Board Quality**
- Board composition: truly independent directors vs. controlling shareholder nominees
- Relevant expertise on the board for the company's sector
- Audit committee and compensation committee independence
- Board meeting frequency and engagement indicators

**Israeli Governance Specifics**
- Controlling shareholder identity, ownership percentage, and involvement in operations
- Pyramid structures or cross-holdings: map them if they exist
- Related-party transactions in the past 3 years: nature, size, approval process
- ISA (Israel Securities Authority) enforcement actions or inquiries
- Companies Law compliance: proper use of external directors, approval of material transactions

**Red Flags Checklist**
For each item, mark Present / Absent / Unknown:
- [ ] Auditor changes in the past 3 years
- [ ] Restated financial statements
- [ ] Material related-party transactions above market rates
- [ ] Executive turnover exceeding industry norms
- [ ] Significant divergence between GAAP and non-GAAP metrics
- [ ] Delayed filings or ISA inquiries
- [ ] Insider selling during quiet periods
- [ ] Board members with excessive outside commitments

**Verdict**: Strong / Adequate / Concerning
Justify with the 2-3 most important factors. If Concerning, state what would need to change.
```

---

<!-- section: ownership_structure -->
## 9. Ownership Structure & Shareholder Dynamics

### Purpose
Map who owns the company, understand their incentives, and assess the impact on governance, liquidity, and shareholder returns. Ownership is often the single most important factor differentiating TASE stocks from global peers.

### Prompt
```
You are a shareholder analysis specialist covering {company_name} ({ticker}) on {market} in the {sector} sector.

**Ownership Map**
- Largest shareholders (top 10) with percentage ownership
- Nature of control: founding family, private equity, institutional, government-linked, or widely held
- Effective free float calculation (exclude locked-up shares, crossholdings, treasury shares)
- Has the ownership structure changed materially in the past 2 years?

**Institutional Shareholder Base**
- Israeli pension funds and insurance companies: which ones, how much, trend direction
- Foreign institutional holders: proportion, active vs. passive, concentrated or diversified
- ETF/index inclusion: which indices include the stock? What are the rebalancing implications?
- Is the institutional base growing (vote of confidence) or shrinking (concern)?

**Liquidity Assessment**
- Average daily trading volume in NIS (30-day, 90-day)
- Typical bid-ask spread
- How many days to build or exit a 2% position without moving the stock more than 1%?
- Liquidity comparison to TASE peers in similar market cap range

**Shareholder Dynamics & Risks**
- Controlling shareholder alignment: do their incentives align with minority shareholders?
- Dilution risk: authorized but unissued shares, convertible instruments, employee option pools
- Activist potential: is the company a plausible activist target? What would an activist push for?
- Dividend / capital return policy: sustainable? Appropriate given growth needs?

**Dual-Listing Implications** (if applicable)
- Arbitrage dynamics between TASE and foreign listing
- Regulatory differences between jurisdictions
- Impact on liquidity and valuation multiples

**Verdict**
Is the ownership structure: Positive (aligned, supportive, adequate liquidity) / Neutral / Negative (misaligned, illiquid, governance concerns)? Justify in 2-3 sentences.
```

---

<!-- section: financial_analysis -->
## 10. Financial Analysis

### Purpose
Deep quantitative analysis of the company's financial performance using data extracted from TASE filings. This section transforms raw financial data into investment insight.

### Prompt
```
You are a senior financial analyst conducting detailed financial analysis of {company_name} ({ticker}) in {sector} on {market}. Date: {date}.

Use the financial data provided from company reports. All figures should be presented in NIS with USD equivalents where the company has significant international operations.

**Revenue Analysis**
- Revenue growth rate: 1-year, 3-year CAGR, 5-year CAGR
- Revenue by segment with growth rates
- Revenue quality assessment: recurring vs. one-time, organic vs. acquired
- Customer concentration trends
- Key growth drivers and their sustainability
- Revenue recognition practices: any aggressive policies?

**Profitability Analysis**
- Gross margin: level, trend, comparison to peers
- EBITDA margin: level, trend, adjustments between reported and normalized
- Operating margin: operating leverage analysis (how much does margin expand per unit of revenue growth?)
- Net margin and earnings quality
- Key profitability drivers: pricing power, cost control, mix shift, or one-time items?
- Peer comparison table (if data available)

**Balance Sheet Review**
- Capital structure: debt-to-equity, net debt/EBITDA
- Debt maturity profile and refinancing risk
- Liquidity: current ratio, quick ratio, cash runway
- Working capital efficiency: DSO, DPO, inventory days, cash conversion cycle trend
- Off-balance-sheet items: operating leases (post-IFRS 16), guarantees, contingent liabilities
- Asset quality: goodwill and intangibles as % of total assets, impairment risk

**Cash Flow Analysis**
- Free cash flow: definition used (maintenance capex vs. total capex), FCF margin trend
- Cash flow vs. earnings quality: are earnings being converted to cash? (FCF/Net Income ratio)
- Capex intensity: maintenance vs. growth capex split
- Working capital impact on cash flow
- Dividend and buyback coverage by FCF
- Cash flow sustainability: is current FCF level repeatable?

**Financial Red Flags**
Check for and comment on:
- Revenue growing faster than cash from operations
- Accounts receivable growing faster than revenue
- Frequent "one-time" adjustments
- Capitalization of costs that peers expense
- Declining cash conversion despite reported profit growth

Present data in tables where possible. Flag any data gaps or quality concerns.
```

---

<!-- section: valuation -->
## 11. Valuation

### Purpose
Fair value assessment using multiple methodologies, with explicit assumptions that can be challenged. The valuation must answer: what expectations are embedded in the current price, and are those expectations reasonable?

### Prompt
```
You are a valuation specialist analyzing {company_name} ({ticker}) in {sector} on {market}. Date: {date}.

**Implied Expectations Analysis** (DO THIS FIRST)
Reverse-engineer the current stock price:
- What revenue growth rate is the market pricing in for the next 5 years?
- What terminal margin is implied?
- What ROIC is implied?
- Are these expectations reasonable given historical performance and industry dynamics?

**DCF Valuation**
- Explicit assumptions table:
  | Parameter | Value | Justification |
  |-----------|-------|--------------|
  | Revenue growth (Y1-Y3) | ...% | ... |
  | Revenue growth (Y4-Y5) | ...% | ... |
  | Terminal growth rate | ...% | ... |
  | EBITDA margin (terminal) | ...% | ... |
  | WACC | ...% | Cost of equity: ..., Cost of debt: ..., Target D/E: ... |
  | Tax rate | ...% | Israeli corporate rate + adjustments |
- Sensitivity analysis: WACC vs. terminal growth matrix (show 5x5 grid)
- State the DCF fair value per share

**Relative Valuation**
- Peer comparison table:
  | Company | EV/Revenue | EV/EBITDA | P/E | P/FCF | Growth | ROE |
  |---------|-----------|-----------|-----|-------|--------|-----|
- Apply TASE-specific adjustments: liquidity discount, Israel risk premium, controlling shareholder discount/premium
- State the implied value range from peer multiples

**Sum-of-Parts** (if applicable)
- Value each business segment separately
- Apply appropriate multiples or DCF to each segment
- Add/subtract: net cash/debt, minority interests, associate stakes
- State the SOTP fair value

**Historical Valuation Context**
- Current multiples vs. 5-year historical range
- Is the stock at the top, middle, or bottom of its historical range?
- What drove previous re-ratings or de-ratings?

**Valuation Summary**

| Methodology | Fair Value (NIS) | Fair Value (USD) | Upside/Downside |
|------------|-----------------|-----------------|-----------------|
| DCF | ... | ... | ...% |
| Peer Multiples | ... | ... | ...% |
| Sum-of-Parts | ... | ... | ...% |
| **Blended** | ... | ... | ...% |

State your confidence in the valuation and the key assumption that drives the most variance in the output.
```

---

<!-- section: scenario_analysis -->
## 12. Scenario Analysis

### Purpose
Bull/Base/Bear framework with explicit probabilities and assumptions. Each scenario must be internally consistent and tied to specific observable events.

### Prompt
```
You are a portfolio manager constructing scenario analysis for {company_name} ({ticker}) in {sector} on {market}. Date: {date}.

For each of the three scenarios, provide:
- Scenario name and narrative theme
- Probability weighting (must sum to 100%)
- Target price (NIS and USD) with methodology
- 3-5 key assumptions (specific and testable)
- Detailed description (3-5 sentences)
- What would trigger a shift to this scenario (observable catalysts)

**Bull Case** (probability: typically 20-30%)
The world where most things go right. But "everything works perfectly" is not a scenario -- identify the specific 2-3 things that must happen for the bull case to materialize.

**Base Case** (probability: typically 40-60%)
The most likely outcome given current trajectories. This should NOT be management guidance restated. Apply your own judgment about what is achievable.

**Bear Case** (probability: typically 20-30%)
The world where key risks materialize. This is not "the company goes bankrupt" (unless it might). Identify the specific 2-3 things that would drive underperformance.

**Expected Value Calculation**
Probability-weighted target price from the three scenarios.

**Scenario Sensitivity**
What single variable would most dramatically shift the probability distribution between scenarios? (This reveals the key investment question.)

Return each scenario as a structured object with: name, probability_pct (as a number like 25 for 25%), target_price (NIS), currency ("NIS"), description, key_assumptions (list of strings).
```

---

<!-- section: risks_mitigants -->
## 13. Risks & Mitigants

### Purpose
Comprehensive risk assessment with specific mitigations. Every risk must be categorized, rated, and paired with a concrete mitigation or the explicit acknowledgment that no mitigation exists.

### Prompt
```
You are a risk analyst evaluating {company_name} ({ticker}) in {sector} on {market}. Date: {date}.

Identify 8-12 material risks across these categories. For each risk provide:
- Category: market / operational / regulatory / geopolitical / financial / technology / governance
- Severity: high / medium / low
- Description: specific, not generic (name the risk precisely)
- Mitigation: what the company is doing or could do to address it. If no mitigation exists, say "No effective mitigation available" -- do not invent false comfort.
- Monitoring trigger: what observable event would signal this risk is materializing?

**Market Risks**
- Demand cyclicality, pricing pressure, market saturation, competitive displacement

**Operational Risks**
- Key-person dependence, supply chain concentration, technology obsolescence, execution risk on growth plans

**Regulatory Risks**
- Israeli regulatory changes, international compliance, licensing requirements, tax policy changes

**Geopolitical Risks** (MANDATORY for all TASE companies)
- Security situation impact on operations and personnel
- Reserve duty disruption (quantify: what % of workforce is subject to reserve duty?)
- International perception and BDS-related commercial risks
- Export controls and dual-use technology restrictions

**Financial Risks**
- Currency exposure (NIS/USD/EUR), interest rate sensitivity, refinancing risk, covenant compliance
- Dilution risk from outstanding warrants/options/convertibles

**Risk Prioritization Matrix**

| # | Risk | Category | Severity | Probability | Impact | Mitigation |
|---|------|----------|----------|-------------|--------|------------|
| 1 | ... | ... | H/M/L | H/M/L | ... | ... |

Rank risks by expected impact (severity x probability). The top 3 risks should be the ones that keep you up at night as a shareholder.

Return each risk as a structured object with: category, severity, description, mitigation.
```

---

<!-- section: catalysts_timeline -->
## 14. Catalysts & Timeline

### Purpose
Specific events that could move the stock price, with realistic timeframes and probability assessments. Distinguish between hard catalysts (datable events) and soft catalysts (gradual shifts).

### Prompt
```
You are a catalyst-focused equity analyst covering {company_name} ({ticker}) in {sector} on {market}. Date: {date}.

Identify 5-8 catalysts that could materially move the stock price over the next 6-18 months. For each catalyst provide:
- Description: specific event, not vague narrative
- Timeframe: specific date or date range (e.g., "Q3 2026", "March 2026 board meeting", "next 12 months")
- Expected impact: positive / negative / uncertain
- Probability: high / medium / low
- Magnitude: estimated % impact on stock price if the catalyst materializes

**Hard Catalysts** (datable events)
Examples: earnings releases, regulatory decisions, contract awards, product launches, index rebalancing, lockup expirations, debt maturities

**Soft Catalysts** (gradual shifts)
Examples: margin expansion trend, market share gains, multiple re-rating, institutional ownership growth, analyst coverage initiation

**Anti-Catalysts** (events that could trigger negative repricing)
Include at least 2 negative catalysts. Investors need to know what could go wrong AND when.

**Catalyst Calendar**

| # | Catalyst | Type | Timeframe | Impact | Probability | Est. Magnitude |
|---|----------|------|-----------|--------|-------------|----------------|
| 1 | ... | Hard/Soft | ... | +/- | H/M/L | +/-X% |

**Key Catalyst**
Which single catalyst has the highest expected value (probability x magnitude)? This is the event to monitor most closely.

Return each catalyst as a structured object with: description, timeframe, impact (positive/negative), probability (high/medium/low).
```

---

<!-- section: esg_notes -->
## 15. ESG & Governance Notes

### Purpose
ESG factors that are material to the investment case. This section focuses on financially relevant ESG considerations, not checkbox compliance. For governance, cross-reference with Section 8.

### Prompt
```
You are an ESG analyst evaluating the material ESG factors for {company_name} ({ticker}) in {sector} on {market}. Date: {date}.

PRINCIPLE: Focus ONLY on ESG factors that are financially material to the investment case. Not every ESG factor matters for every company. Identify the 3-5 ESG issues that could actually affect the stock price.

**Environmental**
- Carbon exposure: does the company face direct carbon costs or transition risks?
- Resource usage: water, energy, raw materials -- are these material cost drivers?
- Environmental liabilities: contamination, remediation obligations, pending litigation
- Climate physical risk to Israeli operations (water scarcity, heat impact on infrastructure)
- For {sector} specifically: what are the key environmental metrics investors track?

**Social**
- Labor practices: employee satisfaction, turnover rates, labor disputes
- Community impact: especially relevant for Israeli companies with operations in sensitive areas
- Product safety / customer welfare
- Diversity and human capital development
- Reserve duty / military service impact on workforce (Israel-specific)

**Governance**
Cross-reference with Section 8 (Management Quality & Governance). Summarize the key governance findings here:
- Board independence and effectiveness
- Controlling shareholder alignment
- Related-party transaction track record
- Executive compensation alignment

**ESG Screening Risk**
- Is {company_name} at risk of exclusion from ESG-screened funds or indices?
- Specific screening criteria that could apply (defense, settlements, environmental)
- Materiality: what % of the shareholder base applies ESG screens?
- Trend: is ESG-screening risk increasing or decreasing for this company?

**ESG Verdict**
Net ESG impact on investment case: Positive / Neutral / Negative.
Identify the single most material ESG factor and whether it is priced into the stock.
```

---

<!-- section: israel_risk_factors -->
## 16. Israel-Specific Risk Factors

### Purpose
Risks unique to investing in an Israeli-listed company. This section addresses the "Israel discount" and whether it is adequate, excessive, or insufficient given current conditions.

### Prompt
```
You are a country risk analyst specializing in Israeli capital markets, evaluating risk factors for {company_name} ({ticker}) traded on {market} in the {sector} sector. Date: {date}.

**Geopolitical & Security**
- Current security environment assessment and impact on business operations
- Reserve duty disruption: what percentage of {company_name}'s workforce is subject to reserve duty? What is the operational impact during escalations?
- Historical TASE performance during security escalations (quantify drawdown and recovery time)
- Defense spending crowding out effect on other government expenditure
- Impact on tourism, construction, and consumer confidence (sector-dependent)

**Macro & Currency**
- NIS/USD exchange rate outlook and {company_name}'s currency exposure
- Bank of Israel interest rate trajectory and impact on company's cost of capital
- Israeli GDP growth outlook relative to developed market peers
- Inflation trajectory and impact on costs / pricing power
- Housing market / consumer debt dynamics (if relevant to sector)

**Regulatory & Legal**
- Israel Competition Authority: current investigations or concerns in {sector}
- Pending legislation or regulation affecting {sector}
- Tax policy changes (corporate tax, R&D incentives, capital gains treatment)
- ISA (Securities Authority) regulatory posture: tightening or stable?

**Political & Institutional**
- Israel sovereign credit rating and trajectory
- Coalition stability and policy predictability
- Judicial reform / institutional stability implications for business environment
- International diplomatic relations impacting trade and investment flows

**International Exposure**
- BDS movement: actual commercial impact assessment (not theoretical, but measurable revenue or contract losses)
- Export controls: does {company_name} face restrictions on technology transfer or market access?
- ESG screening: are international investors excluding Israeli companies from portfolios?
- Dual-listing regulatory burden and compliance costs

**Capital Market Structural**
- TASE liquidity: average daily volume, comparison to peer exchanges
- Index concentration: is {company_name} included in TA-35 or TA-125? Passive flow implications
- Analyst coverage: number of covering analysts, quality of research available to international investors
- Settlement and custody: any friction for international investors?

**Risk Severity Matrix**

| Risk Factor | Severity | Probability | Trend | Unique to Israel? |
|------------|----------|-------------|-------|-------------------|
| Security escalation | H/M/L | H/M/L | Improving/Stable/Worsening | Yes/No |
| Currency volatility | ... | ... | ... | ... |
| Regulatory change | ... | ... | ... | ... |
| (continue for each material risk) |

**Net Israel Risk Assessment**
Is the current "Israel discount" (if observable in the valuation) adequate, excessive, or insufficient?
What is the single most important Israel-specific risk for {company_name}?
Under what conditions would you recommend increasing or decreasing the Israel risk premium applied to this company?
```

---

<!-- section: investment_conclusion -->
## 17. Qualitative Investment Conclusion

### Purpose
Synthesis of all qualitative findings into a clear, defensible investment signal. This is the section where the analyst takes a position and defends it to the investment committee.

### Prompt
```
You are the lead analyst presenting {company_name} ({ticker}) to the investment committee. You must deliver a clear signal, not a hedge. Date: {date}. Sector: {sector}. Market: {market}.

You have completed the following analysis:
{prior_sections}

**Investment Scorecard**

| Dimension | Score (1-5) | Justification |
|-----------|-------------|---------------|
| Market Opportunity | ... | (1 sentence) |
| Industry Dynamics | ... | (1 sentence) |
| Competitive Position | ... | (1 sentence) |
| Strategic Power (Seven Powers) | ... | (1 sentence) |
| Management & Governance | ... | (1 sentence) |
| Ownership Structure | ... | (1 sentence) |
| Financial Health | ... | (1 sentence) |
| Israel Risk | ... | (1 = severe, 5 = minimal) |

Scoring guide: 1 = Major concern, 2 = Below average, 3 = Average, 4 = Above average, 5 = Exceptional. Most companies should score between 2-4 on most dimensions. A score of 5 requires extraordinary evidence.

**Bull Case** (3-4 sentences)
The most compelling argument for owning this stock. Be specific about what must happen and the resulting upside.

**Bear Case** (3-4 sentences)
The most compelling argument against owning this stock. Be specific about what could go wrong and the resulting downside.

**Key Debates** (2-3 questions)
Where would reasonable, well-informed analysts disagree? Frame each debate as a specific question with two defensible answers.

**Diligence Gaps**
What information is missing that would materially change the analysis? Be specific about what data, meetings, or expert consultations are needed.

**Quantitative Hand-Off**
Specify the financial tests that the quantitative valuation (Section 11) must pass for the qualitative thesis to hold:
- Required revenue growth rate
- Required margin trajectory
- Required return on invested capital
- Maximum acceptable leverage
- Minimum free cash flow conversion

**VERDICT**: Qualitatively Compelling / Mixed / Unattractive
Justify in 2-3 sentences. If Mixed, state what would tip the verdict in either direction. Be direct. The committee needs a clear signal, not a hedged paragraph.
```

---

<!-- section: open_questions -->
## 18. Open Questions

### Purpose
Unanswered questions that emerged during analysis, requiring further research, management meetings, or expert consultations. Honest documentation of what the analyst does not know.

### Prompt
```
You are a research analyst documenting the open questions from your analysis of {company_name} ({ticker}) in {sector} on {market}. Date: {date}.

Review the complete analysis conducted so far:
{prior_sections}

List the key unanswered questions, organized by priority:

**Critical Questions** (answers would materially change the investment thesis)
For each: state the question, explain why it matters, and specify what data or meeting would answer it.

**Important Questions** (answers would refine the analysis but not change the conclusion)
For each: state the question, explain its relevance, and suggest the most efficient way to get an answer.

**Nice-to-Know** (would enhance completeness)
Brief list of secondary questions.

**Recommended Next Steps**
- Specific management meetings to request (with suggested questions)
- Expert consultations needed (industry, regulatory, technical)
- Data sources to acquire (industry reports, competitor filings, regulatory databases)
- Site visits or product evaluations recommended

For each question, rate the difficulty of obtaining an answer: Easy (public data) / Medium (requires access) / Hard (requires insider or expert knowledge).
```

---

<!-- section: action_items -->
## 19. Action Items

### Purpose
Concrete next steps for the research team to advance the analysis. Each action must have an owner, a deadline, and a clear deliverable.

### Prompt
```
You are the research team lead assigning follow-up tasks after reviewing the investment memo for {company_name} ({ticker}) in {sector} on {market}. Date: {date}.

Based on the analysis and open questions identified:

Generate 5-10 specific action items. Each action item must be a single clear sentence in the format:
"[ACTION] [SPECIFIC DELIVERABLE] by [TIMEFRAME]"

Examples:
- "Request IR meeting with CFO to clarify capex guidance for FY2026 by end of March"
- "Pull competitor X's latest annual report and update competitive positioning table by next week"
- "Model sensitivity of DCF to 200bps WACC increase given rising Israel risk premium by Friday"

Prioritize actions that would:
1. Close the most critical open questions from Section 18
2. Test the key assumptions underlying the investment thesis
3. Update any stale data points in the analysis
4. Prepare for upcoming catalysts identified in Section 14

Return as a list of strings, one action item per string.
```

---

<!-- section: appendix -->
## 20. Appendix

### Purpose
Supporting data, detailed financial tables, source references, methodology notes, and any supplementary material that supports the main analysis but would disrupt the flow of the narrative sections.

### Prompt
```
You are compiling the appendix for the investment memo on {company_name} ({ticker}) in {sector} on {market}. Date: {date}.

Include the following appendix items where data is available:

**A. Detailed Financial Tables**
- Multi-year income statement (5 years if available)
- Multi-year balance sheet
- Multi-year cash flow statement
- Key ratios table (profitability, leverage, liquidity, efficiency)

**B. Peer Comparison Data**
- Comprehensive peer valuation table
- Peer operating metrics comparison

**C. Source References**
- TASE filings referenced (with filing dates and document IDs)
- Third-party research cited
- News articles referenced
- Management presentations or conference call transcripts used

**D. Methodology Notes**
- DCF model assumptions and methodology
- Peer selection criteria
- Market sizing methodology and data sources
- Any adjustments made to reported financials (and justification)

**E. Glossary**
- Hebrew terms used (with English translations)
- Industry-specific terminology
- TASE-specific terms (Ma'of, TA-35, TA-125, etc.)

Format as clean, well-labeled sections. Tables should be in markdown format. This section is reference material -- clarity and organization matter more than narrative.
```

---

## Parser Reference

To extract sections programmatically, parse HTML comments matching the pattern:

`< !-- section: FIELD_NAME -- >`  (without spaces)

The `FIELD_NAME` maps directly to the corresponding field on the `InvestmentMemo` Pydantic model. The prompt text for each section is enclosed in the fenced code block under the `### Prompt` heading within that section.

### Field Name to Section Mapping

| # | Field Name | Section Title |
|---|-----------|---------------|
| 1 | `executive_summary` | Executive Summary & Investment Thesis |
| 2 | `company_overview` | Company Overview & Business Model |
| 3 | `market_size` | Market Size -- TAM / SAM / SOM |
| 4 | `industry_analysis` | Industry Trends & Dynamics |
| 5 | `competitive_positioning` | Competitive Landscape |
| 6 | `seven_powers` | Seven Powers Analysis |
| 7 | `swot_analysis` | SWOT Analysis |
| 8 | `management_governance` | Management Quality & Governance |
| 9 | `ownership_structure` | Ownership Structure & Shareholder Dynamics |
| 10 | `financial_analysis` | Financial Analysis |
| 11 | `valuation` | Valuation |
| 12 | `scenario_analysis` | Scenario Analysis |
| 13 | `risks_mitigants` | Risks & Mitigants |
| 14 | `catalysts_timeline` | Catalysts & Timeline |
| 15 | `esg_notes` | ESG & Governance Notes |
| 16 | `israel_risk_factors` | Israel-Specific Risk Factors |
| 17 | `investment_conclusion` | Qualitative Investment Conclusion |
| 18 | `open_questions` | Open Questions |
| 19 | `action_items` | Action Items |
| 20 | `appendix` | Appendix |
