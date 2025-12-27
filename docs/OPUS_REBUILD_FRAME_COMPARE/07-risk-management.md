# Risk Management

> **Module:** Planning  
> **Version:** 1.0

---

## 1. Risk Register

### 1.1 Technical Risks

| ID | Risk | Probability | Impact | Score | Owner | Status |
|----|------|-------------|--------|-------|-------|--------|
| TR-001 | VapourSynth container build fails | Medium | Critical | High | DevOps | Open |
| TR-002 | libplacebo API changes | Low | High | Medium | Core Dev | Open |
| TR-003 | slow.pics API deprecation | Low | Medium | Low | Core Dev | Open |
| TR-004 | Python 3.13 breaks dependencies | Low | High | Medium | Core Dev | Open |
| TR-005 | Performance regression | Medium | Medium | Medium | Core Dev | Open |
| TR-006 | Memory exhaustion on large files | Medium | Medium | Medium | Core Dev | Open |

### 1.2 Project Risks

| ID | Risk | Probability | Impact | Score | Owner | Status |
|----|------|-------------|--------|-------|-------|--------|
| PR-001 | Scope creep | Medium | Medium | Medium | PM | Open |
| PR-002 | Feature parity gaps discovered late | Medium | High | High | QA | Open |
| PR-003 | Documentation incomplete | Medium | Low | Low | Tech Writer | Open |
| PR-004 | Testing infrastructure delays | Low | Medium | Low | DevOps | Open |

### 1.3 External Risks

| ID | Risk | Probability | Impact | Score | Owner | Status |
|----|------|-------------|--------|-------|-------|--------|
| ER-001 | TMDB API changes | Low | Low | Low | Core Dev | Open |
| ER-002 | Docker Hub rate limits | Medium | Low | Low | DevOps | Open |
| ER-003 | GitHub Actions quota | Low | Low | Low | DevOps | Open |

---

## 2. Risk Assessment Matrix

```
        │ Low Impact    Medium Impact   High Impact
────────┼───────────────────────────────────────────
High    │               TR-005, TR-006  TR-001
Prob    │               PR-001          PR-002
────────┼───────────────────────────────────────────
Medium  │ ER-002        TR-002, TR-004  
Prob    │ PR-003        PR-004          
────────┼───────────────────────────────────────────
Low     │ ER-001        TR-003
Prob    │ ER-003        
```

---

## 3. Mitigation Strategies

### TR-001: VapourSynth Container Build Fails

**Severity:** Critical  
**Mitigation:**

1. Use multi-stage build with cached base image
2. Pre-build VapourSynth in separate CI job
3. Maintain fallback to software-only libplacebo
4. Document manual installation as backup

**Contingency:**

- Provide pre-built base images on ghcr.io
- Fall back to pip installation with manual VS

### TR-002: libplacebo API Changes

**Severity:** High  
**Mitigation:**

1. Pin libplacebo version in container
2. Abstract libplacebo calls behind interface
3. Monitor libplacebo releases

**Contingency:**

- Version-specific code paths
- Fallback to basic tonemapping

### TR-003: slow.pics API Deprecation

**Severity:** Medium  
**Mitigation:**

1. Adapter pattern for publishing interface
2. Local-only mode always functional
3. Monitor slow.pics announcements

**Contingency:**

- Implement alternative host support
- Focus on HTML report as primary output

### PR-002: Feature Parity Gaps

**Severity:** High  
**Mitigation:**

1. Create feature matrix early (Phase 0)
2. Test each feature against v0.0.14
3. Involve existing users in UAT

**Contingency:**

- Prioritize blocking gaps
- Document known limitations

### TR-005: Performance Regression

**Severity:** Medium  
**Mitigation:**

1. Establish baseline benchmarks
2. Profile critical paths
3. CI performance tests

**Contingency:**

- Optimization sprint before launch
- Document performance expectations

---

## 4. Risk Monitoring

### 4.1 Review Cadence

| Frequency | Activity |
|-----------|----------|
| Weekly | Risk status update |
| Sprint | Risk review in retrospective |
| Phase End | Full risk reassessment |
| Incident | Immediate risk review |

### 4.2 Escalation Criteria

| Score | Action |
|-------|--------|
| Low | Monitor, no action required |
| Medium | Active mitigation, report to lead |
| High | Immediate mitigation, escalate to PM |
| Critical | Stop work, executive notification |

---

## 5. Contingency Budget

| Category | Reserve | Purpose |
|----------|---------|---------|
| Schedule | +2 weeks | Technical blockers |
| Scope | Defer P2 features | Prioritization flexibility |
| Resources | Consultant budget | External expertise |
