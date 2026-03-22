# Integrations

**Last Updated:** 2026-03-22

## External Services

### n8n Workflow Automation

**Purpose:** AI-powered character design and storyboard generation

**Connection Details:**
- Base URL: `N8N_BASE_URL` environment variable (default: `http://localhost:5678`)
- Protocol: HTTP REST
- Authentication: None (internal network)

**Webhooks:**

| Webhook | Path | Method | Purpose |
|---------|------|--------|---------|
| Character Design | `/webhook/character-design` | POST | Generate character designs |
| Storyboard | `/webhook/storyboard` | POST | Generate storyboards |

**Implementation:**
- `film-ai-web/src/lib/n8n.ts` - n8n client library
- Functions: `triggerCharacterDesign()`, `triggerStoryboard()`

### Character Design Request Format

```typescript
{
  projectName: string;
  artStyle: 'realistic' | 'anime' | 'chinese' | 'cartoon' | 'oil-painting' | 'watercolor' | 'cyberpunk' | 'fantasy';
  aspectRatio: '16:9' | '9:16' | '1:1' | '4:3' | '21:9';
  characterIntro: string;
}
```

### Character Design Response Format

```typescript
{
  success: boolean;
  data?: {
    characters: Array<{
      name: string;
      description: string;
      costume: string;
      promptTemplate: string;
    }>;
    projectId: string;
  };
  error?: string;
}
```

### Storyboard Request Format

```typescript
{
  projectId: string;
  episodeId: string;
  episodeName: string;
  scriptContent: string;
}
```

### Storyboard Response Format

```typescript
{
  success: boolean;
  data?: {
    scenes: Array<{
      sceneNumber: number;
      description: string;
      keyFrames: string[];
      visualRules: string[];
    }>;
    episodeId: string;
  };
  error?: string;
}
```

## Deployment Infrastructure

### PM2 Process Manager

**Purpose:** Node.js process management

**Configuration:** `film-ai-web/ecosystem.config.js`

### Nginx Reverse Proxy

**Purpose:** HTTP reverse proxy, SSL termination

**Configuration:** `film-ai-web/nginx.conf.example`

## No Database

This application does not use a database. All state is:
- Client-side (React context)
- Session-based (cookies)
- External (n8n workflows)

## Authentication

**Type:** Simple password-based session authentication

**Implementation:**
- `film-ai-web/src/lib/auth.ts` - Server-side auth functions
- Cookie-based session (`film-ai-auth`)
- bcrypt password hashing
- Session expires on browser close