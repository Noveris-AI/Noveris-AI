# Feature Specification: Node Management Frontend-Backend Integration

**Feature Branch**: `001-node-management-integration`
**Created**: 2026-01-16
**Status**: Draft
**Input**: User description: "关于节点管理，我目前有后端与前端代码，但是不一定有对接上，我需要你分析现有代码，给出计划"

## Overview

This feature addresses the integration gaps between the existing Node Management frontend and backend implementations. The backend provides comprehensive node management capabilities (CRUD operations, connectivity verification, job execution, inventory management), while the frontend has API client code that is not fully aligned with backend responses and enumerations.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verify Node Connectivity (Priority: P1)

As an administrator, I need to verify that a compute node is reachable and properly configured so that I can confidently deploy workloads to it.

**Why this priority**: Connectivity verification is the foundational operation that enables all other node management tasks. Without reliable connectivity checks, administrators cannot trust the system's node status.

**Independent Test**: Can be fully tested by selecting a node and clicking "Verify Connectivity" - the system should display clear success/failure status with detailed diagnostics.

**Acceptance Scenarios**:

1. **Given** a registered node with SSH credentials, **When** user clicks "Verify Connectivity", **Then** system displays reachability status, response time, and connection details
2. **Given** a node that is unreachable, **When** user attempts connectivity check, **Then** system displays clear error message explaining the failure reason
3. **Given** multiple nodes selected, **When** user triggers bulk connectivity check, **Then** system shows individual results for each node with summary statistics

---

### User Story 2 - View Node Details with Accelerator Information (Priority: P1)

As an administrator, I need to view complete node details including GPU/NPU accelerator information so that I can understand the computing capabilities available.

**Why this priority**: Accurate display of node capabilities, especially accelerators, is critical for workload placement decisions in AI/ML platforms.

**Independent Test**: Can be fully tested by navigating to a node detail page - all hardware facts, accelerator types (NVIDIA GPU, AMD GPU, Ascend NPU, etc.), and node status should display correctly.

**Acceptance Scenarios**:

1. **Given** a node with NVIDIA GPUs, **When** user views node details, **Then** accelerator type displays correctly as "NVIDIA GPU" with device count
2. **Given** a node with Huawei Ascend NPUs, **When** user views node details, **Then** accelerator type displays correctly as "Ascend NPU"
3. **Given** a node with custom/generic accelerators, **When** user views node details, **Then** accelerator type displays as "Generic Accelerator"

---

### User Story 3 - Create and Manage Nodes with All Connection Types (Priority: P2)

As an administrator, I need to add new nodes using SSH, Local, or WinRM connection types so that I can manage both Linux and Windows infrastructure.

**Why this priority**: Node creation is essential, but the current system already supports SSH and Local. Adding WinRM support expands the platform's capability to Windows environments.

**Independent Test**: Can be fully tested by creating a node with each connection type (SSH, Local, WinRM) and verifying successful creation and connectivity.

**Acceptance Scenarios**:

1. **Given** a Linux server, **When** user creates a node with SSH connection, **Then** node is created and can be verified
2. **Given** a Windows server, **When** user creates a node with WinRM connection, **Then** node is created with proper WinRM settings (transport, certificate validation)
3. **Given** the local machine, **When** user creates a node with Local connection, **Then** node is created for local execution

---

### User Story 4 - Execute and Monitor Job Runs (Priority: P2)

As an administrator, I need to run jobs on nodes and monitor their execution output so that I can perform maintenance tasks and verify results.

**Why this priority**: Job execution is core functionality, and users need to see real-time output to troubleshoot issues.

**Independent Test**: Can be fully tested by running a job on a node and viewing the execution events and output stream.

**Acceptance Scenarios**:

1. **Given** a job template selected, **When** user triggers job execution on a node, **Then** job status updates in real-time (pending → running → success/failed)
2. **Given** a running job, **When** user views job details, **Then** execution events stream in real-time
3. **Given** a completed job, **When** user reviews job history, **Then** all events and final status are preserved and viewable

---

### User Story 5 - Navigate Node Lists with Pagination (Priority: P3)

As an administrator, I need to browse through large numbers of nodes efficiently so that I can manage infrastructure at scale.

**Why this priority**: Pagination is a UX enhancement that becomes critical only at scale; basic functionality works without it.

**Independent Test**: Can be fully tested by listing nodes when >10 nodes exist - pagination controls should work correctly.

**Acceptance Scenarios**:

1. **Given** 50 registered nodes, **When** user loads node list, **Then** first page shows configured page size with correct total count
2. **Given** node list on page 2, **When** user clicks next page, **Then** system navigates to page 3 with correct nodes

---

### Edge Cases

- What happens when node credentials are expired or invalid during connectivity check?
- How does system handle network timeout during connectivity verification?
- What happens when a job execution is canceled mid-run?
- How does system behave when node status changes during a long-running operation?
- What happens when accelerator detection returns unknown hardware types?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST return complete connectivity check results including reachability status, response time, and error details
- **FR-002**: System MUST correctly map all accelerator types between frontend display and backend storage (NVIDIA GPU, AMD GPU, Intel GPU, Ascend NPU, T-Head NPU, Generic Accelerator)
- **FR-003**: System MUST support all three connection types (SSH, Local, WinRM) in both node creation and display
- **FR-004**: System MUST provide consistent pagination information including total count, current page, and total pages
- **FR-005**: System MUST support bulk connectivity verification for multiple nodes simultaneously
- **FR-006**: System MUST display job execution events in real-time with proper sequence ordering
- **FR-007**: System MUST handle job serial configuration as text values (supporting formats like "10%", "3", "30%")
- **FR-008**: System MUST provide appropriate error messages when API calls fail

### Key Entities

- **Node**: Computing resource with hostname, connection credentials, status, and hardware capabilities
- **Accelerator**: GPU or NPU device attached to a node with type, count, and memory specifications
- **NodeGroup**: Logical grouping of nodes for inventory management
- **JobRun**: Execution instance of a job template on one or more nodes
- **JobRunEvent**: Individual event during job execution containing output, timing, and status

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of API responses from backend are correctly parsed and displayed in frontend without type errors
- **SC-002**: All 6 accelerator types are correctly displayed with appropriate icons and labels
- **SC-003**: Connectivity verification shows complete diagnostic information within 30 seconds per node
- **SC-004**: Bulk verification of 10 nodes completes and displays individual results within 60 seconds
- **SC-005**: Job execution events appear in UI within 2 seconds of being generated
- **SC-006**: Node creation succeeds for all three connection types (SSH, Local, WinRM) when valid credentials are provided
- **SC-007**: Pagination correctly handles lists of 100+ nodes without UI errors

## Assumptions

- Backend API endpoints are correctly implemented and return data as defined in schemas
- Frontend has access to authentication tokens for API calls
- Network connectivity between frontend and backend is stable
- WinRM-enabled Windows nodes have proper firewall and service configuration

## Dependencies

- Backend Node Management API (v1/nodes endpoints)
- Backend Job Management API (v1/job-runs, v1/job-templates endpoints)
- Frontend routing and authentication infrastructure
- Existing UI component library for consistent styling

## Out of Scope

- Backend API implementation changes (this feature focuses on frontend alignment)
- New backend endpoints beyond what's documented in schemas
- Mobile responsive design
- Offline/cached operation support
- Real-time WebSocket updates (current implementation uses polling/REST)
