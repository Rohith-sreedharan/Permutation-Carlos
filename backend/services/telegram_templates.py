"""
Telegram Templates - Institutional-Grade Locked Templates
Status: LOCKED - NO DYNAMIC TEMPLATES ALLOWED

All templates must be reviewed and approved before use.
Templates are immutable once approved (version-controlled).

Templates:
1. TG_EDGE_V1 - Clean EDGE post with all numbers
2. TG_LEAN_V1 - LEAN post (optional EV omission)
3. TG_EDGE_CONSTRAINED_V1 - EDGE with constraint notice
4. TG_LEAN_CONSTRAINED_V1 - LEAN with constraint notice
5. TG_MARKET_ALIGNED_V1 - Transparency update (no recommendation language)
"""

from typing import Dict, Any
from jinja2 import Template


# ==================== HELPER FILTERS ====================

def format_percentage(value: float, signed: bool = False) -> str:
    """Format decimal as percentage"""
    pct = value * 100
    if signed and pct > 0:
        return f"+{pct:.1f}%"
    return f"{pct:.1f}%"


def format_line(value: float, market_type: str) -> str:
    """Format line based on market type"""
    if market_type == "TOTAL":
        # Totals show unsigned (e.g., "221.5")
        return f"{value:.1f}"
    else:
        # Spreads show signed (e.g., "-3.5", "+7.5")
        if value > 0:
            return f"+{value:.1f}"
        return f"{value:.1f}"


def format_odds(value: int) -> str:
    """Format American odds"""
    if value > 0:
        return f"+{value}"
    return str(value)


def format_side_label(side: str, market_type: str, team_name: str, line: float) -> str:
    """
    Format the market selection label.
    
    Examples:
    - SPREAD: "Boston Celtics -3.5"
    - MONEYLINE: "Boston Celtics"
    - TOTAL: "Over 221.5" or "Under 221.5"
    """
    if market_type == "TOTAL":
        if side == "OVER":
            return f"Over {line:.1f}"
        else:
            return f"Under {line:.1f}"
    elif market_type == "SPREAD":
        return f"{team_name} {format_line(line, market_type)}"
    else:  # MONEYLINE
        return team_name


# ==================== TEMPLATE DEFINITIONS ====================

# Template 1: TG_EDGE_V1 (clean EDGE post)
TG_EDGE_V1_TEXT = """📊 {{ league|upper }} — {{ market_type }}
{{ selection_label }} ({{ odds }})
Model Prob: {{ model_prob }}
Market Prob: {{ market_prob }}
Prob Edge: {{ prob_edge }}
{% if ev %}EV: {{ ev }}
{% endif %}Classification: EDGE

🔗 {{ cta_url }}"""

TG_EDGE_V1 = {
    "template_id": "TG_EDGE_V1",
    "tier": "EDGE",
    "constraints_mode": "none",
    "template_text": TG_EDGE_V1_TEXT,
    "required_fields": [
        "league",
        "market_type",
        "team_name",
        "selection_label",
        "odds",
        "model_prob",
        "market_prob",
        "prob_edge",
        "cta_url",
    ],
    "optional_fields": ["ev"],
    "forbidden_phrases": [],
    "version": "1.0.0",
    "approved_by": "system_admin",
    "description": "Standard EDGE post with all probabilities and edges",
}


# Template 2: TG_LEAN_V1 (clean LEAN post)
TG_LEAN_V1_TEXT = """📊 {{ league|upper }} — {{ market_type }}
{{ selection_label }} ({{ odds }})
Model Prob: {{ model_prob }}
Market Prob: {{ market_prob }}
Prob Edge: {{ prob_edge }}
{% if ev %}EV: {{ ev }}
{% endif %}Classification: LEAN — Proceed with caution

🔗 {{ cta_url }}"""

TG_LEAN_V1 = {
    "template_id": "TG_LEAN_V1",
    "tier": "LEAN",
    "constraints_mode": "none",
    "template_text": TG_LEAN_V1_TEXT,
    "required_fields": [
        "league",
        "market_type",
        "team_name",
        "selection_label",
        "odds",
        "model_prob",
        "market_prob",
        "prob_edge",
        "cta_url",
    ],
    "optional_fields": ["ev"],
    "forbidden_phrases": [],
    "version": "1.0.0",
    "approved_by": "system_admin",
    "description": "Standard LEAN post with caution notice",
}


