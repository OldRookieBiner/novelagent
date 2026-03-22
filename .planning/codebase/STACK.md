# Tech Stack

**Last Updated:** 2026-03-22

## Languages

- **TypeScript** (primary) - All source code is written in TypeScript
- **JavaScript** - Configuration files and runtime

## Runtime

- **Node.js** 18.x+ - Server runtime
- **Next.js** 16.1.6 - Full-stack React framework with App Router

## Frontend Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.2.3 | UI framework |
| Next.js | 16.1.6 | Full-stack framework |
| Tailwind CSS | 4.x | Utility-first CSS |
| shadcn/ui | 4.0.5 | Component library |
| Lucide React | 0.577.0 | Icon library |
| Base UI React | 1.2.0 | Unstyled UI primitives |

## Backend Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js API Routes | 16.1.6 | Server-side API endpoints |
| bcryptjs | 3.0.3 | Password hashing |
| js-cookie | 3.0.5 | Client-side cookie management |

## Development Tools

| Tool | Purpose |
|------|---------|
| ESLint | Linting |
| TypeScript | Type checking |
| PostCSS | CSS processing |

## Key Configuration Files

- `film-ai-web/package.json` - Dependencies and scripts
- `film-ai-web/tsconfig.json` - TypeScript configuration
- `film-ai-web/next.config.ts` - Next.js configuration
- `film-ai-web/eslint.config.mjs` - ESLint configuration
- `film-ai-web/postcss.config.mjs` - PostCSS configuration

## Scripts

```bash
npm run dev      # Development server
npm run build    # Production build
npm run start    # Production server
npm run lint     # Run ESLint
```

## External Dependencies

- **n8n** - Workflow automation (external service)
- **PM2** - Process management
- **Nginx** - Reverse proxy

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `APP_PASSWORD` | Access password |
| `APP_SECRET` | JWT secret |
| `N8N_BASE_URL` | n8n service URL |
| `N8N_CHARACTER_WEBHOOK` | Character design webhook path |
| `N8N_STORYBOARD_WEBHOOK` | Storyboard webhook path |