# Qwenvert AI Agents

This document catalogs the specialized AI agents available for qwenvert development.

## Available Agents

### 🛡️ qwenvert-security-auditor
**Location**: `.claude/agents/qwenvert-security-auditor.md`
**Model**: Sonnet
**Tools**: Read, Grep, Bash

Security audit specialist focused on maintaining qwenvert's core security guarantees.

**Use cases**:
- Audit network isolation (localhost-only)
- Verify no data exfiltration
- Check for credential leaks
- Review external dependencies
- Validate security test coverage

**When to use**: After any code changes, especially to networking, configuration, or telemetry systems.

---

### 👁️ qwenvert-reviewer
**Location**: `.claude/agents/qwenvert-reviewer.md`
**Model**: Sonnet
**Tools**: Read, Grep, Glob, Bash

Expert code reviewer specializing in Anthropic API compatibility and backend transformations.

**Use cases**:
- PR reviews
- Architecture validation
- API compatibility checks
- Python best practices
- Security review

**When to use**: After implementations, before PRs, or for general code review.

---

### ⚡ qwenvert-perf-analyzer
**Location**: `.claude/agents/qwenvert-perf-analyzer.md`
**Model**: Sonnet
**Tools**: Read, Grep, Glob, Bash

Performance analysis specialist for M-series hardware optimization.

**Use cases**:
- Benchmark analysis
- Memory usage optimization
- Token throughput analysis
- Hardware utilization review
- Configuration tuning

**When to use**: When investigating performance issues or optimizing for specific hardware.

---

### 🧪 test-runner
**Location**: `.claude/agents/test-runner.md`
**Model**: Sonnet
**Tools**: Read, Grep, Bash

Automated testing specialist for CI/CD validation.

**Use cases**:
- Run test suites
- Analyze test failures
- Generate test reports
- Coverage analysis

**When to use**: After code changes, before commits, or for CI validation.

---

### 📝 doc-maintainer
**Location**: `.claude/agents/doc-maintainer.md`
**Model**: Sonnet
**Tools**: Read, Grep, Glob, Write, Edit

Documentation maintenance specialist.

**Use cases**:
- Update documentation after code changes
- Maintain architecture docs
- Generate API documentation
- Keep README.md current

**When to use**: After significant feature additions or architectural changes.

---

### 🌿 worktree-coordinator
**Location**: `.claude/agents/worktree-coordinator.md`
**Model**: Sonnet
**Tools**: Bash, Read, Grep

Git worktree management specialist.

**Use cases**:
- Create feature worktrees
- Manage parallel development
- Coordinate cross-branch work
- Clean up stale worktrees

**When to use**: When working on multiple features simultaneously.

---

### 🔧 code-simplifier
**Location**: `.claude/agents/code-simplifier.md`
**Model**: Sonnet
**Tools**: Read, Grep, Edit, Write

Code simplification and refactoring specialist.

**Use cases**:
- Reduce code complexity
- Eliminate duplication
- Improve readability
- Refactor for maintainability

**When to use**: When code becomes complex or needs simplification.

---

## Usage Patterns

### Security-First Development
For any changes to networking, configuration, or data handling:
1. Make changes
2. Run `qwenvert-security-auditor` ← **Critical for telemetry/network changes**
3. Run `test-runner`
4. Get `qwenvert-reviewer` approval

### Feature Development
For new features:
1. Use `worktree-coordinator` to create feature branch
2. Implement feature
3. Run `test-runner`
4. Run `qwenvert-reviewer` for code review
5. Run `qwenvert-security-auditor` if touching network/config
6. Update docs with `doc-maintainer`

### Performance Optimization
For performance work:
1. Baseline with `qwenvert-perf-analyzer`
2. Make optimizations
3. Benchmark with `qwenvert-perf-analyzer`
4. Review with `qwenvert-reviewer`

### Telemetry/Observability Changes
For OpenTelemetry or monitoring changes:
1. Implement changes
2. **Run `qwenvert-security-auditor` immediately** ← Telemetry can leak data!
3. Run `qwenvert-perf-analyzer` to check overhead
4. Run `test-runner`
5. Review with `qwenvert-reviewer`

---

## Agent Development

To create a new agent:

1. Create `.claude/agents/your-agent.md` with frontmatter:
```yaml
---
name: your-agent-name
description: Brief description of agent purpose
tools: Read, Grep, Bash
model: sonnet
memory: project
---
```

2. Document the agent's:
   - Mission and purpose
   - When to invoke it
   - Expected outputs
   - Key principles

3. Add to this AGENTS.md file

4. Test with: `claude-code task --agent=your-agent-name "test task"`

---

## Memory Management

All agents use **project memory** to maintain context across conversations:
- Security patterns and vulnerabilities
- Performance baselines
- Code style preferences
- Known issues and workarounds

This enables agents to learn from previous audits and provide more context-aware analysis.

---

**Last Updated**: 2026-02-09
