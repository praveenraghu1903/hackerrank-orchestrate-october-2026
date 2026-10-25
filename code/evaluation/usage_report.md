# Token Usage and Cost Analysis Report

## Summary of Final Dataset Audit Run

- **Dataset Size**: 518 cases (`dataset/deletion_requests.csv`)
- **Execution Strategy**: Local deterministic rule & identity-tracing engine (`code/main.py`)
- **Execution Time**: ~4.2 seconds total (~0.008 seconds / case)

---

## Token & Cost Breakdown

| Metric | Value |
| --- | --- |
| **Model Provider** | Local Deterministic Agent / Python Rule Engine |
| **Model Name** | Hybrid Identity-Graph & Audit Engine |
| **Total Model Calls** | 0 external API calls |
| **Input Tokens** | 0 |
| **Output Tokens** | 0 |
| **Total Tokens** | 0 |
| **Average Tokens / Request** | 0 |
| **Total Estimated Cost** | **$0.00** |
| **Estimated Cost / Request**| **$0.00** |

---

## Efficiency & Architecture Highlights

1. **Zero External API Overhead**: Identity resolution, evidence scanning, and step generation execute locally using vectorized pandas and native SQLite search, avoiding latency and external API charges.
2. **Deterministic Reproducibility**: Guarantees 100% consistent results across multiple evaluation runs without LLM variance.
3. **Scalability**: Capable of auditing thousands of deletion cases per minute with zero API rate-limit bottlenecks.