# Template 3: TG_EDGE_CONSTRAINED_V1 (EDGE with constraints)
TG_EDGE_CONSTRAINED_V1_TEXT = """📊 {{ league|upper }} — {{ market_type }}
{{ selection_label }} ({{ odds }})
Model Prob: {{ model_prob }}
Market Prob: {{ market_prob }}
Prob Edge: {{ prob_edge }}
{% if ev %}EV: {{ ev }}
{% endif %}Classification: EDGE (CONSTRAINED)

⚠️ Signal is constrained due to {{ constraint_reasons }}. Proceed with caution — explanation limited.

🔗 {{ cta_url }}"""

TG_EDGE_CONSTRAINED_V1 = {
    "template_id": "TG_EDGE_CONSTRAINED_V1",
    "tier": "EDGE",
    "constraints_mode": "constrained",
    "template_text": TG_EDGE_CONSTRAINED_V1_TEXT,
    "required_fields": [
        "league",
        "market_type",
        "team_name",
        "selection_label",
        "odds",
        "model_prob",
        "market_prob",
        "prob_edge",
        "constraint_reasons",
        "cta_url",
    ],
    "optional_fields": ["ev"],
    "forbidden_phrases": [
        # Hard constraint: CANNOT contain narrative beyond constraint notice
        "because",
        "injury",
        "sharp",
        "steam",
        "public",
        "confident",
        "lock",
        "guaranteed",
    ],
    "version": "1.0.0",
    "approved_by": "system_admin",
    "description": "EDGE post with constraint notice (no narrative explanations)",
}


# Template 4: TG_LEAN_CONSTRAINED_V1 (LEAN with constraints)
TG_LEAN_CONSTRAINED_V1_TEXT = """📊 {{ league|upper }} — {{ market_type }}
{{ selection_label }} ({{ odds }})
Model Prob: {{ model_prob }}
Market Prob: {{ market_prob }}
Prob Edge: {{ prob_edge }}
{% if ev %}EV: {{ ev }}
{% endif %}Classification: LEAN (CONSTRAINED)

⚠️ Signal is constrained due to {{ constraint_reasons }}. Proceed with caution — explanation limited.

🔗 {{ cta_url }}"""

TG_LEAN_CONSTRAINED_V1 = {
    "template_id": "TG_LEAN_CONSTRAINED_V1",
    "tier": "LEAN",
    "constraints_mode": "constrained",
    "template_text": TG_LEAN_CONSTRAINED_V1_TEXT,
    "required_fields": [
        "league",
        "market_type",
        "team_name",
        "selection_label",
        "odds",
        "model_prob",
        "market_prob",
        "prob_edge",
        "constraint_reasons",
        "cta_url",
    ],
    "optional_fields": ["ev"],
    "forbidden_phrases": [
        # Same hard constraint as EDGE_CONSTRAINED
        "because",
        "injury",
        "sharp",
        "steam",
        "public",
        "confident",
        "lock",
        "guaranteed",
    ],
    "version": "1.0.0",
    "approved_by": "system_admin",
    "description": "LEAN post with constraint notice (no narrative explanations)",
}


# Template 5: TG_MARKET_ALIGNED_V1 (transparency update, no recommendation)
TG_MARKET_ALIGNED_V1_TEXT = """📊 {{ league|upper }} — {{ market_type }}
{{ selection_label }} ({{ odds }})
Model Prob: {{ model_prob }}
Market Prob: {{ market_prob }}
Prob Edge: {{ prob_edge }}

Classification: MARKET_ALIGNED — No edge detected. Informational only.

🔗 {{ cta_url }}"""

