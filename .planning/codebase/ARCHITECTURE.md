# Architecture

**Last Updated:** 2026-03-22

## Architecture Pattern

**Full-Stack Monolith** - Single Next.js application handling both frontend and backend

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   Pages     │  │  Components │  │   Context   │          │
│  │  (React)    │  │  (React)    │  │  (State)    │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
└─────────┼────────────────┼────────────────┼─────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Next.js App Router                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   API Routes                          │    │
│  │  /api/auth     /api/character    /api/storyboard    │    │
│  └──────────────────────────┬──────────────────────────┘    │
└─────────────────────────────┼───────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   n8n Server    │
                    │  (Webhooks)     │
                    └─────────────────┘
```

## Layers

### 1. Presentation Layer (Frontend)

**Location:** `film-ai-web/src/app/`, `film-ai-web/src/components/`

- **Pages:** React components for each route
- **Components:** Reusable UI components (forms, results, layout)
- **Context:** Client-side state management

### 2. API Layer (Backend)

**Location:** `film-ai-web/src/app/api/`

- **Route Handlers:** Next.js API routes (serverless functions)
- **Authentication:** Cookie-based session management
- **Validation:** Request validation and error handling

### 3. Integration Layer

**Location:** `film-ai-web/src/lib/`

- **n8n Client:** Webhook calls to n8n server
- **Auth Utilities:** Password hashing, cookie management
- **Context Providers:** React context for state management

## Data Flow

### Character Design Flow

```
User Input → CharacterForm → /api/character → n8n Webhook → AI Processing
                     ↑                                         ↓
            CharacterResult ← Context Provider ← Response ←─┘
```

### Storyboard Generation Flow

```
User Input → StoryboardForm → /api/storyboard → n8n Webhook → AI Processing
                      ↑                                            ↓
            StoryboardResult ← Context Provider ← Response ←─────┘
```

### Authentication Flow

```
Password Input → /api/auth → Cookie Set → Session Validated
       ↑                                         ↓
   PasswordGate ←─────────────────────────────┘
```

## Component Communication

- **Context API:** Used for sharing state between form and result components
- **Props:** Used for layout-level communication (onLogout, onAuthenticated)
- **Server Actions:** Not used (preferring API routes)

## Entry Points

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | `Home` | Character design page |
| `/storyboard` | `StoryboardPage` | Storyboard generation page |
| `/api/auth` | Route handler | Authentication |
| `/api/character` | Route handler | Character design webhook |
| `/api/storyboard` | Route handler | Storyboard webhook |

## State Management

### Client-Side State

- **React Context:** CharacterProvider, StoryboardProvider
- **Local State:** Form data, loading states
- **Session Storage:** Cookie-based auth

### Server-Side State

- **None:** No database or server-side sessions
- **External:** n8n handles all persistent data

## Security Considerations

- Password stored in environment variables
- bcrypt hashing for password verification
- HTTP-only cookies for session
- API routes check authentication before processing
- No sensitive data stored client-side