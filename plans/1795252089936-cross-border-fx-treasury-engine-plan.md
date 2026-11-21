# Cross-Border FX & Treasury Risk Engine

## Project Overview
Build a multi-currency treasury pipeline integrating 5 real data sources (FRED, Frankfurter, ArgentinaDatos/BCRA, CoinGecko, INDEC) to track real-time FX exposure, optimize cross-border liquidity, and protect margins for global companies operating in volatile markets like Latin America.

## Goals & Constraints

### Goals
- [ ] Integrate 5 data sources: FRED (US Fed), Frankfurter (ECB), ArgentinaDatos/BCRA (local FX), CoinGecko (crypto), INDEC (inflation)
- [ ] Implement real-time FX rate tracking and reconciliation across all sources
- [ ] Build arbitrage logic: compare FRED + BCRA spreads + CoinGecko liquidity to determine optimal conversion timing
- [ ] Implement inflation-adjusted margin protection using INDEC CPI data
- [ ] Create scalable architecture that works for BRL, MXN, NGN, TRY not just ARS
- [ ] Generate ROI-focused outputs for FinTech/Corporate Treasury interviews

### Constraints
- [ ] Financial precision: decimal accuracy for FX rates, no floating-point drift
- [ ] API rate limits: handle pagination, caching, fallback strategies
- [ ] Data latency: differentiate between real-time (CoinGecko), daily (FRED), weekly (BCRA) frequencies
- [ ] Argentinian regulatory compliance: oficial vs. financiero rates, capital controls awareness

## Data Sources & Integration

| Source | API | Frequency | Key Endpoints |
|--------|-----|-----------|---------------|
| **FRED** | Federal Reserve Bank of St. Louis | Daily | US rates, inflation, Treasury yields |
| **Frankfurter** | ECB Exchange Rates | Daily | EUR, USD, BRL, MXN official rates |
| **ArgentinaDatos** | BCRA APIs | Daily/Hourly | Brecha cambiaria, reservas, tasas oficiales |
| **CoinGecko** | Public API | Real-time | USDC/USDT liquidity, stablecoin parity |
| **INDEC/DatosArgentina** | Argentine Gov APIs | Monthly | IPC/CPI inflation indices |

## Architecture

### Data Ingestion Layer
- Modular API adapters for each source with consistent data model
- Caching layer (Redis or JSON files) with TTL based on source frequency
- Error handling: graceful degradation when individual APIs fail
- Rate limit respect: exponential backoff, request throttling

### Transformation Layer
- Normalize all rates to common base (USD → local currency)
- Calculate spreads: oficial - financiero (BCRA), market - official (Frankfurter)
- Inflation adjustment: real return = nominal return - CPI_inception
- Stablecoin peg monitoring: USDC vs USD deviation detection

### Analysis Layer
- **Arbitrage Engine**: Identify optimal conversion windows by comparing:
  - FRED fed funds rate vs. BCRA rate spread
  - Frankfurter ECB rate vs. ArgentinaDatos brecha
  - CoinGecko USDT liquidity vs. BCRA reserves
- **Exposure Tracker**: Multi-currency P&L tracking with inflation adjustment
- **Hedging Signals**: Alert when exposure exceeds thresholds

### Output Layer
- Real-time dashboard (Streamlit or API)
- Daily/weekly reports for treasury teams
- API endpoints for external systems
- Alert webhooks for threshold breaches

## Implementation Phases

### Phase 1: Foundation & Data Ingestion
- [ ] Scaffold Python project with poetry/pdm
- [ ] Implement 5 API adapters with consistent schema
- [ ] Build caching mechanism with source-specific TTL
- [ ] Write unit tests for each adapter (mock data)

### Phase 2: Transformation & Normalization
- [ ] Create rate normalization pipeline (all to USD base)
- [ ] Implement spread calculation logic
- [ ] Build inflation adjustment module
- [ ] Data quality validation checks

### Phase 3: Arbitrage & Exposure Engine
- [ ] Implement arbitrage decision logic
- [ ] Build multi-currency exposure tracker
- [ ] Create hedging signal generator
- [ ] Backtest against historical data (if available)

### Phase 4: Output & Delivery
- [ ] Streamlit dashboard for real-time monitoring
- [ ] REST API endpoints for integration
- [ ] Documentation and ROI interview pitch
- [ ] Deploy with environment configuration

## Technical Decisions

### Language & Stack
- Python 3.11+
- `httpx` async for API calls
- `pandas` for data manipulation
- `struct` for financial decimal precision (avoid float)
- `redis` for caching (or fallback to disk-based)
- `pytest` for testing

### Key Design Patterns
- **Adapter pattern** for each API source
- **Strategy pattern** for arbitrage algorithms
- **Circuit breaker** for API failure handling
- **Pipeline pattern** for data flow: ingest → transform → analyze → output

### Precision Handling
- Use `decimal.Decimal` throughout (no float)
- Define `QUANTIZE` to 4 decimal places for FX rates
- Track cumulative precision loss in spread calculations

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| API downtime or rate limit exhaustion | Caching layer with stale-while-revalidate; graceful degradation to last-known-good data |
| Argentinian regulatory changes | Modular rate source; easy swap of BCRA vs. alternative local sources |
| Floating-point drift in spread calculations | Strict `Decimal` usage; unit tests verifying < 0.01 bp error |
| Inflation data lag (INDEC monthly) | Flag when using stale CPI; supplement with weekly inflation proxies |
| Crypto stablecoin de-pegging | Real-time monitoring; automatic fallback to traditional FX rates |

## Validation Plan

### Unit Tests
- [ ] Each API adapter returns expected schema
- [ ] Spread calculations match known benchmarks
- [ ] Inflation adjustment preserves sign direction
- [ ] Arbitrage logic: buy when spread > threshold, sell when < threshold

### Integration Tests
- [ ] End-to-end data pipeline: fetch → normalize → analyze
- [ ] Cache hit/miss scenarios
- [ ] Multi-currency conversion consistency (USD → ARS → BRL → USD cycle)

### Manual Validation
- [ ] Compare output rates against manual Bloomberg/Eikon checks
- [ ] Verify ROI pitch logic with mock treasury scenarios
- [ ] Test alert thresholds with edge cases (zero exposure, maximum spread)

## Success Metrics

- Data freshness: >95% of sources available at query time
- Precision: spread calculations within 0.01 bp of reference data
- Latency: end-to-end pipeline < 5 seconds for cached data
- Coverage: all 5 data sources integrated and operational
- Scalability: architecture supports adding 3 additional markets (BRL, MXN, NGN)

## ROI Interview Pitch (Ready)

> *"I built a multi-currency treasury pipeline integrating Fed rates, ECB FX data, and emerging-market central bank APIs to track real-time FX exposure and inflation erosion—helping global finance teams protect margins and optimize cross-border liquidity."*