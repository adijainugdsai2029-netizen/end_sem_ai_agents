# MarketPulse Requirements Compliance Implementation Plan

## Executive Summary

**Objective:** Refactor MarketPulse data structures to achieve 100% compliance with Problem 1 requirements  
**Current Status:** 75% compliant (critical data structure gaps)  
**Target Status:** 100% compliant  
**Timeline:** 2-3 days  
**Risk Level:** HIGH (breaking changes to state contract)

## Critical Issues Identified

### Data Structure Mismatches (Section 4.2 Requirements)

**Required vs Current:**
- `pricing_data: dict[str, list[PricePoint]]` ❌ Currently: `PricingData`
- `sentiment_data: dict[str, SentimentSummary]` ❌ Currently: `SentimentData`  
- `promo_data: dict[str, list[Promotion]]` ❌ Currently: `PromoData`

## Implementation Strategy

### Phase 1: Data Model Creation (Day 1 - Morning)

**Priority:** CRITICAL  
**Effort:** 2-3 hours  
**Deliverables:** New Pydantic models matching exact requirements

#### Task 1.1: Create PricePoint Model
```python
class PricePoint(BaseModel):
    """Individual SKU pricing data point."""
    sku: str
    price: float = Field(gt=0, description="Price must be positive")
    competitor: str
    week_start: date
    product: str
```

#### Task 1.2: Create SentimentSummary Model
```python
class SentimentSummary(BaseModel):
    """Competitor-specific sentiment summary."""
    competitor: str
    overall_sentiment: float = Field(ge=-1.0, le=1.0)
    review_themes: list[str] = Field(default_factory=list)
    sample_reviews: list[str] = Field(default_factory=list)
    sentiment_distribution: dict[str, int] = Field(default_factory=dict)
    review_count: int = Field(ge=0, default=0)
```

#### Task 1.3: Create Promotion Model
```python
class Promotion(BaseModel):
    """Individual promotion data."""
    competitor: str
    promo_type: str
    discount_depth: float = Field(ge=0.0, le=1.0)
    promo_copy: str
    start_date: date
    end_date: date | None = None
    product: str | None = None
```

### Phase 2: State Contract Update (Day 1 - Afternoon)

**Priority:** CRITICAL  
**Effort:** 2-3 hours  
**Deliverables:** Updated MarketPulseState with compliant structures

#### Task 2.1: Update MarketPulseState
```python
class MarketPulseState(BaseModel):
    """Complete state for MarketPulse workflow execution."""
    
    # Required fields (Section 4.2)
    competitors: list[str]
    pricing_data: dict[str, list[PricePoint]] = Field(default_factory=dict)
    sentiment_data: dict[str, SentimentSummary] = Field(default_factory=dict)
    promo_data: dict[str, list[Promotion]] = Field(default_factory=dict)
    final_brief: str = ""
    
    # Additional workflow fields
    question: str
    records: list[MarketRecord] = Field(default_factory=list)
    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags)
    run_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    
    # Workflow state
    supervisor_decision: SupervisorDecision | None = None
    worker_outputs: dict[WorkerName, WorkerOutput] = Field(default_factory=dict)
    aggregated: AggregatedInsight | None = None
    structured_brief: FinalBrief | None = None
    
    # Logging
    logs: list[NodeLog] = Field(default_factory=list)
```

#### Task 2.2: Update Helper Methods
- Maintain existing `add_log()` method
- Update `to_markdown_brief()` to work with new structures
- Ensure backward compatibility where possible

### Phase 3: Worker Implementation Updates (Day 2 - Morning)

**Priority:** HIGH  
**Effort:** 3-4 hours  
**Deliverables:** Updated workers returning compliant data structures

