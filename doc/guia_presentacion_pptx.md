
## ⏱️ 1. Estructura de Tiempos y Reparto (5:00 min · 3 Ponentes)

| Tramo | Tiempo | Diapositivas | Responsable sugerido | Foco principal |
| :--- | :---: | :---: | :---: | :--- |
| **Bloque 1: Arquitectura e Ingesta** | `0:00 – 1:40` *(1m 40s)* | **Slides 1, 2 y 3** | **Ponente 1** | Visión de conjunto, desacoplamiento por capas, conectores multifuente (`Yahoo` + `FRED`) y validación *fail-fast*. |
| **Bloque 2: Paradigma OOP y Motor Cuantitativo** | `1:40 – 3:30` *(1m 50s)* | **Slides 4, 5 y 6** | **Ponente 2** | `DataClasses` (`PriceSeries`, `Portfolio`), vectorización 100 % matricial (cero bucles `for`), métricas de riesgo y Monte Carlo (Cholesky). |
| **Bloque 3: Reportes, DevOps y Cierre** | `3:30 – 5:00` *(1m 30s)* | **Slides 7, 8 y 9** | **Ponente 3** | Separación dominio/presentación (`.report()` Markdown + Dashboard 2x2 `.plots_report()`), GitFlow, suite de 19 tests offline y cierre. |

---

## 🎤 2. Guion Diapositiva por Diapositiva (`Taller_1_B1_Toolbox_Financiera.pptx`)

### **Slide 1 — Portada: Toolbox Financiera Institucional** *(0:00 – 0:20)*
- **Mensaje clave:** Presentar al equipo y el objetivo del proyecto: transformar scripts financieros aislados en un paquete Python instalable (`src-layout` con [`pyproject.toml`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/pyproject.toml)), modular y extensible.
- **Frase de apertura:**
  > *"Buenas tardes. Presentamos nuestra Toolbox Financiera para el Taller B1-T1: una librería en Python diseñada bajo principios de ingeniería de software institucional para la ingesta multifuente, gestión cuantitativa de carteras, simulación de Monte Carlo y generación automatizada de reportes."*

---

### **Slide 2 — Blueprint Arquitectónico: El Ciclo de Vida del Dato** *(0:20 – 0:55)*
- **Qué señalar en la slide:** Los 4 cubos del pipeline (`Ingesta y Limpieza` $\rightarrow$ `Núcleo OOP` $\rightarrow$ `Motor Analítico` $\rightarrow$ `Output Automatizado`).
- **Puntos clave a explicar:**
  - **Desacoplamiento estricto (*Separation of Concerns*)**: [`data/`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/data) no conoce qué es una cartera ni Monte Carlo; [`models/`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/models) es agnóstico al proveedor de datos; y [`reports.py`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/reports.py) aísla toda la capa visual y de informes.
  - Si mañana añadimos Bloomberg o SIX Market Signal, el núcleo cuantitativo no cambia ni una línea.

---

