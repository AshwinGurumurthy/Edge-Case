# TodoList App

## Overview
A web-based task management application that allows users to create, organize, and track personal to-do items.

## Features
- User registration and login (email + password)
- Create, edit, delete tasks
- Mark tasks as complete / incomplete
- Assign due dates and priority levels (low, medium, high)
- Filter and search tasks by status, priority, or keyword
- Organize tasks into named lists/categories
- Optional task descriptions and notes
- Recurring tasks (daily, weekly, monthly)

## User Workflows
1. **New user**: Sign up → verify email → create first list → add tasks
2. **Returning user**: Log in → view dashboard → check/complete tasks → add new ones
3. **Power user**: Manage multiple lists, use filters, set recurring tasks
4. **Guest**: Browse landing page (no task creation without login)

## Tech Stack
- Frontend: React SPA
- Backend: REST API (Node.js/Express)
- Database: PostgreSQL
- Auth: JWT tokens stored in localStorage
