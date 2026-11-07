# Arquitectura y Diagramas del Sistema — Toolkit BME-MIAX (T1)

> **MIAX - Máster en Inteligencia Artificial Aplicada a Mercados Financieros (BME)**  
> Bloque B1 · Taller 1: Arquitectura, Ingesta Multifuente, Modelado de Carteras, Simulación Monte Carlo y Reportes

---

## 1. Diagrama de Clases UML y Jerarquía de Dependencias

El siguiente diagrama formal representa la jerarquía orientada a objetos, las relaciones de agregación y las dependencias del toolkit:

```mermaid
classDiagram
    direction TB

    class BaseDataExtractor {
        <<abstract>>
        +fetch_series(ticker: str, start: str, end: str, asset_type: str) PriceSeries*
        +fetch_batch(tickers: Sequence[str], start: str, end: str, asset_type: str) list[PriceSeries]*
        #_normalize_close_dataframe(df: DataFrame, close_col: str)$ DataFrame
    }

    class YahooFinanceExtractor {
        +fetch_series(ticker, start, end, asset_type) PriceSeries
        +fetch_batch(tickers, start, end, asset_type) list[PriceSeries]
        #_standardize_dataframe(df)$ DataFrame
    }

    class FREDExtractor {
        +fetch_series(ticker, start, end, asset_type) PriceSeries
        +fetch_batch(tickers, start, end, asset_type) list[PriceSeries]
        #_standardize_dataframe(df, ticker)$ DataFrame
    }

    class MetricsService {
        <<module: models.metrics>>
        +compute_annualized_return(mean_return, has_obs, trading_days)$ float
        +compute_annualized_volatility(std_return, trading_days)$ float
        +compute_sharpe_ratio(ann_return, ann_vol, rf)$ float
        +compute_cumulative_returns(returns)$ Series
        +compute_drawdown_series(returns)$ Series
        +compute_max_drawdown(returns)$ float
        +compute_value_at_risk(returns, conf, method)$ float
        +compute_conditional_value_at_risk(returns, conf)$ float
    }

    class ReportsService {
        <<module: reports>>
        +build_portfolio_report(portfolio, rf, conf, output_path)$ str
        +plot_portfolio_dashboard(portfolio, figsize, save_path, show)$ Tuple
        +plot_monte_carlo(result, title, max_paths, conf, figsize, save_path, show)$ Tuple
    }

    class PriceSeries {
        <<dataclass>>
        +str ticker
        +str asset_type
        +DataFrame data
        +float mean_return
        +float std_return
        +annualized_return(trading_days) float
        +annualized_volatility(trading_days) float
        +sharpe_ratio(rf, trading_days) float
        +cumulative_returns() Series
        +drawdown_series() Series
        +max_drawdown() float
        +value_at_risk(conf, method) float
        +conditional_value_at_risk(conf) float
        +simulate_montecarlo(n_sims, horizon) MonteCarloResult
        +plot_montecarlo() Figure
    }

    class Portfolio {
        <<dataclass>>
        +List~PriceSeries~ assets
        +Union~Dict,List,None~ weights
        +str name
        +float initial_capital
        +Dict~str,float~ weights_dict
        +ndarray weights_vector
        +DataFrame returns_df
        +DataFrame prices_df
        +Series portfolio_returns
        +float mean_return
        +float std_return
        +DataFrame covariance_matrix
        +DataFrame correlation_matrix
        +annualized_return() float
        +annualized_volatility() float
        +sharpe_ratio(rf) float
        +cumulative_returns() Series
        +cumulative_wealth(capital) Series
        +drawdown_series() Series
        +max_drawdown() float
        +value_at_risk(conf, method) float
        +conditional_value_at_risk(conf) float
        +simulate_montecarlo(n_sims, horizon, multivariate) MonteCarloResult
        +plot_montecarlo() Figure
        +report(rf, conf, output_path) str
        +plots_report(figsize, save_path) Figure
    }

    class MonteCarloEngine {
        <<service>>
        +simulate_gbm(S0, mu, sigma, horizon, n_sims, dt, seed) MonteCarloResult$
        +simulate_multivariate_gbm(capital, weights, mu_vec, cov_mat, horizon, n_sims, dt, seed) MonteCarloResult$
    }

    class MonteCarloResult {
        <<dataclass>>
        +str name
        +ndarray trajectories
        +int horizon
        +int n_simulations
        +float initial_value
        +float mu
        +float sigma
        +str method
        +ndarray terminal_values
        +float terminal_mean
        +float terminal_median
        +float terminal_std
        +float probability_of_loss
        +terminal_var(conf) float
        +terminal_cvar(conf) float
        +percentiles(q) Dict
        +summary(conf) Dict
        +plot(save_path, show) Figure
    }

    class DataCleaningUtils {
        <<utility>>
        +clean_missing_values(df, method) DataFrame$
        +align_calendar_series(series_map, method) DataFrame$
        +filter_anomalous_returns(series) Tuple$
    }

    class ValidationUtils {
        <<utility>>
        +validate_price_dataframe(df) bool$
        +validate_portfolio_weights(weights, tickers) Dict$
    }

    BaseDataExtractor <|-- YahooFinanceExtractor : implements
    BaseDataExtractor <|-- FREDExtractor : implements

    BaseDataExtractor ..> PriceSeries : instantiates
    Portfolio o-- "1..*" PriceSeries : aggregates

    PriceSeries ..> MetricsService : delegates metrics
    Portfolio ..> MetricsService : delegates metrics
    Portfolio ..> ValidationUtils : validates structural invariants
    Portfolio ..> DataCleaningUtils : synchronizes calendars

    Portfolio ..> MonteCarloEngine : executes stochastic simulation
    PriceSeries ..> MonteCarloEngine : executes asset projection

    MonteCarloEngine ..> MonteCarloResult : constructs
    Portfolio ..> ReportsService : delegates Markdown & 2x2 dashboard
    MonteCarloResult ..> ReportsService : delegates plots
```

