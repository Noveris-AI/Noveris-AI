# Tasks: 前后端鉴权集成与登录流程优化

**Input**: Design documents from `/specs/002-auth-integration/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are OPTIONAL in this implementation - test tasks are NOT included per project practice.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `Backend/`, `Frontend/` at repository root
- Paths follow the project structure defined in plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Remove Mock鉴权配置 - 删除Frontend/.env中的VITE_USE_MOCK_AUTH环境变量
- [X] T002 [P] Remove Mock鉴权文件 - 删除Frontend/src/features/auth/api/authMock.ts
- [X] T003 [P] Remove Mock配置 - 删除Frontend/src/shared/config/auth.ts中的API_MODE配置

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Remove前端Mock token注入 - 删除Frontend/src/shared/lib/apiClient.ts中的Mock token注入逻辑(115-121行)
- [X] T005 扩展BaseApiClient添加401拦截 - 在Frontend/src/shared/lib/apiClient.ts的request()方法中添加401状态码拦截逻辑和onUnauthorized回调支持
- [X] T006 [P] 创建AuthContext - 创建Frontend/src/features/auth/contexts/AuthContext.tsx,实现用户认证状态管理
- [X] T007 [P] 创建useAuth Hook - 创建Frontend/src/features/auth/hooks/useAuth.ts,封装AuthContext的使用
- [X] T008 [P] 创建ProtectedRoute组件 - 创建Frontend/src/shared/components/routing/ProtectedRoute.tsx,实现路由守卫
- [X] T009 修改authClient移除Mock选择 - 修改Frontend/src/features/auth/api/authClient.ts,始终使用RealAuthClient
- [X] T010 检查并移除后端Mock token识别 - 检查Backend/app/core/dependencies.py中是否有Mock token识别逻辑,如有则移除

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - 正常登录流程 (Priority: P1) 🎯 MVP

**Goal**: 实现用户从访问应用到成功登录并进入主页的完整流程,确保未登录用户自动重定向到登录页

**Independent Test**: 访问应用根路径或任何受保护页面,验证是否正确显示登录页,使用测试账号完成登录流程,成功进入主页

### Implementation for User Story 1

- [X] T011 [US1] 修改App.tsx添加AuthProvider - 在Frontend/src/App.tsx中使用AuthProvider包裹所有路由
- [X] T012 [US1] 修改App.tsx根路径重定向逻辑 - 修改Frontend/src/App.tsx中的根路径(/),根据登录状态重定向到登录页或主页
- [X] T013 [US1] 使用ProtectedRoute包裹受保护路由 - 在Frontend/src/App.tsx中使用ProtectedRoute组件包裹/dashboard及其子路由
- [X] T014 [US1] 修改LoginPage处理重定向 - 修改Frontend/src/features/auth/pages/LoginPage.tsx,从location.state获取原始URL,登录成功后跳转回去
- [X] T015 [US1] 添加LoginPage"记住我"选项 - 在Frontend/src/features/auth/pages/LoginPage.tsx中添加remember_me复选框UI
- [X] T016 [US1] 实现登录表单验证 - 在Frontend/src/features/auth/pages/LoginPage.tsx中使用React Hook Form和Zod验证邮箱和密码
- [X] T017 [US1] 注册全局401拦截器 - 在Frontend/src/features/auth/contexts/AuthContext.tsx的useEffect中注册apiClient.onUnauthorized回调

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - 会话管理和登出 (Priority: P2)

**Goal**: 实现用户登出功能和会话过期自动处理,确保用户可以主动登出或会话过期时自动退出登录

**Independent Test**: 登录系统后,点击登出按钮验证能否正确清除会话并返回登录页;模拟会话超时后刷新页面,验证是否重定向到登录页

### Implementation for User Story 2

- [X] T018 [US2] 实现AuthContext的logout方法 - 在Frontend/src/features/auth/contexts/AuthContext.tsx中实现logout方法,调用authClient.logout()并清除状态
- [X] T019 [US2] 实现401拦截器的清除逻辑 - 在Frontend/src/features/auth/contexts/AuthContext.tsx的onUnauthorized回调中调用logout()并重定向到登录页
- [X] T020 [US2] 添加登出按钮UI - 在Dashboard布局组件中添加登出按钮,调用useAuth().logout()
- [X] T021 [US2] 实现多标签页登出同步 - 配置React Query的refetchOnWindowFocus和错误重试策略,确保多标签页会话失效同步

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - API请求鉴权 (Priority: P1)

**Goal**: 确保所有API请求自动携带会话凭证,后端验证会话有效性后处理请求

**Independent Test**: 登录后访问任何需要鉴权的API端点(如节点列表),验证请求成功;未登录时访问,验证返回401错误

### Implementation for User Story 3

- [X] T022 [P] [US3] 验证BaseApiClient的credentials配置 - 检查Frontend/src/shared/lib/apiClient.ts的fetch请求是否已配置credentials: 'include'
- [X] T023 [P] [US3] 验证后端CORS配置 - 检查Backend/main.py的CORS中间件是否正确配置allow_credentials=True
- [X] T024 [US3] 实现首次访问时获取用户信息 - 在Frontend/src/features/auth/contexts/AuthContext.tsx中使用React Query在首次访问受保护页面时调用getCurrentUser()
- [X] T025 [US3] 配置React Query缓存策略 - 在Frontend/src/features/auth/contexts/AuthContext.tsx中配置staleTime为5分钟,retry为false

**Checkpoint**: All core user stories should now be independently functional

---

## Phase 6: User Story 4 - 用户注册流程 (Priority: P3)

**Goal**: 实现新用户通过注册页面创建账号,接收验证码,完成注册后可以登录

**Independent Test**: 访问注册页面,输入邮箱获取验证码,填写完整信息后成功创建账号,然后使用该账号登录系统

### Implementation for User Story 4

- [X] T026 [P] [US4] 创建注册表单验证Schema - 在Frontend/src/features/auth/api/authTypes.ts中添加registerSchema(Zod),验证邮箱、验证码、密码强度
- [X] T027 [P] [US4] 创建发送验证码表单验证Schema - 在Frontend/src/features/auth/api/authTypes.ts中添加sendVerificationCodeSchema(Zod)
- [X] T028 [US4] 实现RegisterPage表单 - 创建或修改Frontend/src/features/auth/pages/RegisterPage.tsx,使用React Hook Form实现注册表单
- [X] T029 [US4] 实现发送验证码功能 - 在Frontend/src/features/auth/pages/RegisterPage.tsx中实现发送验证码按钮,调用authClient.sendVerificationCode()
- [X] T030 [US4] 添加验证码倒计时UI - 在Frontend/src/features/auth/pages/RegisterPage.tsx中添加60秒倒计时,防止重复请求
- [X] T031 [US4] 实现注册成功后跳转 - 在Frontend/src/features/auth/pages/RegisterPage.tsx中注册成功后重定向到登录页,显示成功提示
- [X] T032 [US4] 添加密码强度指示器 - 在Frontend/src/features/auth/pages/RegisterPage.tsx中添加密码强度实时显示组件

**Checkpoint**: User Story 4 should be independently functional

---

## Phase 7: User Story 5 - 密码重置流程 (Priority: P3)

**Goal**: 用户忘记密码时,可以通过邮箱接收重置链接或验证码,设置新密码

**Independent Test**: 在登录页点击"忘记密码",输入注册邮箱,接收重置链接或验证码,设置新密码后使用新密码登录

### Implementation for User Story 5

- [X] T033 [P] [US5] 创建忘记密码表单验证Schema - 在Frontend/src/features/auth/api/authTypes.ts中添加forgotPasswordSchema(Zod)
- [X] T034 [P] [US5] 创建重置密码表单验证Schema - 在Frontend/src/features/auth/api/authTypes.ts中添加resetPasswordSchema(Zod),验证token或code和新密码
- [X] T035 [US5] 实现ForgotPasswordPage - 创建或修改Frontend/src/features/auth/pages/ForgotPasswordPage.tsx,实现请求重置表单
- [X] T036 [US5] 实现ResetPasswordPage - 创建或修改Frontend/src/features/auth/pages/ResetPasswordPage.tsx,支持token模式和code模式重置
- [X] T037 [US5] 添加重置密码路由 - 在Frontend/src/App.tsx中添加/auth/forgot-password和/auth/reset-password路由
- [X] T038 [US5] 实现重置成功后自动登录提示 - 在Frontend/src/features/auth/pages/ResetPasswordPage.tsx中重置成功后重定向到登录页,提示用户使用新密码登录

**Checkpoint**: User Story 5 should be independently functional

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T039 [P] 更新或移除Mock文档 - 标记或删除MOCK_AUTH_GUIDE.md,在README中说明已移除Mock鉴权
- [ ] T040 [P] 更新README快速开始 - 更新README.md,添加真实鉴权的使用说明和快速开始步骤
- [ ] T041 优化错误提示文案 - 统一前端所有认证相关页面的错误提示,确保用户友好且符合安全要求(不透露用户是否存在)
- [ ] T042 添加加载状态优化 - 在ProtectedRoute和LoginPage中添加加载动画,改善用户体验
- [X] T043 代码清理和注释 - 移除所有Mock相关的注释和废弃代码,添加关键逻辑注释
- [ ] T044 运行quickstart.md验证 - 按照specs/002-auth-integration/quickstart.md中的步骤验证完整功能

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User Story 1 (P1) and User Story 3 (P1) are highest priority, should be completed first
  - User Story 2 (P2) can follow immediately after US1
  - User Stories 4 and 5 (P3) can be completed later or in parallel
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Depends on User Story 1 completion - Needs login flow working first
- **User Story 3 (P1)**: Can start after Foundational (Phase 2) - Works alongside US1
- **User Story 4 (P3)**: Can start after Foundational (Phase 2) - Independent of login flow
- **User Story 5 (P3)**: Can start after Foundational (Phase 2) - Independent of other stories

### Within Each User Story

- Tasks within a story should be completed in listed order unless marked [P]
- Tasks marked [P] can run in parallel (different files, no dependencies)
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (Phase 1)
- All Foundational tasks marked [P] can run in parallel (Phase 2: T006, T007, T008)
- Within User Story 3: T022 and T023 can run in parallel
- Within User Story 4: T026 and T027 can run in parallel
- Within User Story 5: T033 and T034 can run in parallel
- Polish phase: T039 and T040 can run in parallel
- Once Foundational phase completes, User Stories 1 and 3 can work in parallel (both P1)
- User Stories 4 and 5 can work in parallel with each other (both P3)

---

## Parallel Example: Foundational Phase

```bash
# Launch foundational components in parallel:
Task: "创建AuthContext - 创建Frontend/src/features/auth/contexts/AuthContext.tsx"
Task: "创建useAuth Hook - 创建Frontend/src/features/auth/hooks/useAuth.ts"
Task: "创建ProtectedRoute组件 - 创建Frontend/src/shared/components/routing/ProtectedRoute.tsx"
```

---

## Parallel Example: User Story 3

```bash
# Launch verification tasks in parallel:
Task: "验证BaseApiClient的credentials配置 - 检查Frontend/src/shared/lib/apiClient.ts"
Task: "验证后端CORS配置 - 检查Backend/main.py的CORS中间件"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 3 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T010) - CRITICAL - blocks all stories
3. Complete Phase 3: User Story 1 (T011-T017)
4. Complete Phase 5: User Story 3 (T022-T025)
5. **STOP and VALIDATE**: Test login flow and API requests independently
6. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (Login MVP!)
3. Add User Story 3 → Test independently → Deploy/Demo (Full Auth MVP!)
4. Add User Story 2 → Test independently → Deploy/Demo (Session Management)
5. Add User Story 4 → Test independently → Deploy/Demo (Registration)
6. Add User Story 5 → Test independently → Deploy/Demo (Password Reset)
7. Complete Polish → Full feature delivery

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T010)
2. Once Foundational is done:
   - Developer A: User Story 1 (T011-T017)
   - Developer B: User Story 3 (T022-T025)
   - Both P1, can work in parallel
