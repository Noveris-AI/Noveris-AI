<!--
Sync Impact Report:
Version: 1.0.0 → 1.1.0
Ratification Date: 2026-01-16
Last Amended: 2026-01-16

Modified Principles: None
Added Sections:
  - Principle VII: Chinese Language Communication (新增中文交流原则)

Removed Sections: None

Templates Requiring Updates:
  ✅ .specify/templates/plan-template.md - No changes needed (language-agnostic)
  ✅ .specify/templates/spec-template.md - No changes needed (language-agnostic)
  ✅ .specify/templates/tasks-template.md - No changes needed (language-agnostic)
  ✅ .specify/templates/agent-file-template.md - No changes needed
  ✅ .specify/templates/checklist-template.md - No changes needed

Follow-up TODOs: None
-->

# Noveris AI Constitution

## Core Principles

### I. Configuration First
All configuration MUST be externalized through environment variables. Hardcoding sensitive information (passwords, API keys, tokens) or environment-specific values (URLs, ports, database names) is STRICTLY PROHIBITED.

**Rationale**: Configuration through environment variables enables secure, flexible deployments across development, testing, and production environments while preventing credential leaks and supporting containerization strategies.

**Requirements**:
- Use environment variables for all configuration
- Follow precedence: default values < configuration files < environment variables < runtime parameters
- Never commit `.env` files or secrets to version control
- Maintain `env-example-template.txt` with all required variables documented

### II. Security by Design
All security measures MUST be implemented proactively as part of the initial design, not retrofitted later. Session + Cookie authentication is the REQUIRED authentication mechanism. JWT tokens are PROHIBITED.

**Rationale**: Security vulnerabilities are exponentially more expensive to fix after deployment. Session + Cookie authentication provides stronger security boundaries and easier revocation compared to stateless JWT tokens.

**Requirements**:
- Implement Session + Cookie authentication with httponly, secure, and samesite flags
- Enforce password policies (12+ characters, mixed case, numbers, special characters)
- Validate and sanitize all user inputs
- Use parameterized queries for all database operations
- Enable HTTPS in production with security headers (X-Frame-Options, CSP, HSTS)
- Implement CSRF protection for state-changing operations
- Sanitize all HTML content to prevent XSS attacks
- Log security events (login attempts, password changes, suspicious activity) with PII redaction

### III. API Standards Compliance
All APIs MUST follow RESTful design principles with consistent resource naming, HTTP methods, and response formats. API versioning is REQUIRED for all public endpoints.

**Rationale**: Consistent API design reduces integration errors, improves developer experience, and enables smooth evolution of services without breaking existing clients.

**Requirements**:
- Use semantic resource naming (plural nouns: `/users`, `/posts`)
- Apply correct HTTP methods (GET for retrieval, POST for creation, PUT/PATCH for updates, DELETE for removal)
- Return standardized JSON responses with `success`, `data`, `error`, and `pagination` fields
- Version all public APIs using URL path versioning (`/api/v1/`, `/api/v2/`)
- Document APIs with OpenAPI/Swagger specifications
- Implement pagination for list endpoints (default: page=1, page_size=20, max: 100)

### IV. Testing Discipline
Testing MUST follow the testing pyramid: 70-80% unit tests, 15-20% integration tests, 5-10% end-to-end tests. Unit test coverage MUST NOT fall below 80% for new code, with critical paths requiring 90% coverage.

**Rationale**: The testing pyramid balances test execution speed, maintenance cost, and fault detection. High unit test coverage catches bugs early when they are cheapest to fix.

**Requirements**:
- Write unit tests for all business logic and service layers
- Mock external dependencies (databases, APIs, file systems) in unit tests
- Implement integration tests for API endpoints with real database connections
- Ensure all tests run independently without shared state
- Configure CI/CD to fail builds when coverage drops below 80%
- Use descriptive test names that explain the scenario and expected outcome

### V. Observability & Structured Logging
All services MUST emit structured JSON logs with appropriate severity levels. Logs MUST include correlation IDs for distributed tracing. Sensitive information MUST be redacted from logs.

**Rationale**: Structured logging enables automated analysis, alerting, and troubleshooting in production environments. Correlation IDs are essential for tracing requests across microservices.

**Requirements**:
- Log in structured JSON format with fields: timestamp, level, message, correlation_id, user_id, service_name
- Use appropriate log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Redact sensitive fields (passwords, tokens, session_ids, emails, credit cards) before logging
- Include request/response logging for all API calls with timing metrics
- Implement health check endpoints (`/health`, `/ready`) for Kubernetes probes
- Export metrics to Prometheus (request count, latency, error rates)
- Enable distributed tracing with Jaeger for cross-service requests

