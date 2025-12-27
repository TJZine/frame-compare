# Sprint Planning Templates

> **Module:** Roadmap  
> **Version:** 1.0

---

## 1. Sprint Template

### 1.1 Sprint Header

```yaml
Sprint: [Number]
Duration: 2 weeks
Start Date: YYYY-MM-DD
End Date: YYYY-MM-DD
Goal: [One-sentence sprint goal]

Team Capacity:
  Available Days: [X]
  Story Points Target: [X]
```

### 1.2 Story Template

```yaml
STORY-XXX:
  Title: [User story title]
  Type: [Feature | Bug | Chore | Spike]
  Priority: [P0 | P1 | P2]
  Points: [1 | 2 | 3 | 5 | 8 | 13]
  
  User Story: |
    As a [user type]
    I want [capability]
    So that [benefit]
  
  Acceptance Criteria:
    - GIVEN [context] WHEN [action] THEN [result]
    - GIVEN [context] WHEN [action] THEN [result]
  
  Tasks:
    - [ ] TASK-001: [Technical task] (Xh)
    - [ ] TASK-002: [Technical task] (Xh)
    - [ ] TASK-003: [Write tests] (Xh)
    - [ ] TASK-004: [Update docs] (Xh)
  
  Dependencies:
    - [STORY-XXX]
  
  Notes: |
    [Additional context, edge cases, technical notes]
```

---

## 2. Sprint Planning Checklist

### Before Planning

- [ ] Previous sprint retrospective complete
- [ ] Backlog groomed and prioritized
- [ ] Stories estimated and well-defined
- [ ] Dependencies identified
- [ ] Team capacity calculated

### During Planning

- [ ] Sprint goal agreed
- [ ] Stories selected from backlog
- [ ] Tasks broken down
- [ ] Risks discussed
- [ ] Commitment confirmed

### After Planning

- [ ] Sprint board updated
- [ ] Calendar blocked
- [ ] Stakeholders notified
- [ ] Documentation started

---

## 3. Definition of Done

### Story Level

- [ ] All acceptance criteria met
- [ ] Code reviewed and approved
- [ ] Unit tests written and passing
- [ ] Integration tests for critical paths
- [ ] No Pyright errors
- [ ] No Ruff errors
- [ ] Documentation updated
- [ ] Deployed to staging

### Sprint Level

- [ ] All committed stories complete
- [ ] Sprint demo prepared
- [ ] Retrospective scheduled
- [ ] Metrics collected
- [ ] Backlog refined for next sprint

---

## 4. Example Sprints

### Sprint 0: Foundation

```yaml
Sprint: 0
Duration: 1 week
Goal: Project scaffolding and CI/CD pipeline

Stories:

  STORY-001:
    Title: Project scaffold setup
    Type: Chore
    Priority: P0
    Points: 3
    
    Acceptance Criteria:
      - GIVEN new clone WHEN `uv sync` runs THEN dependencies install
      - GIVEN project WHEN `.venv/bin/pyright --warnings` runs THEN 0 errors
      - GIVEN project WHEN `.venv/bin/pytest -q` runs THEN empty suite passes
    
    Tasks:
      - [ ] Create directory structure (1h)
      - [ ] Configure pyproject.toml (2h)
      - [ ] Setup pytest configuration (1h)
      - [ ] Setup Ruff and Pyright (1h)

  STORY-002:
    Title: GitHub Actions CI pipeline
    Type: Chore
    Priority: P0
    Points: 2
    
    Acceptance Criteria:
      - GIVEN push to main WHEN CI runs THEN lint + type + test stages execute
      - GIVEN failed lint WHEN CI runs THEN build fails with clear error
    
    Tasks:
      - [ ] Create CI workflow file (2h)
      - [ ] Configure matrix for Python 3.13 (1h)
      - [ ] Add status badges to README (30m)

  STORY-003:
    Title: Dockerfile and DevContainer
    Type: Chore
    Priority: P0
    Points: 5
    
    Acceptance Criteria:
      - GIVEN Dockerfile WHEN `docker build` runs THEN image builds
      - GIVEN VS Code WHEN "Reopen in Container" THEN dev environment ready
      - GIVEN container WHEN VapourSynth imported THEN R72+ available
    
    Tasks:
      - [ ] Create multi-stage Dockerfile (3h)
      - [ ] Build VapourSynth in container (4h)
      - [ ] Configure DevContainer (2h)
      - [ ] Document container usage (1h)
```

