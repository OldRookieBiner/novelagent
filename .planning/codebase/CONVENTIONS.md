# Code Conventions

**Last Updated:** 2026-03-22

## TypeScript

### Strict Mode

TypeScript strict mode is enabled. All code should be type-safe.

### Type Definitions

```typescript
// Interface for data structures
interface Character {
  name: string;
  description: string;
  costume: string;
  promptTemplate: string;
}

// Type for function parameters
type CharacterFormData = {
  projectName: string;
  artStyle: string;
  aspectRatio: string;
  characterIntro: string;
};
```

### Type Exports

Types are defined alongside implementations:

```typescript
// src/lib/n8n.ts
export interface CharacterDesignRequest { ... }
export interface CharacterDesignResponse { ... }
```

## React Components

### Component Structure

```typescript
'use client'; // Required for client components

import { useState } from 'react';
import { Button } from '@/components/ui/button';

interface ComponentProps {
  // Props definition
}

export function Component({ prop }: ComponentProps) {
  // Hooks at the top
  const [state, setState] = useState(initialState);

  // Event handlers
  const handleClick = () => { ... };

  // Early returns for loading/error states
  if (isLoading) return <Loading />;

  // Main render
  return (
    <div>
      {/* JSX */}
    </div>
  );
}
```

### Client vs Server Components

- **Default:** Server components (no `'use client'`)
- **Client components:** Require interactivity (state, effects, event handlers)
- **API Routes:** Always server-side

### Context Pattern

```typescript
// Create context
const Context = createContext<ContextType | undefined>(undefined);

// Provider component
export function Provider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(initialState);
  return (
    <Context.Provider value={{ state, setState }}>
      {children}
    </Context.Provider>
  );
}

// Custom hook with error checking
export function useContext() {
  const context = useContext(Context);
  if (context === undefined) {
    throw new Error('useContext must be used within Provider');
  }
  return context;
}
```

## Styling

### Tailwind CSS

Utility-first approach with Tailwind classes:

```typescript
<div className="bg-slate-800/50 border-slate-700 text-white">
  <Button className="bg-gradient-to-r from-violet-600 to-purple-600">
    Submit
  </Button>
</div>
```

### Color Scheme

- **Background:** Slate tones (900, 800, 700)
- **Accent:** Violet/Purple gradients
- **Text:** White (primary), slate-300/400 (secondary)

### Component Styling

- Use shadcn/ui components for consistency
- Override with Tailwind classes
- Avoid custom CSS files

## Error Handling

### API Routes

```typescript
export async function POST(request: NextRequest) {
  try {
    // Check authentication
    const authenticated = await isAuthenticated();
    if (!authenticated) {
      return NextResponse.json(
        { success: false, error: 'Unauthorized' },
        { status: 401 }
      );
    }

    // Validate input
    if (!requiredField) {
      return NextResponse.json(
        { success: false, error: 'Missing required fields' },
        { status: 400 }
      );
    }

    // Process request
    const result = await processData(data);
    return NextResponse.json(result);

  } catch (error) {
    console.error('Error:', error);
    return NextResponse.json(
      { success: false, error: 'Internal server error' },
      { status: 500 }
    );
  }
}
```

### Client Components

```typescript
try {
  const response = await fetch('/api/endpoint', { ... });
  const data = await response.json();

  if (data.success) {
    setResult(data);
  } else {
    setError(data.error || '操作失败');
  }
} catch {
  setError('网络错误，请检查连接后重试');
} finally {
  setIsLoading(false);
}
```

## Naming Patterns

| Type | Convention | Example |
|------|------------|---------|
| Components | PascalCase | `CharacterForm` |
| Functions | camelCase | `handleSubmit` |
| Constants | SCREAMING_SNAKE_CASE | `AUTH_COOKIE_NAME` |
| Interfaces | PascalCase | `CharacterDesignRequest` |
| Props types | ComponentNameProps | `CharacterFormProps` |
| Context types | ContextNameType | `CharacterContextType` |

## File Organization

```
ComponentName.tsx
├── Imports (external → internal → types)
├── Types/Interfaces
├── Constants
├── Component function
└── Exports
```

## Best Practices

1. **Single Responsibility:** Each component does one thing well
2. **Composition:** Prefer composition over inheritance
3. **Error Boundaries:** Handle errors gracefully with user feedback
4. **Loading States:** Show loading indicators during async operations
5. **Accessibility:** Use semantic HTML and ARIA attributes
6. **Type Safety:** Avoid `any`, use proper types