#### Task 3.1: Update Pricing Worker
```python
def run_pricing_worker(records: list[MarketRecord], flags: FeatureFlags) -> WorkerOutput:
    """Extract pricing data per SKU as required."""
    # Convert records to PricePoint format
    price_points: list[PricePoint] = []
    for record in records:
        price_point = PricePoint(
            sku=f"{record.competitor}_{record.product}",
            price=record.price,
            competitor=record.competitor,
            week_start=record.week_start,
            product=record.product
        )
        price_points.append(price_point)
    
    # Group by competitor
    pricing_dict: dict[str, list[PricePoint]] = {}
    for point in price_points:
        if point.competitor not in pricing_dict:
            pricing_dict[point.competitor] = []
        pricing_dict[point.competitor].append(point)
    
    # Create worker output
    return WorkerOutput(
        worker="pricing",
        title="Pricing Analysis",
        summary=f"Analyzed {len(price_points)} price points across {len(pricing_dict)} competitors",
        bullets=[...],
        metrics={"total_price_points": len(price_points), "competitors": len(pricing_dict)},
        confidence=0.9
    )
```

#### Task 3.2: Update Sentiment Worker
```python
def run_sentiment_worker(records: list[MarketRecord], flags: FeatureFlags) -> WorkerOutput:
    """Summarise customer reviews into sentiment themes."""
    # Group by competitor and create sentiment summaries
    sentiment_dict: dict[str, SentimentSummary] = {}
    
    for competitor in set(record.competitor for record in records):
        competitor_records = [r for r in records if r.competitor == competitor]
        
        # Calculate sentiment
        sentiments = [r.social_sentiment for r in competitor_records]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
        
        # Extract themes (simplified)
        themes = ["product quality", "customer service", "value for money"]
        
        sentiment_summary = SentimentSummary(
            competitor=competitor,
            overall_sentiment=avg_sentiment,
            review_themes=themes,
            sample_reviews=[],
            sentiment_distribution={"positive": 0, "negative": 0, "neutral": 0},
            review_count=len(competitor_records)
        )
        sentiment_dict[competitor] = sentiment_summary
    
    return WorkerOutput(
        worker="sentiment",
        title="Sentiment Analysis",
        summary=f"Analyzed sentiment across {len(sentiment_dict)} competitors",
        bullets=[...],
        metrics={"competitors_analyzed": len(sentiment_dict)},
        confidence=0.85
    )
```

#### Task 3.3: Update Promo Worker
```python
def run_promo_worker(records: list[MarketRecord], flags: FeatureFlags) -> WorkerOutput:
    """Identify active deals, discount depth, and promotion copy."""
    # Extract promotions from records
    promo_dict: dict[str, list[Promotion]] = {}
    
    for record in records:
        if record.promo:  # If there's promotional content
            promotion = Promotion(
                competitor=record.competitor,
                promo_type="discount",  # Simplified type detection
                discount_depth=0.1,  # Simplified discount calculation
                promo_copy=record.promo,
                start_date=record.week_start,
                end_date=None,
                product=record.product
            )
            
            if record.competitor not in promo_dict:
                promo_dict[record.competitor] = []
            promo_dict[record.competitor].append(promotion)
    
    return WorkerOutput(
        worker="promo",
        title="Promotional Activity",
        summary=f"Identified {sum(len(v) for v in promo_dict.values())} promotions",
        bullets=[...],
        metrics={"total_promotions": sum(len(v) for v in promo_dict.values())},
        confidence=0.8
    )
```

### Phase 4: Aggregator Update (Day 2 - Afternoon)

**Priority:** HIGH  
**Effort:** 2-3 hours  
**Deliverables:** Updated aggregator working with new data structures

#### Task 4.1: Update Aggregation Logic
```python
def aggregate_outputs(outputs: dict[WorkerName, WorkerOutput]) -> AggregatedInsight:
    """Merge worker outputs into unified insights using new data structures."""
    # Extract insights from the new data structures
    risks = []
    opportunities = []
    actions = []
    
    # Analyze pricing data for risks/opportunities
    # Analyze sentiment data for insights
    # Analyze promo data for competitive intelligence
    
    return AggregatedInsight(
        executive_summary="Competitive analysis complete",
        risks=risks,
        opportunities=opportunities,
        recommended_actions=actions
    )
```

### Phase 5: Testing & Validation (Day 3 - Morning)

**Priority:** HIGH  
**Effort:** 3-4 hours  
**Deliverables:** All tests passing, validation complete

#### Task 5.1: Update Existing Tests
- Modify `test_graph.py` to work with new structures
- Update `test_phase6.py` for compatibility
- Ensure all 38 tests still pass