TG_MARKET_ALIGNED_V1 = {
    "template_id": "TG_MARKET_ALIGNED_V1",
    "tier": "MARKET_ALIGNED",
    "constraints_mode": "none",
    "template_text": TG_MARKET_ALIGNED_V1_TEXT,
    "required_fields": [
        "league",
        "market_type",
        "team_name",
        "selection_label",
        "odds",
        "model_prob",
        "market_prob",
        "prob_edge",
        "cta_url",
    ],
    "optional_fields": [],
    "forbidden_phrases": [
        # MARKET_ALIGNED cannot contain recommendation language
        "recommend",
        "play",
        "bet",
        "edge",
        "value",
        "sharp",
        "confident",
        "lock",
    ],
    "version": "1.0.0",
    "approved_by": "system_admin",
    "description": "Market transparency update (no recommendation language)",
}


# ==================== TEMPLATE REGISTRY ====================

TEMPLATE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "TG_EDGE_V1": TG_EDGE_V1,
    "TG_LEAN_V1": TG_LEAN_V1,
    "TG_EDGE_CONSTRAINED_V1": TG_EDGE_CONSTRAINED_V1,
    "TG_LEAN_CONSTRAINED_V1": TG_LEAN_CONSTRAINED_V1,
    "TG_MARKET_ALIGNED_V1": TG_MARKET_ALIGNED_V1,
}


# ==================== TEMPLATE SELECTOR ====================

def select_template(tier: str, constraints_mode: str) -> str:
    """
    Select appropriate template based on tier and constraints.
    
    Args:
        tier: EDGE, LEAN, or MARKET_ALIGNED
        constraints_mode: "none" or "constrained"
    
    Returns:
        template_id
    
    Raises:
        ValueError if no matching template found
    """
    # Build template key
    if constraints_mode == "constrained":
        template_key = f"TG_{tier}_CONSTRAINED_V1"
    else:
        template_key = f"TG_{tier}_V1"
    
    if template_key not in TEMPLATE_REGISTRY:
        raise ValueError(f"No template found for tier={tier}, constraints_mode={constraints_mode}")
    
    return template_key


# ==================== TEMPLATE RENDERER ====================

class TelegramTemplateRenderer:
    """
    Renders Telegram posts from templates.
    
    HARD RULE: Only fills slots, never computes or modifies values.
    """
    
    def __init__(self):
        # Precompile all templates
        self.compiled_templates: Dict[str, Template] = {}
        for template_id, template_def in TEMPLATE_REGISTRY.items():
            self.compiled_templates[template_id] = Template(template_def["template_text"])
    
    def render(self, template_id: str, context: Dict[str, Any]) -> str:
        """
        Render template with given context.
        
        Args:
            template_id: Template to use
            context: Values to fill (all must come from canonical payload)
        
        Returns:
            Rendered text
        
        Raises:
            ValueError if template not found or required fields missing
        """
        if template_id not in self.compiled_templates:
            raise ValueError(f"Template '{template_id}' not found")
        
        # Get template definition
        template_def = TEMPLATE_REGISTRY[template_id]
        
        # Validate required fields present
        missing_fields = []
        for field in template_def["required_fields"]:
            if field not in context or context[field] is None:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(
                f"Missing required fields for template '{template_id}': {missing_fields}"
            )
        
        # Render
        template = self.compiled_templates[template_id]
        rendered = template.render(**context)
        
        return rendered.strip()


# ==================== CONTEXT BUILDER ====================

def build_render_context(queue_item) -> Dict[str, Any]:
    """
    Build template render context from queue item.
    
    CRITICAL: All values come directly from queue_item (canonical payload).
    NO computation, NO inference.
    
    Args:
        queue_item: TelegramQueueItem
    
    Returns:
        Context dict for template rendering
    """
    from backend.db.telegram_schemas import TelegramQueueItem
    
    # Format selection label
    selection_label = format_side_label(
        side=queue_item.selection.side,
        market_type=queue_item.market_type,
        team_name=queue_item.selection.team_name,
        line=queue_item.selection.line if queue_item.selection.line is not None else 0.0,
    )
    
    # Format odds
    odds = format_odds(queue_item.selection.american_odds) if queue_item.selection.american_odds else "N/A"
    
    # Format probabilities and edges
    model_prob = format_percentage(queue_item.pricing.model_prob)
    market_prob = format_percentage(queue_item.pricing.market_prob)
    prob_edge = format_percentage(queue_item.pricing.prob_edge, signed=True)
    ev = format_percentage(queue_item.pricing.ev, signed=True) if queue_item.pricing.ev is not None else None
    
    # Format constraint reasons (if constrained)
    constraint_reasons = ", ".join(queue_item.constraints.reason_codes) if queue_item.constraints.reason_codes else "data limitations"
    
    # Build context
    context = {
        # Event metadata
        "league": queue_item.league,
        "market_type": queue_item.market_type,
        
        # Selection
        "team_name": queue_item.selection.team_name,
        "selection_label": selection_label,
        "odds": odds,
        
        # Probabilities
        "model_prob": model_prob,
        "market_prob": market_prob,
        "prob_edge": prob_edge,
        "ev": ev,
        
        # Constraints
        "constraint_reasons": constraint_reasons,
        
        # CTA
        "cta_url": queue_item.display.cta_url,
    }
    
    return context


