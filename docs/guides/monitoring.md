# Monitoring

---
tags:
  - #guide
  - #runtime
---

Set up observability for xnch + Nexi.

## Metrics

### Built-in Metrics

xnch exposes Prometheus metrics:

```yaml
metrics:
  enabled: true
  port: 9090
  path: /metrics
```

### Available Metrics

#### Execution Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `xnch_executions_total` | Counter | Total executions |
| `xnch_execution_duration_seconds` | Histogram | Execution duration |
| `xnch_execution_success_total` | Counter | Successful executions |
| `xnch_execution_failure_total` | Counter | Failed executions |

#### Nexi Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `xnch_nexi_candidates_generated` | Histogram | Candidates per execution |
| `xnch_nexi_candidates_filtered` | Histogram | Candidates filtered by policy |
| `xnch_nexi_evaluation_duration_ms` | Histogram | Evaluation time |
| `xnch_nexi_decision_total` | Counter | Decisions made |

#### Memory Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `xnch_memory_context_stored` | Counter | Contexts stored |
| `xnch_memory_outcome_recorded` | Counter | Outcomes recorded |
| `xnch_memory_vector_query_duration_ms` | Histogram | Vector search latency |

#### Learning Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `xnch_learning_episodes_recorded` | Counter | Episodes recorded |
| `xnch_learning_patterns_extracted` | Counter | Patterns extracted |
| `xnch_learning_score_adaptations` | Counter | Score adaptations |

## Logging

### Configuration

```yaml
logging:
  level: INFO
  format: json  # or "text"
  
  handlers:
    console:
      enabled: true
      level: INFO
      
    file:
      enabled: true
      path: ~/.xnch/logs/xnch.log
      rotation: daily
      retention: 7
      
    syslog:
      enabled: false
      host: localhost
      port: 514
```

### Structured Logging

Logs are JSON formatted with:

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "logger": "xnch.nexi.evaluator",
  "message": "Evaluated candidates",
  "trace_id": "abc123",
  "data": {...}
}
```

## Tracing

### OpenTelemetry

```yaml
tracing:
  enabled: true
  exporter: otlp
  endpoint: http://localhost:4317
  service_name: xnch
```

### Trace Spans

| Span | Description |
|------|-------------|
| `xnch.execute` | Full execution |
| `nexi.generate_options` | Option generation |
| `nexi.evaluate` | Evaluation |
| `memory.store` | Memory operations |
| `execution.run` | Plan execution |

## Dashboard

### Grafana Dashboard

Import the included Grafana dashboard:

```bash
xnch dashboard import --grafana-url=http://localhost:3000
```

### Key Dashboards

- **Execution Overview**: Success rate, duration, throughput
- **Nexi Performance**: Candidate generation, evaluation time
- **Memory Health**: Store sizes, query latency
- **Learning Progress**: Episodes, patterns, adaptations

## Alerts

### Recommended Alerts

```yaml
alerts:
  - name: high_failure_rate
    metric: xnch_execution_failure_total
    threshold: ">0.1"  # 10% failure rate
    severity: critical
    
  - name: high_latency
    metric: xnch_execution_duration_seconds
    threshold: ">30"  # 30 seconds
    severity: warning
    
  - name: policy_rejection_high
    metric: xnch_nexi_candidates_filtered
    threshold: ">0.8"  # 80% filtered
    severity: warning
```

## Health Checks

```bash
# Check system health
xnch doctor

# Check specific component
xnch health memory
xnch health nexi

# API health endpoint
curl http://localhost:8000/health
```

## Log Aggregation

### Quick Setup with Loki

```bash
# Run Loki
docker run -d -p 3100:3100 grafana/loki

# Configure
logging:
  handlers:
    loki:
      enabled: true
      url: http://localhost:3100/loki/api/v1/push
```