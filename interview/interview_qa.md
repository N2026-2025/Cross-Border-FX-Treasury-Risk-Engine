# Motor de Tesorería FX - Entrevista Q&A

## Preguntas Técnicas y Respuestas

### Q1: Explique la arquitectura del Motor de Riesgo de Tesorería FX.
**A:** La arquitectura sigue un diseño de tubería modular con clara separación de responsabilidades:

1. **Capa de Ingestión de Datos**: Cinco adaptadores especializados (FRED, Frankfurter, ArgentinaDatos, BCRA, CoinGecko, INDEC) cada uno implementa una interfaz común `BaseAdapter` con un modelo de tasa consistente. Usa lógica de reintento con retroceso exponencial (tenacity) y caché de cliente HTTP.

2. **Capa de Caché**: Caché TTL específico por fuente con degradación graceful. Cada fuente tiene frecuencia de refresco diferente (CoinGecko cada 60s, FRED horario, INDEC diario).

3. **Capa de Normalización**: Las tasas se normalizan a una moneda base común (USD) con precisión Decimal. Cálculos de spread realizados en puntos básicos (bps) para detección de arbitraje.

4. **Capa de Análisis**: Motor de arbitraje compara tasas entre fuentes, genera señales con puntuación de confianza y ahorro esperado en USD.

5. **Capa de Salida**: API REST FastAPI y panel Streamlit para visualización y alertas.

### Q2: ¿Por qué eligió Decimal en lugar de float para cálculos financieros?
**A:** La aritmética de punto flotante causa drift de precisión, lo cual es inaceptable para cálculos financieros donde un error de 0.01 puede representar millones de dólares. Usando `decimal.Decimal` de Python asegura precisión exacta. Quantizamos las tasas a 4 decimales para FX y realizamos todos los cálculos de spread con precisión absoluta.

### Q3: ¿Cómo maneja desacuerdos entre fuentes de tasas?
**A:** El calculador de spread compara tasas entre fuentes. Para USD/ARS, comparamos FRED oficial vs. BCRA oficial vs. ArgentinaDatos blue/financial rates. Las discrepancias se convierten en oportunidades de arbitraje. El sistema soporta señales de compra/venta basadas en qué fuente es más barata.

### Q4: Explique la lógica de arbitraje. ¿Cómo calcula puntos básicos?
**A:** Arbitrage detection compares two rates A and B. Spread in bps = |(RateA - RateB) / RateA| Ã— 10,000. If spread exceeds threshold (default 50 bps), a signal is generated. Direction: if RateA > RateB, BUY at B, SELL at A.

### Q5: ¿Cómo funciona el arbitraje de stablecoins?
**A:** Usamos CoinGecko para rastrear precios USDT/USDC USD. Si la desviación del par $1.00 peg exceeds 100 bps (1%), señalamos riesgo de despegue y excluimos del arbitraje. También cruzamos la liquidez de stablecoin con reservas del BCRA para decisiones de enrutamiento del tesoro.

### Q6: ¿Cómo ajusta por inflación en cálculos FX?
**A:** Usando la ecuación de Fisher: Real = (1 + Nominal) / (1 + Inflation) - 1. Aplicamos ajustes de inflación mensuales usando datos CPI INDEC para calcular exposición real USD ajustada por inflación.

### Q7: ¿Cuáles son los diferentes tipos de tasas y cómo las maneja?
**A:** Los tipos de tasa incluyen OFICIAL, FINANCIAL, BLUE, MID_MARKET, y SPOT. Para Argentina, distinguimos entre oficial (BCRA), blue (mercado paralelo), y financial (MEP/CCL). Cada uno tiene diferentes implicaciones de liquidez para decisiones del tesoro.

### Q8: ¿Cómo escalar este motor a Brasil o México?
**A:** La arquitectura ya es multi-divisa. Agregamos fuentes: BCB (Brasil), Banxico (México), y extendemos el registro de adaptadores. La lógica de arbitraje es agnóstica a divisa ya que opera en pares de tasas.

### Q9: ¿Cómo maneja los límites de API?
**A:** Cada adaptador respeta límites de fuente específicos y almacena en caché respuestas con TTL basado en frecuencia de fuente. Los reintentos usan retroceso exponencial mediante la librería tenacity.

### Q10: ¿Cuál es el umbral de impacto financiero para una señal de arbitraje?
**A:** Establecemos umbral default en 50 bps. Para un tesoro de $1M USD, una oportunidad de 50 bps equivale a $5,000 de ahorro por ciclo de conversión. Señales con confianza > 0.5 se muestran para acción.

## Pregunta de Arquitectura

### Q11: Paseo por cómo diseñaría un sistema para 10 divisas.
**A:** Yo:
1. Diseñaría una tabla de pares de divisa con todas las combinaciones
2. Usaría keying basado hash para eficiencia de caché
3. Implementaría funciones de conversión cruzada
4. Crearía matriz de arbitraje unificada
5. Generaría recomendaciones de cobertura a nivel de portafolio

### Q12: ¿Cómo prueba la lógica financiera?
**A:** Usamos Decimal en pruebas, probamos comportamiento de redondeo, probamos redondeo banker's vs. round-half-up, y validamos cálculos de spread contra benchmarks históricos.

## Preguntas de Patrones de Diseño

### Q13: ¿Qué patrones de diseño utilizó y por qué?
**A:**
- **Patrón Adapter**: Para abstracción de fuentes API
- **Patrón Strategy**: Para algoritmos de arbitraje (pluggable)
- **Patrón Circuit Breaker**: Para manejo graceful de fallos de API
- **Patrón Factory**: Para instantiation de adaptador basado en config

## Pregunta de Rendimiento

### Q14: ¿Cómo asegura la frescura de datos?
**A:** TTLs específicos por fuente (CoinGecko 60s, FRED 3600s, BCRA 900s, INDEC 86400s), invalidación de caché en expiry TTL, y patrón stale-while-revalidate para resiliencia.

### Q15: ¿Cómo monitoriza el sistema?
**A:** Registro estructurado (structlog), health checks por fuente, historial de señales, y puntuación de confianza en todas las señales de arbitraje.

---

## Referencia Rápida para Entrevistas

### El Pitch de 30 Segundos:
> "I built a tubería multi-divisa integrating tasas de Fed, datos FX del ECB, and APIs de bancos centrales emergentes to track exposición FX en tiempo real and erosión por inflaciónâ€”ayudando a equipos de finanzas globales proteger márgenes y optimizar liquidez transfronteriza."

### Preguntas Profundas Técnicas:

**"Paseo por su pipeline de datos":** Ingestion â†’ Normalization â†’ Analysis â†’ Output

**"¿Cómo maneja la precisión?":** Tipo Decimal, cuantización a 4dp para FX.

**"¿Cómo detecta arbitraje?":** Spread en bps entre fuentes, señales basadas en umbral.

**"¿Cómo ajusta por inflación?**:** Ecuación de Fisher con datos CPI.

**"¿Qué tan escalable es?:** Registro de adaptadores facilita la incorporación de nuevos mercados.

---

*Este documento acompaña al proyecto Cross-Border FX & Treasury Risk Engine en el directorio plans/.*