3. After US1 completes:
   - Developer A: User Story 2 (T018-T021)
   - Developer B: Can continue US3 or start US4/US5
4. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Priority: Focus on P1 stories first (US1 + US3) for MVP, then P2 (US2), then P3 (US4, US5)
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence

---

## Summary

**Total Tasks**: 44

**Tasks per User Story**:
- Setup: 3 tasks
- Foundational: 7 tasks
- User Story 1 (P1): 7 tasks
- User Story 2 (P2): 4 tasks
- User Story 3 (P1): 4 tasks
- User Story 4 (P3): 7 tasks
- User Story 5 (P3): 6 tasks
- Polish: 6 tasks

**Parallel Opportunities**:
- Phase 1: 2 parallel tasks (T002, T003)
- Phase 2: 3 parallel tasks (T006, T007, T008)
- Phase 3: 0 parallel tasks (sequential dependencies)
- Phase 4: 0 parallel tasks (sequential dependencies)
- Phase 5: 2 parallel tasks (T022, T023)
- Phase 6: 2 parallel tasks (T026, T027)
- Phase 7: 2 parallel tasks (T033, T034)
- Phase 8: 2 parallel tasks (T039, T040)

**Independent Test Criteria**:
- User Story 1: Can login from landing page to dashboard
- User Story 2: Can logout and handle session expiry
- User Story 3: Can make authenticated API calls
- User Story 4: Can register new account and login
- User Story 5: Can reset password and login with new password

**Suggested MVP Scope**: User Story 1 (正常登录流程) + User Story 3 (API请求鉴权)

**Format Validation**: ✅ ALL tasks follow the checklist format (checkbox, ID, labels, file paths)

---

**Generated**: 2026-01-16
**Based on**: plan.md v1.0.0, spec.md (5 user stories), data-model.md, contracts/auth-api.yaml
**Status**: Ready for Implementation