### Sprint 1: Analysis Module

```yaml
Sprint: 1
Duration: 2 weeks
Goal: Complete frame analysis and selection module

Stories:

  STORY-004:
    Title: Frame metrics calculation
    Type: Feature
    Priority: P0
    Points: 5
    
    User Story: |
      As a user
      I want frame metrics calculated automatically
      So that representative frames are selected
    
    Acceptance Criteria:
      - GIVEN video clip WHEN metrics calculated THEN luminance values normalized [0,1]
      - GIVEN two identical videos WHEN metrics calculated THEN results identical
      - GIVEN progress callback WHEN processing THEN progress reported
    
    Tasks:
      - [ ] Create types.py with FrameMetrics (2h)
      - [ ] Implement luminance calculation (3h)
      - [ ] Implement motion calculation (3h)
      - [ ] Write unit tests (3h)
      - [ ] Add progress callbacks (2h)

  STORY-005:
    Title: Frame selection algorithms
    Type: Feature
    Priority: P0
    Points: 5
    
    User Story: |
      As a user
      I want frames selected by luminance, motion, and random
      So that I get representative samples
    
    Acceptance Criteria:
      - GIVEN same seed WHEN selection runs twice THEN same frames selected
      - GIVEN N frames requested WHEN selection runs THEN exactly N unique frames returned
      - GIVEN selection breakdown WHEN inspected THEN shows quantile/motion/random counts
    
    Tasks:
      - [ ] Implement quantile selection (3h)
      - [ ] Implement motion selection (3h)
      - [ ] Implement random selection (2h)
      - [ ] Combine into mixed mode (2h)
      - [ ] Write unit tests (4h)

  STORY-006:
    Title: Metrics caching
    Type: Feature
    Priority: P0
    Points: 3
    
    User Story: |
      As a user
      I want metrics cached
      So that subsequent runs are faster
    
    Acceptance Criteria:
      - GIVEN first run WHEN metrics computed THEN cache file created
      - GIVEN second run WHEN config unchanged THEN cache hit
      - GIVEN config changed WHEN run THEN cache miss, recomputed
    
    Tasks:
      - [ ] Implement cache key computation (2h)
      - [ ] Implement cache read/write (3h)
      - [ ] Handle cache versioning (2h)
      - [ ] Write integration tests (2h)
```

---

## 5. Estimation Guidelines

### Story Points Scale

| Points | Complexity | Risk | Example |
|--------|------------|------|---------|
| 1 | Trivial | None | Config change |
| 2 | Simple | Low | Add new option |
| 3 | Standard | Low | New helper function |
| 5 | Moderate | Medium | New module |
| 8 | Complex | Medium | Integration work |
| 13 | Very complex | High | Architectural change |

### Estimation Tips

1. **Don't estimate in hours** — use relative sizing
2. **Include testing time** — tests are not optional
3. **Account for unknowns** — spikes reduce risk
4. **Compare to reference stories** — use past velocity
5. **Split large stories** — nothing over 13 points

---

## 6. Sprint Metrics

### Velocity Tracking

| Sprint | Committed | Completed | Velocity |
|--------|-----------|-----------|----------|
| 0 | 10 | 10 | 10 |
| 1 | 13 | 11 | 11 |
| 2 | 12 | 12 | 12 |
| Avg | - | - | 11 |

### Burndown Template

```
Points Remaining
     │
  13 │●
     │ ●
  10 │  ●
     │   ●
   5 │    ●──────●
     │           ●
   0 │            ●
     └──────────────────
       D1  D3  D5  D7  D10
```

---

## 7. Retrospective Template

### What Went Well

- [Item 1]
- [Item 2]

### What Could Improve

- [Issue 1] → [Action item]
- [Issue 2] → [Action item]

### Action Items

| Action | Owner | Due |
|--------|-------|-----|
| [Action 1] | [Name] | [Date] |
| [Action 2] | [Name] | [Date] |