### VI. Database Design & Migration Discipline
All database changes MUST be applied through versioned migration scripts. Schema changes MUST be backward-compatible for zero-downtime deployments. Soft deletes (deleted_at timestamp) are REQUIRED for all user-facing entities.

**Rationale**: Versioned migrations enable reliable deployments and rollbacks. Backward-compatible changes allow rolling updates without service interruption. Soft deletes preserve data integrity and enable audit trails.

**Requirements**:
- Use migration tools (Alembic for Python, Flyway for Java) for all schema changes
- Never modify existing migrations after they reach production
- Implement soft deletes with `deleted_at` timestamp column on User, Post, and other primary entities
- Follow naming conventions: `snake_case` for tables/columns, plural table names
- Add indexes on foreign keys and frequently queried columns
- Use `created_at`, `updated_at`, `deleted_at` timestamps on all tables
- Implement tenant isolation with `tenant_id` column for multi-tenant data

### VII. Chinese Language Communication
All responses to users MUST be in Chinese (中文). This applies to all user-facing communications, documentation comments, and interactive messages.

**Rationale**: Ensuring consistent language usage improves user experience and accessibility for Chinese-speaking users. Standardized language reduces confusion and maintains professional communication standards.

**Requirements**:
- All user-facing responses MUST be written in Chinese
- Error messages and system notifications MUST be in Chinese
- Interactive prompts and confirmations MUST use Chinese
- Code comments in implementation files MAY remain in English for technical clarity
- API responses and technical logs MAY use English for compatibility with monitoring tools
- Documentation intended for end users SHOULD be provided in Chinese

## Development Workflow

### Branch Strategy
- `main`: Production-ready code, always deployable
- `feature/*`: Feature development branches
- `hotfix/*`: Emergency production fixes
- `release/*`: Release preparation branches

### Commit Standards
Follow Conventional Commits specification:
- `feat`: New features
- `fix`: Bug fixes
- `docs`: Documentation changes
- `style`: Code formatting (no functional changes)
- `refactor`: Code restructuring without behavior changes
- `perf`: Performance optimizations
- `test`: Test additions or modifications
- `chore`: Build tool or dependency updates

### Code Review Requirements
- All changes MUST be reviewed by at least one team member
- Reviewers MUST verify compliance with this constitution
- CI/CD checks (linting, tests, security scans) MUST pass before merge
- Breaking changes MUST be documented and approved by technical lead

### Deployment Standards
- Use Docker for containerization with multi-stage builds
- Apply infrastructure as code principles (Kubernetes manifests, Helm charts)
- Separate configuration by environment (dev, staging, production)
- Implement automated rollback procedures for failed deployments
- Require smoke tests after deployment before marking release as successful

## Governance

This constitution supersedes all other development practices and guidelines. All team members MUST adhere to these principles.

### Amendment Process
1. Proposed amendments MUST be documented with rationale and impact analysis
2. Technical lead MUST review and approve all amendments
3. Version number MUST be incremented following semantic versioning:
   - MAJOR: Backward-incompatible governance changes or principle removals
   - MINOR: New principle additions or material expansions
   - PATCH: Clarifications, wording improvements, non-semantic fixes
4. Migration plan MUST be provided for any breaking changes
5. All dependent templates and documentation MUST be updated for consistency

### Compliance Review
- All pull requests MUST include a constitution compliance checklist
- Technical debt that violates principles MUST be justified in writing with:
  - Specific principle violated
  - Business justification for the exception
  - Remediation plan with timeline
- Security and configuration principles (I, II) have NO EXCEPTIONS
- Regular audits MUST verify ongoing compliance

### Runtime Development Guidance
For detailed implementation guidance on specific topics, refer to the comprehensive standards in the `/Docs` directory:
- Configuration: `Docs/10-Config-Standard.md`
- Database: `Docs/20-Database-Standard.md`
- API: `Docs/30-API-Standard.md`
- Testing: `Docs/40-Testing-Standard.md`
- Deployment: `Docs/50-Deployment-Standard.md`
- Security: `Docs/60-Security-Standard.md`
- Performance: `Docs/70-Performance-Standard.md`
- Observability: `Docs/80-Observability-Standard.md`
- Git/Release: `Docs/90-Git-Release-Standard.md`

**Version**: 1.1.0 | **Ratified**: 2026-01-16 | **Last Amended**: 2026-01-16
