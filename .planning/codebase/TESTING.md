# Testing

**Last Updated:** 2026-03-22

## Current State

**No automated tests exist.** This project was bootstrapped with `create-next-app` and does not include a test framework.

## Test Framework

None configured. Options for future implementation:

| Framework | Purpose |
|-----------|---------|
| Jest | Unit testing |
| Vitest | Fast unit testing (Vite-compatible) |
| Playwright | E2E testing |
| Cypress | E2E testing |
| React Testing Library | Component testing |

## Recommended Test Setup

### Unit Tests

For testing utility functions and hooks:

```typescript
// Example: lib/auth.test.ts
import { hashPassword, verifyPassword } from './auth';

describe('auth utilities', () => {
  it('should hash and verify password', async () => {
    const password = 'test-password';
    const hash = await hashPassword(password);
    expect(await verifyPassword(password, hash)).toBe(true);
  });
});
```

### Component Tests

For testing React components:

```typescript
// Example: components/forms/CharacterForm.test.tsx
import { render, screen } from '@testing-library/react';
import { CharacterForm } from './CharacterForm';

describe('CharacterForm', () => {
  it('should render form fields', () => {
    render(<CharacterForm />);
    expect(screen.getByLabelText('项目名称')).toBeInTheDocument();
  });

  it('should disable submit when form is empty', () => {
    render(<CharacterForm />);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

### API Route Tests

For testing API endpoints:

```typescript
// Example: app/api/character/route.test.ts
import { POST } from './route';

describe('POST /api/character', () => {
  it('should return 401 when not authenticated', async () => {
    const request = new Request('http://localhost/api/character', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    const response = await POST(request);
    expect(response.status).toBe(401);
  });
});
```

## Test Coverage Goals

| Layer | Target Coverage |
|-------|-----------------|
| Utility functions | 80%+ |
| API routes | 70%+ |
| Components | 60%+ |

## Manual Testing

Currently, all testing is manual:

1. Start dev server: `npm run dev`
2. Open browser: `http://localhost:3000`
3. Test authentication flow
4. Test character design form
5. Test storyboard generation

## CI/CD Integration

No CI/CD pipeline configured. Recommended setup:

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npm test
      - run: npm run lint
```

## Testing Checklist

When adding tests, cover:

- [ ] Authentication flow (login, logout, session)
- [ ] API route validation (missing fields, unauthorized)
- [ ] Form validation and submission
- [ ] Error handling and user feedback
- [ ] Loading states
- [ ] n8n webhook integration (mocked)

## Mocking Strategy

For n8n integration tests:

```typescript
// Mock the n8n client
jest.mock('@/lib/n8n', () => ({
  triggerCharacterDesign: jest.fn().mockResolvedValue({
    success: true,
    data: { characters: [], projectId: 'test' }
  }),
}));
```