### **Slide 3 — Fase 1: Motor de Ingesta y Normalización Absoluta** *(0:55 – 1:40)*
- **Qué señalar en la slide:** El embudo (*Data Funnel*) que convierte múltiples fuentes heterogéneas en una estructura tabular canónica.
- **Puntos clave a explicar (Requisitos 4.2 y 4.5):**
  1. **Contrato abstracto [`BaseDataExtractor`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/data/base.py#L14)**: implementado por [`YahooFinanceExtractor`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/data/yahoo.py#L18) (acciones e índices como `AAPL`, `SAN.MC`, `^IBEX`, soportando descargas individuales y *batch* `MultiIndex`) y [`FREDExtractor`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/data/fred.py#L50) (series macro como tipos Fed `DFF`, `VIXCLS` y petróleo `DCOILWTICO`, con *fallback* automático a `fredgraph.csv`).
  2. **Política de validación estricta *Fail-Fast* ([`validation.py`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/utils/validation.py#L30))**: rechazamos precios $\le 0$, `NaN`/`inf`, fechas desordenadas o duplicadas antes de que corrompan las matrices de covarianza.
  3. **Sincronización multicalendario sin *look-ahead bias* ([`cleaning.py`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/utils/cleaning.py#L12))**: alineación entre NYSE y BME (`inner` u `outer_ffill` acotado por `max_consecutive_nans`), descartando huecos iniciales sin usar `bfill` para no filtrar precios del futuro.

---

### **Slide 4 — Decisión Arquitectónica: El Paradigma OOP** *(1:40 – 2:10)*
- **Qué señalar en la slide:** La comparativa *Scripts Secuenciales (B0)* vs. *Diseño Orientado a Objetos (B1)* y los tres pilares: **Encapsulamiento, Modularidad y Abstracción**.
- **Puntos clave a explicar:**
  - En lugar de pasar `DataFrames` sueltos que pueden mutarse accidentalmente, cada activo y cada cartera encapsulan su propio estado validado e invariantes.
  - Un fallo o anomalía en un activo individual se detecta en su construcción sin corromper la cartera global.

---

### **Slide 5 — Fase 2: Implementación del Núcleo Modular** *(2:10 – 2:50)*
- **Qué señalar en la slide:** Relación de agregación `Class Series` ([`PriceSeries`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/models/series.py#L20)) $\rightarrow$ `Class Portfolio` ([`Portfolio`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/models/portfolio.py#L29)).
- **Puntos clave a explicar (Requisito 4.3):**
  - Ambas clases son `@dataclass` que calculan automáticamente sus estadísticos fundamentales (`mean_return`, `std_return`, matrices de covarianza y correlación) en `__post_init__`.
  - Implementan los métodos especiales del estándar de Python (`__len__`, `__getitem__` por ticker `portfolio["AAPL"]`, `__str__`, `__repr__`).
  - **Matiz de valor añadido sobre la slide:** *"Aunque inicialmente partimos de comprensiones de listas, evolucionamos el código a **vectorización integral con NumPy y Pandas (cero bucles `for` en todo `src/toolkit/`)**: los retornos de cartera se calculan mediante producto matriz-vector directo $\mathbf{r}_p = \mathbf{R}\mathbf{w}$ (`returns_df @ weights_vector`)."*

---

### **Slide 6 — Fase 3: Motor Analítico y Gestión de Riesgo** *(2:50 – 3:30)*
- **Qué señalar en la slide:** Las 3 ramas que salen del procesador central (Volatilidad/Covarianzas, VaR/Tail Risk y Simulación de Monte Carlo).
- **Puntos clave a explicar (Requisitos 4.3 y 4.4):**
  - **Rama 1 y 2 ([`metrics.py`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/models/metrics.py))**: Módulo de funciones puras compartidas entre `PriceSeries` y `Portfolio` para rentabilidad anualizada geométrica, volatilidad, ratio de Sharpe, *Max Drawdown* (incluyendo pico inicial de riqueza), **VaR** (histórico y paramétrico gaussiano con `NormalDist`) y **CVaR / Expected Shortfall**.
  - **Rama 3 ([`monte_carlo.py`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/models/monte_carlo.py#L195))**: Motor 100 % vectorizado en tensores 3D `(horizon, n_assets, n_simulations)` con dos modos:
    1. **GBM Univariante** para activos individuales o cartera agregada.
    2. **GBM Multivariante Correlado** mediante descomposición de **Cholesky** ($\boldsymbol{\Sigma} = \mathbf{L}\mathbf{L}^\top$) sobre la covarianza empírica (con factorización por autovalores `np.linalg.eigh` cuando la matriz es singular semidefinida positiva).

---

### **Slide 7 — Fase 4: Automatización de Output** *(3:30 – 4:05)*
- **Qué señalar en la slide:** El flujo `Pipeline Analítico` $\rightarrow$ `Renderizado automático` $\rightarrow$ `Reportes`.
- **Puntos clave a explicar (Requisito 4.5):**
  - **Informe Ejecutivo en Markdown (`portfolio.report()`)**: genera tablas de métricas, atribución por activo, matriz de correlaciones y **alertas automáticas de riesgo 100 % vectorizadas** (concentración $>40\%$, colinealidad en el triángulo superior `np.triu(corr, k=1) > 0.75` y *drawdown* $>20\%$).
  - **Cuadro de Mando Visual 2x2 (`portfolio.plots_report()`)**: exporta en alta resolución la riqueza acumulada comparada, *Underwater Drawdown*, *heatmap* de correlaciones e histograma de retornos con cortes de VaR/CVaR, además de los conos estocásticos de Monte Carlo (`mc.plot()`).
  - **Documentación técnica compilada en HTML y PDF**: 5 guías paso a paso en [`doc/`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/doc).

---

### **Slide 8 — Metodología y Trazabilidad DevOps (Git)** *(4:05 – 4:35)*
- **Qué señalar en la slide:** El grafo de ramas (*Feature Branches* $\rightarrow$ `develop` $\rightarrow$ `main`).
- **Puntos clave a explicar (Requisito 4.1):**
  - Trabajo colaborativo mediante ramas temáticas (`feature/T1`, `feature/T1_doc`, `develop`, `main`) y *Pull Requests* revisadas.
  - **Suite de 19 tests unitarios *offline* ([`tests/test_toolkit.py`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/tests/test_toolkit.py))**: verifica invariantes, limpieza sin *look-ahead bias*, matrices singulares en Monte Carlo, *mocks* de FRED/Yahoo y generación de reportes en $< 2\text{ s}$ sin depender de conexión a internet.

---

### **Slide 9 — Auditoría de Entregables (Arquitectura T1)** *(4:35 – 5:00)*
- **Qué señalar en la slide:** El *checklist* completo de los 6 bloques del enunciado (4.1 a 4.6).
- **Frase de cierre:**
  > *"En conclusión, hemos construido una toolbox plug-and-play, 100 % vectorizada, validada con 19 tests unitarios offline y documentada con diagramas UML/Mermaid y guías PDF, lista para escalar en los siguientes bloques del máster. Muchas gracias y quedamos a su disposición para cualquier pregunta."*

---

## 💻 3. Comandos Listos por si Piden Demo en Vivo (30 s)

Si durante las preguntas os piden enseñar el código corriendo en terminal, tened abierta una terminal en [`Taller-T1-B1`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1) con estos dos comandos preparados:

1. **Lanzar los 19 tests unitarios offline (tarda 1,8 segundos y no depende del Wi-Fi del aula):**
   ```bash
   python -m unittest discover -s tests -v
   ```
2. **Mostrar los gráficos ya generados en [`examples/plots/`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/examples/plots) y el reporte en [`examples/reports/portfolio_report.md`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/examples/reports/portfolio_report.md)**, o lanzar el pipeline completo de reportes y limpieza:
   ```bash
   python examples/test_reports_and_cleaning.py
   ```

---

## ❓ 4. Posibles Preguntas del Tribunal (Respuestas Rápidas)

1. ***"¿Por qué habéis impuesto una validación tan estricta en `PriceSeries` y `Portfolio` en lugar de aceptar cualquier DataFrame?"***
   - **Respuesta:** Porque en finanzas cuantitativas un precio cero o negativo, un `NaN` intermedio o una fecha duplicada corrompen silenciosamente los retornos, hacen singular la matriz de covarianzas en Cholesky y distorsionan el Sharpe. Preferimos una política *fail-fast* en [`validation.py`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/utils/validation.py) con mensajes de diagnóstico explícitos.
2. ***"¿Cómo habéis resuelto el problema de distintos calendarios festivos (p. ej. EE. UU. vs. España)?"***
   - **Respuesta:** En [`Portfolio._align_data`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/models/portfolio.py#L99-L112) primero alineamos los precios de cierre sobre las fechas comunes (`align_calendar_series`) y después calculamos `pct_change(fill_method=None)` sobre intervalos temporales idénticos; además, en `clean_missing_values` eliminamos el *backward-fill* para evitar *look-ahead bias*.
3. ***"¿Qué ocurre en el Monte Carlo multivariante si dos activos son colineales y la matriz de covarianzas no es definida positiva?"***
   - **Respuesta:** [`MonteCarloEngine.simulate_multivariate_gbm`](file:///home/sergio/Documents/Master_MIAX_BME/Talleres_Master_MIAX_BME/Taller-T1-B1/src/toolkit/models/monte_carlo.py#L287-L303) comprueba la simetría y los autovalores con `np.linalg.eigh`: si es definida positiva usa Cholesky ($\mathbf{L}\mathbf{L}^\top$), y si es semidefinida positiva singular usa factorización espectral ($\mathbf{V}\sqrt{\max(\boldsymbol{\Lambda}, 0)}$), todo testado en `test_multivariate_gbm_preserves_singular_covariance`.
