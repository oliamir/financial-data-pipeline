import json
import os
from datetime import datetime
from typing import Optional

from .providers import BaseProvider
from ..models.memo import InvestmentMemo, Scenario, RiskEntry, ThesisEvent

MEMO_PROMPT = """
You are a Senior Investment Analyst at a top-tier buy-side firm. You maintain structured investment memos.

CURRENT MEMO STATE:
{current_memo}

NEW DOCUMENT: (attached)
File: {filename}

TASK: Update the investment memo based on the new document. Return a JSON object with this structure:

{{
    "recommendation": "buy" or "hold" or "sell" or "monitor",
    "conviction": "high" or "medium" or "low",
    "thesis_status": "new" or "intact" or "strengthening" or "weakening" or "broken",
    "one_line_thesis": "Single sentence thesis",
    "executive_summary": "2-3 paragraph executive summary with key numbers",
    "company_overview": "Company description, products, markets",
    "financial_summary": "Key financial metrics and trends discussion",
    "competitive_positioning": "Market position, competitive advantages/disadvantages",
    "management_notes": "Key management observations if available",
    "scenarios": [
        {{
            "name": "bull",
            "probability_pct": 25,
            "description": "Bull case narrative",
            "key_assumptions": ["assumption 1", "assumption 2"],
            "catalyst_or_risk": "What needs to go right"
        }},
        {{
            "name": "base",
            "probability_pct": 55,
            "description": "Base case narrative",
            "key_assumptions": ["assumption 1"],
            "catalyst_or_risk": "Most likely path"
        }},
        {{
            "name": "bear",
            "probability_pct": 20,
            "description": "Bear case narrative",
            "key_assumptions": ["assumption 1"],
            "catalyst_or_risk": "What goes wrong"
        }}
    ],
    "risks": [
        {{
            "category": "operational" or "market" or "financial" or "regulatory",
            "severity": "high" or "medium" or "low",
            "description": "Risk description",
            "mitigation": "How it is mitigated"
        }}
    ],
    "latest_event": {{
        "event": "Brief summary of what this report reveals",
        "impact": "positive" or "negative" or "neutral"
    }},
    "open_questions": ["Question 1?", "Question 2?"],
    "raw_narrative": "Detailed free-form analysis text (as long as needed)"
}}

RULES:
- If no previous memo exists, create a comprehensive new one.
- If a previous memo exists, UPDATE it with new information. Strengthen or weaken thesis based on evidence.
- Scenario probabilities must sum to approximately 100%.
- Be specific with numbers. Cite revenue, margins, growth rates from the document.
- Include TASE-specific risks (geopolitical, FX, liquidity).
- Return ONLY valid JSON.
"""


def generate_memo(
    provider: BaseProvider,
    file_path: str,
    company_slug: str,
    current_memo: Optional[dict] = None,
) -> InvestmentMemo:
    """Generate or update an investment memo from a new document."""
    memo_state = json.dumps(current_memo, indent=2) if current_memo else "(No previous memo. Create new.)"
    filename = os.path.basename(file_path)

    prompt = MEMO_PROMPT.format(
        current_memo=memo_state,
        filename=filename,
    )

    print(f"  [Memo] Generating/updating memo from {filename}...")
    response = provider.prompt_with_document(file_path, prompt)

    # Parse JSON
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        data = json.loads(response[start:end])
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  [Memo] JSON parse error: {e}")
        # Return a minimal memo with the raw response
        return InvestmentMemo(
            company_slug=company_slug,
            last_updated=datetime.now().isoformat(),
            raw_narrative=response,
        )

    now = datetime.now().isoformat()

    # Build scenarios
    scenarios = []
    for s in data.get("scenarios", []):
        scenarios.append(Scenario(
            name=s.get("name", "base"),
            probability_pct=s.get("probability_pct", 0),
            target_price=s.get("target_price"),
            currency=s.get("currency", "USD"),
            description=s.get("description", ""),
            key_assumptions=s.get("key_assumptions", []),
            catalyst_or_risk=s.get("catalyst_or_risk", ""),
        ))

    # Build risks
    risks = []
    for r in data.get("risks", []):
        risks.append(RiskEntry(
            category=r.get("category", "operational"),
            severity=r.get("severity", "medium"),
            description=r.get("description", ""),
            mitigation=r.get("mitigation"),
            monitoring_trigger=r.get("monitoring_trigger"),
        ))

    # Build thesis timeline
    timeline = []
    if current_memo and "thesis_timeline" in current_memo:
        for t in current_memo["thesis_timeline"]:
            timeline.append(ThesisEvent(
                date=t["date"],
                event=t["event"],
                source_file=t.get("source_file", ""),
                impact=t.get("impact", "neutral"),
            ))

    # Add latest event
    latest = data.get("latest_event", {})
    if latest:
        timeline.append(ThesisEvent(
            date=now[:10],
            event=latest.get("event", f"Processed {filename}"),
            source_file=filename,
            impact=latest.get("impact", "neutral"),
        ))

    memo = InvestmentMemo(
        company_slug=company_slug,
        last_updated=now,
        recommendation=data.get("recommendation", "monitor"),
        conviction=data.get("conviction", "low"),
        thesis_status=data.get("thesis_status", "new"),
        executive_summary=data.get("executive_summary", ""),
        one_line_thesis=data.get("one_line_thesis", ""),
        company_overview=data.get("company_overview", ""),
        financial_summary=data.get("financial_summary", ""),
        competitive_positioning=data.get("competitive_positioning", ""),
        management_notes=data.get("management_notes", ""),
        scenarios=scenarios,
        risks=risks,
        thesis_timeline=timeline,
        raw_narrative=data.get("raw_narrative", ""),
    )

    return memo