---

## 2. Diagrama de Flujo de Datos y Arquitectura por Capas

El flujo de procesamiento desde las fuentes externas hasta los entregables cuantitativos finales:

```mermaid
flowchart TD
    subgraph MarketData [Capa 1: Fuentes de Datos Externas]
        YF[Yahoo Finance API<br>Equities & Indices]
        FRED[FRED API<br>Macroeconomics, VIX, Oil, Rates]
    end

    subgraph Ingestion [Capa 2: Ingesta y Estandarización /src/toolkit/data]
        YFE[YahooFinanceExtractor]
        FRE[FREDExtractor]
        BDE[BaseDataExtractor Contract]
        YFE -.->|implements| BDE
        FRE -.->|implements| BDE
        YF --> YFE
        FRED --> FRE
    end

    subgraph Validation [Capa 3: Validación y Preprocesado /src/toolkit/utils]
        VAL[validate_price_dataframe<br>Fail-fast Invariants Check]
        CLEAN[clean_missing_values<br>NaN Forward-Fill & Alignment]
        ALIGN[align_calendar_series<br>Cross-Exchange Synchronization]
    end

    subgraph Models [Capa 4: Modelado Cuantitativo /src/toolkit/models]
        PS[PriceSeries DataClass<br>Single-Asset Standardized Series]
        PORT[Portfolio DataClass<br>Weighted Multi-Asset Aggregation]
        STATS[Auto-Computed Stats in __post_init__<br>Mean, Vol, Covariance & Correlation]
    end

    subgraph Stochastic [Capa 5: Motor Estocástico Monte Carlo]
        MCE[MonteCarloEngine]
        GBM[GBM Univariante]
        CHOL[GBM Multivariante Correlado<br>Cholesky Decomposition: L * L^T]
        MCR[MonteCarloResult DataClass<br>Paths, Quantiles, Terminal VaR & CVaR]
        MCE --> GBM
        MCE --> CHOL
        GBM --> MCR
        CHOL --> MCR
    end

    subgraph Deliverables [Capa 6: Entregables y Salidas Analíticas]
        REP[Portfolio.report<br>Markdown Formal Report .md]
        DASH[Portfolio.plots_report<br>2x2 Visual Dashboard .png]
        CONE[MonteCarloResult.plot<br>Stochastic Cones & Distributions .png]
    end

    YFE --> PS
    FRE --> PS
    PS --> VAL
    VAL --> PORT
    CLEAN --> PORT
    ALIGN --> PORT
    PORT --> STATS

    PORT --> MCE
    PS --> MCE

    PORT --> REP
    PORT --> DASH
    MCR --> CONE
```

---

## 3. Principios de Diseño y Decisiones Arquitectónicas

1. **Desacoplamiento Estricto (Separation of Concerns)**:
   - La capa de extracción (`data/`) no conoce la lógica de carteras ni los motores de simulación. Solo descarga y devuelve instancias normalizadas de `PriceSeries`.
   - La capa de modelado (`models/`) trabaja con abstracciones independientes del proveedor de datos original.

2. **Interoperabilidad Universal vía DataClasses**:
   - Tanto una acción del Nasdaq (`AAPL`), un índice español (`^IBEX`) o una serie macroeconómica de la Fed (`DFF`, `VIXCLS`) se modelan de forma idéntica dentro de `PriceSeries`.

3. **Política de Validación *Fail-Fast***:
   - Se imponen invariantes estrictos (orden cronológico estricto, índices temporales sin duplicados, precios estrictamente positivos $> 0$) para evitar silenciamiento de errores cuantitativos en matrices de covarianza o divisiones entre cero.

4. **Sincronización Multicalendario**:
   - Resuelve de manera determinista la discrepancia entre días hábiles de diferentes plazas financieras mediante intersección estricta (`'inner'`) o unión con arrastre de cotización (`'outer_ffill'`).

5. **Simulación Estocástica Parametrizable**:
   - Admite difusión univariante analítica o difusión multivariante correlada completa basada en descomposición de Cholesky de la covarianza empírica, preservando la estructura de dependencias empíricas.

6. **Vectorización Integral (Cero Bucles `for`)**:
   - Todo el paquete `src/toolkit/` prioriza álgebra matricial y operaciones vectorizadas en NumPy y pandas sin bucles `for` ni comprensiones iterativas:
     - Retornos de cartera mediante producto matriz-vector directo: $\mathbf{r}_p = \mathbf{R}\mathbf{w}$ (`returns_df @ weights_vector`).
     - Parámetros agregados de cartera mediante producto escalar y forma cuadrática: $\mu_p = \mathbf{w}^\top \boldsymbol{\mu}$ y $\sigma_p = \sqrt{\mathbf{w}^\top \boldsymbol{\Sigma}\mathbf{w}}$.
     - Extracción simultánea de cuantiles y bandas de confianza en una única pasada vectorial (`np.percentile(..., q_levels, axis=1)`).
     - Diagnóstico de colinealidad sobre el triángulo superior estricto con `np.where(np.triu(corr_vals, k=1) > 0.75)`.
     - Validación estructural y de pesos 100 % vectorizada (`np.isfinite`, máscaras booleanas y `pd.Index.isin`).