#### Task 5.2: Add New Tests
- Test new data model validation
- Test worker output format compliance
- Test aggregator with new structures

#### Task 5.3: Manual Testing
- Test complete workflow end-to-end
- Verify Streamlit UI displays correctly
- Check data structures in UI sidebar

### Phase 6: Documentation Updates (Day 3 - Afternoon)

**Priority:** MEDIUM  
**Effort:** 2-3 hours  
**Deliverables:** Updated documentation reflecting changes

#### Task 6.1: Update Architecture Docs
- Modify `docs/hld.md` with new data structures
- Update `docs/phase6_architecture.md`
- Revise `docs/graph_diagram.md`

#### Task 6.2: Update README
- Document new data structures
- Update examples and usage
- Revise technical specifications

#### Task 6.3: Update Presentation
- Modify slides to reflect correct architecture
- Update technical details
- Ensure compliance claims are accurate

## Risk Management

### High-Risk Areas

1. **Breaking Changes to State Contract**
   - **Mitigation:** Comprehensive testing, gradual rollout
   - **Fallback:** Maintain backward compatibility methods

2. **Worker Output Format Changes**
   - **Mitigation:** Thorough testing of each worker
   - **Fallback:** Keep old implementations as reference

3. **Aggregator Logic Complexity**
   - **Mitigation:** Step-by-step testing, unit tests
   - **Fallback:** Simplified aggregation if needed

### Contingency Plans

**If critical issues arise:**
1. Roll back to previous implementation
2. Implement hybrid approach (wrapper layer)
3. Extend timeline by 1 day if needed

## Success Criteria

### Must-Have (Blocking)
- ✅ All Section 4.2 data structures match exactly
- ✅ All 38 tests pass
- ✅ Streamlit UI functions correctly
- ✅ Demo flow works as specified

### Should-Have (Important)
- ✅ No performance regression
- ✅ Clean code architecture
- ✅ Comprehensive documentation

### Nice-to-Have (Bonus)
- ✅ Backward compatibility maintained
- ✅ Migration guide provided
- ✅ Performance improvements

## Timeline Summary

| Phase | Duration | Status | Dependencies |
|-------|----------|--------|--------------|
| Phase 1: Data Model Creation | 2-3 hours | Pending | None |
| Phase 2: State Contract Update | 2-3 hours | Pending | Phase 1 |
| Phase 3: Worker Updates | 3-4 hours | Pending | Phase 2 |
| Phase 4: Aggregator Update | 2-3 hours | Pending | Phase 3 |
| Phase 5: Testing & Validation | 3-4 hours | Pending | Phase 4 |
| Phase 6: Documentation Updates | 2-3 hours | Pending | Phase 5 |

**Total Estimated Time:** 2-3 days

## Next Steps

1. **Immediate:** Begin Phase 1 - Data Model Creation
2. **Day 1:** Complete Phases 1-2 (Data models and state contract)
3. **Day 2:** Complete Phases 3-4 (Worker and aggregator updates)
4. **Day 3:** Complete Phases 5-6 (Testing and documentation)

## Resource Requirements

- **Development:** 1 senior developer
- **Testing:** Comprehensive test suite
- **Documentation:** Technical writing skills
- **Tools:** Python 3.14+, Pydantic v2, pytest

## Acceptance Criteria

### Functional Requirements
- ✅ Data structures match Section 4.2 exactly
- ✅ All workers return compliant data
- ✅ Aggregator processes new structures correctly
- ✅ Final brief generation works

### Non-Functional Requirements
- ✅ Performance maintained (<1 second execution)
- ✅ All tests passing (38/38)
- ✅ Code quality maintained
- ✅ Documentation complete

### Compliance Requirements
- ✅ 100% compliance with Problem 1 requirements
- ✅ Demo flow works as specified
- ✅ Evaluation checks pass
- ✅ No breaking changes to UI

## Conclusion

This implementation plan addresses the critical data structure gaps identified in the requirements analysis. By following this phased approach, we can achieve 100% compliance while maintaining code quality and system stability.

**Recommendation:** Proceed with implementation immediately to ensure timely completion before evaluation deadline.

---

*Implementation Plan Version 1.0*  
*Created: May 1, 2026*  
*Status: Ready for Execution*