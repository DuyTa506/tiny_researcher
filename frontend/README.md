# Frontend Development Guide

Modern Next.js frontend for the Tiny Researcher research assistant.

## Tech Stack

- **Framework**: Next.js 16.1.6 (App Router)
- **Language**: TypeScript
- **UI Library**: React 19
- **State Management**: @tanstack/react-query (server state)
- **Styling**: CSS Modules with design system
- **HTTP Client**: Axios
- **Icons**: lucide-react
- **Markdown**: react-markdown, remark-gfm
- **Charts**: Recharts

## Project Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx         # Root layout + providers
│   │   ├── page.tsx           # Dashboard
│   │   ├── login/             # Authentication pages
│   │   ├── register/
│   │   ├── profile/
│   │   ├── papers/            # Papers list + detail
│   │   ├── reports/           # Reports list + detail
│   │   ├── sessions/          # Sessions list
│   │   └── research/          # Active research session
│   ├── components/
│   │   ├── layout/            # AppShell, Header, Sidebar
│   │   ├── ui/                # Reusable UI (Button, Card, Modal, etc.)
│   │   └── chat/              # Chat components
│   ├── hooks/
│   │   ├── useAuth.tsx        # Authentication context
│   │   └── useResearchChat.ts # SSE research hook
│   ├── services/              # API clients
│   │   ├── api.ts             # Axios instance
│   │   ├── auth.ts            # Auth service
│   │   ├── papers.ts          # Papers service
│   │   ├── reports.ts         # Reports service
│   │   └── conversations.ts   # Sessions service
│   ├── lib/
│   │   ├── types.ts           # TypeScript types (450 lines)
│   │   ├── constants.ts       # App constants
│   │   └── utils.ts           # Utility functions
│   └── styles/
│       └── globals.css        # Global styles + design system
├── public/                     # Static assets
├── Dockerfile
├── next.config.ts
└── package.json
```

## Quick Start

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Access at http://localhost:3000
```

## Environment Variables

Create `.env.local`:

```bash
# API URL (default: /api/v1 for nginx proxy)
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Development Commands

```bash
# Development server (with hot reload)
npm run dev

# Production build
npm run build

# Start production server
npm run start

# Lint
npm run lint

# Type check
npm run type-check
```

## Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard with stats and activity |
| `/login` | Login page |
| `/register` | Registration page |
| `/profile` | User profile and settings |
| `/papers` | Papers list with filters |
| `/papers/[id]` | Paper detail with study card |
| `/reports` | Reports list with search |
| `/reports/[id]` | Report detail with claims |
| `/sessions` | Research sessions list |
| `/research` | Active research session |

## Components

### UI Components (`components/ui/`)

- **Button** - Primary, secondary, ghost, danger variants
- **Card** - Container with optional glass effect
- **Badge** - Color-coded status indicators
- **Input** - Form input with label and error
- **Modal** - Portal-based dialog
- **Skeleton** - Loading placeholders

### Layout Components (`components/layout/`)

- **AppShell** - Main layout wrapper
- **Header** - Top navigation bar
- **Sidebar** - Side navigation

### Chat Components (`components/chat/`)

- **ThinkingBubble** - LLM thinking indicator
- **StreamingText** - Real-time text streaming
- **PlanCard** - Research plan display
- **ActivityLog** - Pipeline activity timeline

## Services

All services use Axios with centralized configuration:

```typescript
// services/api.ts - Base Axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

// Request interceptor injects JWT token
api.interceptors.request.use((config) => {
  const token = authService.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

### Auth Service

```typescript
import { authService } from '@/services/auth';

// Login
await authService.login(email, password);

// Register
await authService.register({ email, username, password });

// Get profile
const user = await authService.getProfile();

// Logout
authService.clearTokens();
```

### Papers Service

```typescript
import { paperService } from '@/services/papers';

// List papers with pagination
const { data } = await paperService.list({
  page: 1,
  page_size: 20,
  status: 'SCREENED',
  keyword: 'transformer',
});

// Create paper
await paperService.create({ title, abstract, authors });

// Delete paper
await paperService.delete(paperId);
```

### Reports Service

```typescript
import { reportService } from '@/services/reports';

// List reports
const { data } = await reportService.list({ page: 1 });

// Export report
await reportService.export(reportId, 'markdown');

// Get claims
const claims = await reportService.getClaims(reportId);
```

## Hooks

### useAuth

```typescript
import { useAuth } from '@/hooks/useAuth';

function MyComponent() {
  const { user, login, logout, isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginForm onSubmit={login} />;
  }

  return <div>Welcome, {user?.username}!</div>;
}
```

### useResearchChat

```typescript
import { useResearchChat } from '@/hooks/useResearchChat';

function ResearchPage() {
  const {
    events,
    sendMessage,
    pipelineStatus,
    pendingApproval,
    approveGate,
  } = useResearchChat();

  return (
    <div>
      {events.map(event => <ChatEvent event={event} />)}
      {pendingApproval && (
        <ApprovalGate
          gate={pendingApproval}
          onApprove={approveGate}
        />
      )}
    </div>
  );
}
```

## Styling

### Design System

Global CSS variables in `globals.css`:

```css
:root {
  /* Colors */
  --primary: #3b82f6;
  --accent: #8b5cf6;
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;

  /* Spacing */
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2rem;

  /* Typography */
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.25rem;
}
```

### CSS Modules

```tsx
import styles from './styles.module.css';

export default function MyComponent() {
  return (
    <div className={styles.container}>
      <h1 className={styles.title}>Title</h1>
    </div>
  );
}
```

## State Management

### React Query

Server state managed with React Query:

```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// Fetch data
const { data, isLoading } = useQuery({
  queryKey: ['papers', { page: 1 }],
  queryFn: () => paperService.list({ page: 1 }),
});

// Mutations
const queryClient = useQueryClient();
const deleteMutation = useMutation({
  mutationFn: paperService.delete,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['papers'] });
  },
});
```

## Docker Build

The frontend uses Next.js standalone output for optimized Docker builds:

```typescript
// next.config.ts
const nextConfig: NextConfig = {
  output: "standalone",
};
```

Build Docker image:

```bash
docker build -t tiny-researcher-frontend .
```

## Troubleshooting

### Build fails

```bash
# Clear Next.js cache
rm -rf .next

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

### Type errors

```bash
# Run type check
npx tsc --noEmit

# Check specific file
npx tsc --noEmit src/app/page.tsx
```

### API connection issues

```bash
# Check API URL
echo $NEXT_PUBLIC_API_URL

# Test backend connection
curl http://localhost:8000/health
```

## Production Build

```bash
# Build for production
npm run build

# Test production build locally
npm run start
```

Build output:
- `.next/standalone/` - Standalone Node.js server
- `.next/static/` - Static assets
- `public/` - Public assets

For full documentation, see the main README.md in the project root.
