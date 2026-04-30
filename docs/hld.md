# MarketPulse High-Level Design

## Objective

MarketPulse produces a competitive market brief from reliable CSV input. The MVP prioritizes mandatory rubric coverage: typed state, graph orchestration, parallel worker execution, aggregation, final markdown output, and visible node I/O logs.

## Runtime Flow

1. Streamlit collects CSV path, product, competitors, business question, and feature flags.
2. The data layer validates and normalizes CSV rows into `MarketRecord` objects.
3. `MarketPulseWorkflow` compiles a LangGraph `StateGraph` when available.
4. The supervisor selects workers using explicit edge rules.
5. Pricing, demand, and reviews workers run in parallel. Social listening joins only when enabled.
6. The aggregator merges worker outputs into risks, opportunities, and recommended actions.
7. The brief writer uses Gemini when configured, otherwise deterministic local markdown.
8. The UI renders final output, worker tabs, dispatch reasoning, acceptance checks, and node logs.

## State Contract

Primary contract: `MarketPulseState`.

- `question`: evaluator business question.
- `competitors`: selected competitors.
- `records`: normalized CSV records.
- `feature_flags`: bonus gates for social, pricing delta, and scheduler.
- `supervisor_decision`: selected and skipped workers.
- `worker_outputs`: worker result map.
- `aggregated`: merged insight object.
- `final_brief`: final markdown.
- `logs`: node-level event trail.

## Conditional Edge Rules

- `pricing`: runs when selected records contain price data.
- `demand`: runs when selected records contain traffic index data.
- `reviews`: runs when selected records contain review score data.
- `social`: runs only when `enable_social_worker` is true.

## Reliability Position

CSV is the source of truth for demo reliability. Live data sources and scheduler behavior remain behind feature flags, so bonus work cannot destabilize the required flow.