# ==================== CONVENIENCE FUNCTION ====================

def render_telegram_post(queue_item) -> tuple[str, str]:
    """
    Render Telegram post from queue item.
    
    Args:
        queue_item: TelegramQueueItem
    
    Returns:
        (rendered_text, template_id_used)
    
    Raises:
        ValueError if rendering fails
    """
    # Select template
    template_id = select_template(
        tier=queue_item.tier,
        constraints_mode=queue_item.constraints.mode
    )
    
    # Build context
    context = build_render_context(queue_item)
    
    # Render
    renderer = TelegramTemplateRenderer()
    rendered_text = renderer.render(template_id, context)
    
    return rendered_text, template_id


if __name__ == "__main__":
    # Test rendering
    from datetime import datetime
    from backend.db.telegram_schemas import (
        TelegramQueueItem,
        TelegramSelection,
        TelegramPricing,
        TelegramDisplay,
        TelegramConstraints,
    )
    
    # Test EDGE (unconstrained)
    queue_item = TelegramQueueItem(
        queue_id="test_q1",
        event_id="evt_test",
        league="nba",
        market_type="SPREAD",
        prediction_log_id="pred_test",
        snapshot_hash="snap_test",
        model_version="v2.1.0",
        sim_count=100000,
        generated_at=datetime.utcnow(),
        tier="EDGE",
        constraints=TelegramConstraints(mode="none", reason_codes=[]),
        selection=TelegramSelection(
            selection_id="sel_test",
            team_id="team_bos",
            team_name="Boston Celtics",
            side="AWAY",
            line=-3.5,
            american_odds=-110
        ),
        pricing=TelegramPricing(
            model_prob=0.602,
            market_prob=0.502,
            prob_edge=0.100,
            ev=0.145
        ),
        display=TelegramDisplay(
            allowed=True,
            template_id="TG_EDGE_V1",
            posted_at=None,
            telegram_message_id=None
        ),
        home_team="Golden State Warriors",
        away_team="Boston Celtics",
        start_time=datetime.utcnow()
    )
    
    rendered, template_id = render_telegram_post(queue_item)
    print("=== EDGE (Unconstrained) ===")
    print(rendered)
    print(f"\nTemplate used: {template_id}\n")
    
    # Test LEAN (constrained)
    queue_item.tier = "LEAN"
    queue_item.constraints = TelegramConstraints(
        mode="constrained",
        reason_codes=["OVERRIDE_DOWNGRADED", "MISSING_ODDS_FALLBACK"]
    )
    
    rendered, template_id = render_telegram_post(queue_item)
    print("=== LEAN (Constrained) ===")
    print(rendered)
    print(f"\nTemplate used: {template_id}\n")
    
    # Test TOTAL market
    queue_item.market_type = "TOTAL"
    queue_item.tier = "EDGE"
    queue_item.constraints = TelegramConstraints(mode="none", reason_codes=[])
    queue_item.selection.side = "OVER"
    queue_item.selection.line = 221.5
    queue_item.selection.team_name = ""  # Totals don't have team
    
    rendered, template_id = render_telegram_post(queue_item)
    print("=== TOTAL (Over) ===")
    print(rendered)
    print(f"\nTemplate used: {template_id}\n")
