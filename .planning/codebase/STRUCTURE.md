# Structure

**Last Updated:** 2026-03-22

## Directory Layout

```
film-ai-web/
├── src/                      # Source code
│   ├── app/                  # Next.js App Router
│   │   ├── api/              # API routes
│   │   │   ├── auth/         # Authentication endpoint
│   │   │   ├── character/    # Character design endpoint
│   │   │   └── storyboard/   # Storyboard endpoint
│   │   ├── storyboard/       # Storyboard page
│   │   ├── layout.tsx        # Root layout
│   │   └── page.tsx          # Home page
│   ├── components/           # React components
│   │   ├── forms/            # Form components
│   │   ├── results/          # Result display components
│   │   ├── layout/           # Layout components
│   │   └── ui/               # UI primitives (shadcn)
│   └── lib/                  # Utility libraries
│       ├── auth.ts           # Authentication utilities
│       ├── n8n.ts            # n8n client
│       ├── character-context.tsx
│       ├── storyboard-context.tsx
│       └── utils.ts          # General utilities
├── public/                   # Static assets
├── .next/                    # Build output
├── node_modules/             # Dependencies
├── package.json              # Dependencies config
├── tsconfig.json             # TypeScript config
├── next.config.ts            # Next.js config
├── eslint.config.mjs         # ESLint config
├── postcss.config.mjs        # PostCSS config
├── components.json           # shadcn/ui config
├── ecosystem.config.js       # PM2 config
├── nginx.conf.example        # Nginx config template
├── .env.example              # Environment variables template
├── .env.local                # Local environment variables
└── DEPLOYMENT.md             # Deployment guide
```

## Key Files

### Pages

| File | Route | Purpose |
|------|-------|---------|
| `src/app/page.tsx` | `/` | Character design page |
| `src/app/layout.tsx` | - | Root layout with metadata |
| `src/app/storyboard/page.tsx` | `/storyboard` | Storyboard generation page |

### API Routes

| File | Endpoint | Methods |
|------|----------|---------|
| `src/app/api/auth/route.ts` | `/api/auth` | GET, POST |
| `src/app/api/character/route.ts` | `/api/character` | POST |
| `src/app/api/storyboard/route.ts` | `/api/storyboard` | POST |

### Libraries

| File | Purpose |
|------|---------|
| `src/lib/auth.ts` | Password hashing, cookie management |
| `src/lib/n8n.ts` | n8n webhook client |
| `src/lib/character-context.tsx` | Character design state |
| `src/lib/storyboard-context.tsx` | Storyboard state |
| `src/lib/utils.ts` | General utilities (cn function) |

### Components

| Directory | Components | Purpose |
|-----------|------------|---------|
| `components/forms/` | CharacterForm, StoryboardForm | User input forms |
| `components/results/` | CharacterResult, StoryboardResult | Display AI results |
| `components/layout/` | Header, Footer, PasswordGate | Page structure |
| `components/ui/` | Button, Input, Select, etc. | UI primitives |

## Naming Conventions

### Files

- **Components:** PascalCase (e.g., `CharacterForm.tsx`)
- **Utilities:** camelCase (e.g., `auth.ts`)
- **Routes:** lowercase (e.g., `route.ts`)

### Code

- **Components:** PascalCase exports
- **Functions:** camelCase
- **Constants:** SCREAMING_SNAKE_CASE for env-related

### Routes

- **Pages:** lowercase with hyphens
- **API Routes:** lowercase

## Import Patterns

```typescript
// Aliased imports (from tsconfig)
import { Button } from '@/components/ui/button';
import { useCharacter } from '@/lib/character-context';

// Relative imports (same directory)
import { CharacterForm } from './CharacterForm';
```

## Build Output

- `.next/` - Next.js build output
- `node_modules/` - Dependencies
- No custom build scripts beyond Next.js defaults