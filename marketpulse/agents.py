"""Worker agents and aggregation logic for MarketPulse."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean

from marketpulse.contracts import (
    AggregatedInsight,
    FeatureFlags,
    MarketRecord,
    PricingData,
    PromoData,
    SentimentData,
    SupervisorDecision,
    WorkerName,
    WorkerOutput,
)

# Phase 6: Import social listening worker
from marketpulse.social_listening import run_social_worker

BASE_WORKERS: list[WorkerName] = ["pricing", "sentiment", "promo"]
BONUS_WORKERS: list[WorkerName] = ["social"]  # Phase 6 bonus worker

EDGE_RULES: dict[WorkerName, str] = {
    "pricing": "Run when at least one selected competitor has price data.",
    "sentiment": "Run when sentiment data exists for selected competitors.",
    "promo": "Run when promotion data exists for selected competitors.",
    "social": "Run only when enable_social_worker is true (Phase 6 bonus feature).",
}


def route_workers(records: list[MarketRecord], flags: FeatureFlags) -> SupervisorDecision:
    """Route workers using LLM-based supervisor with rule-based fallback."""
    from marketpulse.llm import create_supervisor_router

    import os

    api_key = os.environ.get("GEMINI_API_KEY")
    supervisor = create_supervisor_router(api_key)
    decision = supervisor.route(records, flags)

    # Add social worker if feature flag is enabled (Phase 6 bonus)
    if flags.enable_social_worker and "social" not in decision.selected_workers:
        if records:  # Only add if we have data
            decision.selected_workers.append("social")
            if "social" in decision.skipped_workers:
                del decision.skipped_workers["social"]

    return decision


def run_pricing_worker(records: list[MarketRecord], flags: FeatureFlags) -> WorkerOutput:
    """Analyze pricing data across competitors with optional delta detection."""
    by_competitor = _group_by_competitor(records)
    averages = {name: mean(item.price for item in rows) for name, rows in by_competitor.items()}
    lowest_name = min(averages, key=averages.get)
    highest_name = max(averages, key=averages.get)
    spread = averages[highest_name] - averages[lowest_name]

    bullets = [
        f"{lowest_name} owns the lowest average price at ${averages[lowest_name]:.2f}.",
        f"{highest_name} is highest at ${averages[highest_name]:.2f}, creating a ${spread:.2f} spread.",
    ]

    # Phase 6: Enhanced pricing delta detection
    if flags.enable_pricing_delta:
        from marketpulse.pricing_analysis import PricingAnalyzer

        analyzer = PricingAnalyzer()
        deltas = analyzer.analyze_weekly_deltas(records)
        trends = analyzer.detect_pricing_trends(records)
        alerts = analyzer.generate_pricing_alerts(deltas, trends)

        if deltas:
            bullets.extend(_pricing_delta_bullets(by_competitor))

        if alerts:
            bullets.extend([f"🚨 {alert}" for alert in alerts[:3]])  # Top 3 alerts

    return WorkerOutput(
        worker="pricing",
        title="Pricing intelligence",
        summary=f"Price spread is ${spread:.2f} across selected competitors.",
        bullets=bullets,
        metrics={
            "lowest_average_price": round(averages[lowest_name], 2),
            "highest_average_price": round(averages[highest_name], 2),
            "price_spread": round(spread, 2),
        },
        confidence=0.92,
    )


def run_sentiment_worker(records: list[MarketRecord], flags: FeatureFlags) -> WorkerOutput:
    """Analyze customer sentiment from social mentions and reviews."""
    by_competitor = _group_by_competitor(records)
    sentiment = {
        name: mean(item.social_sentiment for item in rows)
        for name, rows in by_competitor.items()
    }
    leader = max(sentiment, key=sentiment.get)
    concern = min(sentiment, key=sentiment.get)

    # Also analyze review scores if available
    review_scores = {
        name: mean(item.review_score for item in rows)
        for name, rows in by_competitor.items()
    }
    review_leader = max(review_scores, key=review_scores.get)

    bullets = [
        f"{leader} leads sentiment with an average score of {sentiment[leader]:.2f}.",
        f"{concern} has the lowest sentiment at {sentiment[concern]:.2f}.",
        f"{review_leader} has the highest review quality at {review_scores[review_leader]:.2f} out of 5.",
        "Sentiment trends should be monitored alongside pricing changes.",
    ]

    return WorkerOutput(
        worker="sentiment",
        title="Sentiment analysis",
        summary=f"{leader} demonstrates the strongest customer sentiment among competitors.",
        bullets=bullets,
        metrics={
            "sentiment_leader": leader,
            "leader_sentiment_score": round(sentiment[leader], 2),
            "concern_sentiment_score": round(sentiment[concern], 2),
            "review_leader": review_leader,
            "leader_review_score": round(review_scores[review_leader], 2),
        },
        confidence=0.88,
    )


def run_promo_worker(records: list[MarketRecord], flags: FeatureFlags) -> WorkerOutput:
    """Analyze promotion and discount strategies."""
    by_competitor = _group_by_competitor(records)

    # Count promotions by competitor
    promo_counts = {
        name: sum(1 for item in rows if item.promo.strip())
        for name, rows in by_competitor.items()
    }

    # Analyze promotion types
    promo_types: dict[str, list[str]] = {}
    for name, rows in by_competitor.items():
        types = [item.promo.strip() for item in rows if item.promo.strip()]
        promo_types[name] = list(set(types))

    most_active = max(promo_counts, key=promo_counts.get) if promo_counts else "None"
    total_promos = sum(promo_counts.values())

    bullets = [
        f"{most_active} is most promotionally active with {promo_counts[most_active]} promotions.",
        f"Total promotions across competitors: {total_promos}.",
    ]

    # Add promotion type insights
    if promo_types:
        type_count = sum(len(types) for types in promo_types.values())
        bullets.append(f"Competitors are using {type_count} different promotion types.")

        # Add specific promotion types for most active competitor
        if most_active in promo_types and promo_types[most_active]:
            bullets.append(f"{most_active} promotion types: {', '.join(promo_types[most_active][:3])}")

    bullets.append("Promotion frequency should be correlated with traffic and sentiment changes.")

    return WorkerOutput(
        worker="promo",
        title="Promotion analysis",
        summary=f"{most_active} leads in promotional activity with {promo_counts[most_active]} active promotions.",
        bullets=bullets,
        metrics={
            "most_active_promoter": most_active,
            "total_promotions": total_promos,
            "promotion_leader_count": promo_counts.get(most_active, 0),
        },
        confidence=0.85,
    )


def aggregate_outputs(outputs: dict[WorkerName, WorkerOutput]) -> AggregatedInsight:
    """Aggregate worker outputs into consolidated insights."""
    summaries = [output.summary for output in outputs.values()]
    risks = []
    opportunities = []
    actions = []

    if "pricing" in outputs:
        pricing = outputs["pricing"]
        opportunities.append(pricing.bullets[0])
        risks.append("Price gaps can trigger margin pressure if matched without promotion context.")
        actions.append("Set a price-watch threshold for the lowest-priced competitor.")

    if "sentiment" in outputs:
        sentiment = outputs["sentiment"]
        opportunities.append(sentiment.bullets[0])
        risks.append("Negative sentiment trends can amplify the impact of price increases.")
        actions.append("Monitor sentiment trends before and after promotional campaigns.")

    if "promo" in outputs:
        promo = outputs["promo"]
        opportunities.append(promo.bullets[0])
        risks.append("Over-promotion can train customers to wait for discounts.")
        actions.append("Analyze promotion effectiveness alongside traffic and sentiment data.")

    # Phase 6: Social worker insights
    if "social" in outputs:
        social = outputs["social"]
        opportunities.append(social.bullets[0])
        risks.append("Negative social sentiment can spread rapidly and impact brand perception.")
        actions.append("Monitor social conversations and engage with influencers proactively.")

    return AggregatedInsight(
        executive_summary=" ".join(summaries),
        risks=risks,
        opportunities=opportunities,
        recommended_actions=actions,
    )


def run_worker(worker: WorkerName, records: list[MarketRecord], flags: FeatureFlags) -> WorkerOutput:
    """Run a specific worker based on worker name."""
    dispatch = {
        "pricing": run_pricing_worker,
        "sentiment": run_sentiment_worker,
        "promo": run_promo_worker,
        "social": run_social_worker,  # Phase 6 bonus worker
    }
    return dispatch[worker](records, flags)


def _group_by_competitor(records: list[MarketRecord]) -> dict[str, list[MarketRecord]]:
    """Group records by competitor for analysis."""
    grouped: dict[str, list[MarketRecord]] = defaultdict(list)
    for record in records:
        grouped[record.competitor].append(record)
    return dict(grouped)


def _pricing_delta_bullets(
    by_competitor: dict[str, list[MarketRecord]],
) -> list[str]:
    """Generate week-over-week pricing delta bullets."""
    bullets = []
    for competitor, rows in sorted(by_competitor.items()):
        ordered = sorted(rows, key=lambda item: item.week_start)
        if len(ordered) < 2:
            continue
        first = ordered[0].price
        latest = ordered[-1].price
        delta = latest - first
        direction = "increased" if delta > 0 else "decreased" if delta < 0 else "held flat"
        bullets.append(
            f"{competitor} price {direction} by ${abs(delta):.2f} from first to latest week."
        )
    return bullets


def create_pricing_data(outputs: dict[WorkerName, WorkerOutput]) -> PricingData:
    """Create structured pricing data from worker outputs."""
    if "pricing" not in outputs:
        return PricingData(
            lowest_average_price=0.0,
            highest_average_price=0.0,
            price_spread=0.0,
            lowest_priced_competitor="",
            highest_priced_competitor="",
        )

    pricing = outputs["pricing"]
    metrics = pricing.metrics

    return PricingData(
        lowest_average_price=float(metrics.get("lowest_average_price", 0.0)),
        highest_average_price=float(metrics.get("highest_average_price", 0.0)),
        price_spread=float(metrics.get("price_spread", 0.0)),
        lowest_priced_competitor=pricing.bullets[0].split(" owns the lowest")[0].strip() if pricing.bullets else "",
        highest_priced_competitor=pricing.bullets[1].split(" is highest")[0].strip() if len(pricing.bullets) > 1 else "",
    )


def create_sentiment_data(outputs: dict[WorkerName, WorkerOutput]) -> SentimentData:
    """Create structured sentiment data from worker outputs."""
    if "sentiment" not in outputs:
        return SentimentData(
            overall_sentiment_leader="",
            leader_sentiment_score=0.0,
            sentiment_concern="",
            concern_sentiment_score=0.0,
        )

    sentiment = outputs["sentiment"]
    metrics = sentiment.metrics

    return SentimentData(
        overall_sentiment_leader=str(metrics.get("sentiment_leader", "")),
        leader_sentiment_score=float(metrics.get("leader_sentiment_score", 0.0)),
        sentiment_concern=str(metrics.get("concern", "")),
        concern_sentiment_score=float(metrics.get("concern_sentiment_score", 0.0)),
    )


def create_promo_data(outputs: dict[WorkerName, WorkerOutput]) -> PromoData:
    """Create structured promotion data from worker outputs."""
    if "promo" not in outputs:
        return PromoData(
            most_active_promoter="",
            promotion_frequency={},
            promotion_types={},
            effectiveness_score={},
        )

    promo = outputs["promo"]
    metrics = promo.metrics

    return PromoData(
        most_active_promoter=str(metrics.get("most_active_promoter", "")),
        promotion_frequency={
            "total": int(metrics.get("total_promotions", 0)),
            "leader": int(metrics.get("promotion_leader_count", 0)),
        },
        promotion_types={},
        effectiveness_score={},
    )
