# Frontend Design & UI Strategy

**Document:** Frontend Architecture & Design System
**Status:** Living Document
**Last Updated:** 2026-02-09
**Version:** 1.0

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Technology Stack](#technology-stack)
3. [Page Structure](#page-structure)
4. [Component Architecture](#component-architecture)
5. [Visualization Strategy](#visualization-strategy)
6. [State Management](#state-management)
7. [Design System](#design-system)
8. [Routing & Navigation](#routing--navigation)
9. [API Integration](#api-integration)
10. [Performance Considerations](#performance-considerations)
11. [Future Roadmap](#future-roadmap)

---

## Architecture Overview

### **High-Level Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    React SPA (Vite)                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Pages     │  │ Components  │  │  Visualizations     │ │
│  │             │  │             │  │                     │ │
│  │ - Login     │  │ - Header    │  │ - D3ForceGraph      │ │
│  │ - Register  │  │ - NavBar    │  │ - ReactFlowGraph    │ │
│  │ - Dashboard │  │ - DataTable │  │ - CostDashboard     │ │
│  │ - Discovery │  │ - Cards     │  │ - SecurityDashboard │ │
│  │ - Conn List │  │ - Forms     │  │ - SankeyDiagram     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              State Management (React Hooks)              │ │
│  │  - useState (local state)                                │ │
│  │  - useEffect (side effects)                              │ │
│  │  - Context API (global state - future)                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 API Client Layer                         │ │
│  │  - api.js (fetch wrapper)                                │ │
│  │  - Session cookies (httpOnly)                            │ │
│  │  - Error handling                                        │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTPS
┌─────────────────────────────────────────────────────────────┐
│              Agent Orchestrator (FastAPI)                    │
│  - /auth/* (OAuth, email/password)                          │
│  - /me (current user)                                        │
│  - /connections (CRUD)                                       │
│  - /discoveries (create, list, get)                         │
│  - /chat (discovery execution)                              │
└─────────────────────────────────────────────────────────────┘
```

### **Design Principles**

1. **Performance First**: Fast load times, optimized bundles, lazy loading
2. **Mobile Responsive**: Works on desktop, tablet, mobile (future)
3. **Accessibility**: WCAG 2.1 AA compliance (future goal)
4. **Progressive Enhancement**: Core functionality works, visuals enhance
5. **Data-Driven**: Visualizations tell the story, not just tables

---

## Technology Stack

### **Core Framework**

| Technology | Version | Purpose | Why Chosen |
|------------|---------|---------|------------|
| **React** | 18.2+ | UI framework | Industry standard, component model, hooks |
| **Vite** | 5.0+ | Build tool | Fast HMR, modern bundler, ESM-first |
| **React Router** | 6.21+ | Client-side routing | Standard routing solution, nested routes |

### **Visualization Libraries**

| Library | Version | Use Case | Bundle Size |
|---------|---------|----------|-------------|
| **D3.js** | 7.8+ | Custom interactive graphs, force layouts | ~240 KB |
| **React Flow** | 11.10+ | Interactive node graphs, topology | ~180 KB |
| **Recharts** | 2.10+ | Charts (pie, bar, line) for dashboards | ~96 KB |
| **Cytoscape.js** | 3.28+ | (Optional) Alternative graph library | ~280 KB |

**Total visualization bundle:** ~516 KB (gzipped: ~150 KB)

### **Utility Libraries**

| Library | Purpose |
|---------|---------|
| **date-fns** | Date formatting/manipulation |
| **react-icons** | Icon library (Lucide/Feather style) |
| **clsx** | Conditional className utility |

### **Development Tools**

```json
{
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "eslint": "^8.56.0",
    "eslint-plugin-react": "^7.33.2",
    "eslint-plugin-react-hooks": "^4.6.0",
    "prettier": "^3.1.1"
  }
}
```

---

## Page Structure

### **Current Pages (MVP)**

```
/
├── /login                    # Email/password + OAuth buttons
├── /register                 # Email registration with full profile
├── /complete-profile         # OAuth users complete profile
├── /dashboard                # User summary + navigation
├── /discovery                # Run new discovery + see results
└── (404)                     # Catch-all redirect to /login
```

### **Planned Pages (Post-MVP)**

```
/
├── /connections              # List, create, edit, delete connections
├── /connections/:id          # Connection details + subscriptions
├── /discoveries              # Discovery history table
├── /discoveries/:id          # Discovery details with visualizations
├── /discoveries/:id/graph    # Interactive graph topology
├── /tools                    # Tool approval workflow (Phase 4)
├── /settings                 # User settings, preferences
└── /admin                    # Admin panel (future)
```

### **Page Hierarchy**

```
┌─────────────────────────────────────────────────────────┐
│  App.jsx                                                 │
│  ├─ Routes                                               │
│  │  ├─ Public Routes                                     │
│  │  │  ├─ /login          (Login.jsx)                   │
│  │  │  └─ /register       (Register.jsx)                │
│  │  └─ Protected Routes (ProtectedRoute wrapper)        │
│  │     ├─ /complete-profile (CompleteProfile.jsx)       │
│  │     ├─ /dashboard       (Dashboard.jsx)              │
│  │     ├─ /discovery       (Discovery.jsx)              │
│  │     ├─ /connections     (ConnectionsList.jsx)        │
│  │     ├─ /discoveries     (DiscoveriesList.jsx)        │
│  │     └─ /discoveries/:id (DiscoveryDetails.jsx)       │
└─────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### **Component Hierarchy**

```
src/
├── components/
│   ├── layout/
│   │   ├── Header.jsx              # Top navigation bar
│   │   ├── Footer.jsx              # Footer with links
│   │   ├── Sidebar.jsx             # Side navigation (future)
│   │   └── PageLayout.jsx          # Common page wrapper
│   ├── auth/
│   │   ├── OAuthButtons.jsx        # Google/Microsoft OAuth
│   │   ├── LoginForm.jsx           # Email/password form
│   │   └── ProtectedRoute.jsx      # Route guard
│   ├── connections/
│   │   ├── ConnectionCard.jsx      # Single connection display
│   │   ├── ConnectionForm.jsx      # Create/edit connection
│   │   ├── ConnectionTable.jsx     # List of connections
│   │   └── SubscriptionList.jsx    # Show subscriptions
│   ├── discoveries/
│   │   ├── DiscoveryForm.jsx       # Run discovery form
│   │   ├── DiscoveryCard.jsx       # Discovery summary card
│   │   ├── DiscoveryTable.jsx      # Discovery history table
│   │   ├── PlanTimeline.jsx        # 4-stage plan visualization
│   │   └── TraceInfo.jsx           # Trace IDs display
│   ├── visualizations/
│   │   ├── D3ForceGraph.jsx        # D3.js force-directed graph
│   │   ├── ReactFlowGraph.jsx      # React Flow topology
│   │   ├── CostDashboard.jsx       # Recharts cost dashboard
│   │   ├── SecurityDashboard.jsx   # Security findings dashboard
│   │   ├── SankeyDiagram.jsx       # D3 Sankey for cost flow
│   │   └── ResourceTable.jsx       # Expandable resource table
│   ├── shared/
│   │   ├── Button.jsx              # Reusable button component
│   │   ├── Card.jsx                # Card container
│   │   ├── DataTable.jsx           # Generic data table
│   │   ├── LoadingSkeleton.jsx     # Loading state
│   │   ├── ErrorMessage.jsx        # Error display
│   │   ├── Toast.jsx               # Toast notifications
│   │   └── Modal.jsx               # Modal dialog
│   └── charts/
│       ├── PieChart.jsx            # Recharts pie wrapper
│       ├── BarChart.jsx            # Recharts bar wrapper
│       ├── LineChart.jsx           # Recharts line wrapper
│       └── DonutChart.jsx          # Recharts donut wrapper
└── pages/
    ├── Login.jsx
    ├── Register.jsx
    ├── Dashboard.jsx
    ├── Discovery.jsx
    ├── ConnectionsList.jsx
    ├── DiscoveriesList.jsx
    └── DiscoveryDetails.jsx
```

### **Component Patterns**

#### **1. Container/Presenter Pattern**

```jsx
// Container: Handles data fetching and state
const ConnectionsListContainer = () => {
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listConnections()
      .then(setConnections)
      .finally(() => setLoading(false));
  }, []);

  return <ConnectionsTable connections={connections} loading={loading} />;
};

// Presenter: Pure component, just renders
const ConnectionsTable = ({ connections, loading }) => {
  if (loading) return <LoadingSkeleton />;
  return (
    <table>
      {connections.map(conn => <ConnectionRow key={conn.id} {...conn} />)}
    </table>
  );
};
```

#### **2. Compound Components**

```jsx
// Card with sub-components
const Card = ({ children, className }) => (
  <div className={`card ${className}`}>{children}</div>
);

Card.Header = ({ children }) => (
  <div className="card-header">{children}</div>
);

Card.Body = ({ children }) => (
  <div className="card-body">{children}</div>
);

// Usage
<Card>
  <Card.Header>Discovery Results</Card.Header>
  <Card.Body>
    <DiscoveryTable data={data} />
  </Card.Body>
</Card>
```

#### **3. Render Props for Visualizations**

```jsx
const DiscoveryVisualizer = ({ tier, data, children }) => {
  const VisualizerComponent = {
    inventory: D3ForceGraph,
    cost: CostDashboard,
    security: SecurityDashboard
  }[tier];

  return (
    <div className="visualizer">
      {children({ Visualizer: VisualizerComponent, data })}
    </div>
  );
};

// Usage
<DiscoveryVisualizer tier="inventory" data={formatted}>
  {({ Visualizer, data }) => <Visualizer data={data} />}
</DiscoveryVisualizer>
```

---

## Visualization Strategy

### **Three-Tier Approach**

#### **1. D3.js - Custom Interactive Visualizations**

**Use Cases:**
- Resource topology (force-directed graph)
- Cost flow (Sankey diagram)
- Attack surface map (custom layouts)

**Example: Force-Directed Graph**

```jsx
// components/visualizations/D3ForceGraph.jsx
import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

const D3ForceGraph = ({ data, onNodeClick }) => {
  const svgRef = useRef();

  useEffect(() => {
    if (!data) return;

    const { nodes, links } = data;
    const width = 1200;
    const height = 800;

    // Clear previous
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    // Force simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2));

    // Draw links
    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#999')
      .attr('stroke-width', 2);

    // Draw nodes
    const node = svg.append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', d => d.size)
      .attr('fill', d => d.color)
      .on('click', (event, d) => onNodeClick?.(d))
      .call(drag(simulation));

    // Labels
    const label = svg.append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .text(d => d.name)
      .attr('font-size', 12);

    // Update on tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);
      label
        .attr('x', d => d.x)
        .attr('y', d => d.y);
    });

  }, [data, onNodeClick]);

  return <svg ref={svgRef} />;
};
```

#### **2. React Flow - Interactive Node Graphs**

**Use Cases:**
- Editable topology
- Resource dependency explorer
- Network diagram builder

**Example: Resource Topology**

```jsx
// components/visualizations/ReactFlowGraph.jsx
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState
} from 'reactflow';
import 'reactflow/dist/style.css';

const ReactFlowGraph = ({ data }) => {
  const initialNodes = data.nodes.map(n => ({
    id: n.id,
    type: 'default',
    data: { label: n.name },
    position: { x: Math.random() * 500, y: Math.random() * 500 },
    style: { background: n.color, borderRadius: '50%' }
  }));

  const initialEdges = data.links.map((l, i) => ({
    id: `e-${i}`,
    source: l.source,
    target: l.target,
    animated: l.type === 'depends_on'
  }));

  const [nodes] = useNodesState(initialNodes);
  const [edges] = useEdgesState(initialEdges);

  return (
    <div style={{ height: '800px' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
};
```

#### **3. Recharts - Standard Dashboards**

**Use Cases:**
- Cost breakdowns (pie, bar, line)
- Security metrics (severity distribution)
- Resource counts by type/location

**Example: Cost Dashboard**

```jsx
// components/visualizations/CostDashboard.jsx
import {
  PieChart, Pie, Cell,
  BarChart, Bar, XAxis, YAxis,
  LineChart, Line,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const CostDashboard = ({ data }) => {
  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042'];

  return (
    <div className="dashboard-grid">
      {/* Cost by Service - Pie Chart */}
      <div className="chart-card">
        <h3>Cost by Service</h3>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={data.by_service}
              dataKey="cost"
              nameKey="service"
              cx="50%"
              cy="50%"
              outerRadius={100}
              label
            >
              {data.by_service.map((entry, index) => (
                <Cell key={index} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Top Resources - Bar Chart */}
      <div className="chart-card">
        <h3>Top 10 Resources</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data.top_resources}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="cost" fill="#8884d8" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Cost Trend - Line Chart */}
      <div className="chart-card">
        <h3>30-Day Trend</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data.trend_data}>
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="cost" stroke="#8884d8" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
```

### **Visualization Router**

```jsx
// pages/DiscoveryDetails.jsx
const DiscoveryDetails = ({ discoveryId }) => {
  const [discovery, setDiscovery] = useState(null);

  useEffect(() => {
    api.getDiscovery(discoveryId).then(setDiscovery);
  }, [discoveryId]);

  if (!discovery) return <LoadingSkeleton />;

  const { tier, formatted_results } = discovery;

  return (
    <PageLayout>
      <Header title={`${tier} Discovery Results`} />

      {/* Route to tier-specific visualizer */}
      {tier === 'inventory' && (
        <>
          <D3ForceGraph data={formatted_results.graph} />
          <ResourceTable data={formatted_results.by_type} />
        </>
      )}

      {tier === 'cost' && (
        <>
          <CostDashboard data={formatted_results} />
          <SankeyDiagram data={formatted_results.sankey} />
        </>
      )}

      {tier === 'security' && (
        <>
          <SecurityDashboard data={formatted_results} />
          <FindingsTable data={formatted_results.findings} />
        </>
      )}

      <TraceInfo discovery={discovery} />
    </PageLayout>
  );
};
```

---

## State Management

### **Current: React Hooks**

```jsx
// Local state with useState
const [connections, setConnections] = useState([]);
const [loading, setLoading] = useState(false);

// Side effects with useEffect
useEffect(() => {
  api.listConnections()
    .then(setConnections)
    .catch(console.error);
}, []);

// Derived state with useMemo
const activeConnections = useMemo(
  () => connections.filter(c => c.status === 'active'),
  [connections]
);
```

### **Future: Context API for Global State**

```jsx
// contexts/AuthContext.jsx
const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    api.me()
      .then(user => {
        setUser(user);
        setIsAuthenticated(true);
      })
      .catch(() => setIsAuthenticated(false));
  }, []);

  const logout = () => {
    document.cookie = 'access_token=; Max-Age=0';
    setUser(null);
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

// Usage
const Dashboard = () => {
  const { user, logout } = useAuth();
  return (
    <div>
      <p>Welcome, {user.name}</p>
      <button onClick={logout}>Logout</button>
    </div>
  );
};
```

### **Future: React Query for Server State** (Optional)

```bash
npm install @tanstack/react-query
```

```jsx
// Automatic caching, refetching, background updates
import { useQuery } from '@tanstack/react-query';

const DiscoveriesList = () => {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['discoveries'],
    queryFn: () => api.listDiscoveries(),
    staleTime: 60000 // 1 minute
  });

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorMessage error={error} />;

  return <DiscoveryTable discoveries={data} onRefresh={refetch} />;
};
```

---

## Design System

### **Color Palette**

```css
/* Primary Colors */
--color-primary: #0078D4;      /* Azure Blue */
--color-secondary: #50E6FF;    /* Light Blue */
--color-accent: #00B294;       /* Teal */

/* Status Colors */
--color-success: #107C10;      /* Green */
--color-warning: #FFB900;      /* Yellow */
--color-error: #D13438;        /* Red */
--color-info: #0078D4;         /* Blue */

/* Neutral Colors */
--color-gray-50: #F8F8F8;
--color-gray-100: #E1E1E1;
--color-gray-200: #C8C8C8;
--color-gray-700: #323130;
--color-gray-900: #1B1A19;

/* Tier Colors */
--color-inventory: #0078D4;    /* Blue */
--color-cost: #00B294;         /* Teal */
--color-security: #D13438;     /* Red */
```

### **Typography**

```css
/* Font Family */
--font-sans: 'Segoe UI', system-ui, -apple-system, sans-serif;
--font-mono: 'Consolas', 'Monaco', monospace;

/* Font Sizes */
--text-xs: 0.75rem;   /* 12px */
--text-sm: 0.875rem;  /* 14px */
--text-base: 1rem;    /* 16px */
--text-lg: 1.125rem;  /* 18px */
--text-xl: 1.25rem;   /* 20px */
--text-2xl: 1.5rem;   /* 24px */
--text-3xl: 1.875rem; /* 30px */

/* Font Weights */
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;
```

### **Spacing**

```css
/* Spacing Scale (8px base) */
--space-1: 0.25rem;  /* 4px */
--space-2: 0.5rem;   /* 8px */
--space-3: 0.75rem;  /* 12px */
--space-4: 1rem;     /* 16px */
--space-6: 1.5rem;   /* 24px */
--space-8: 2rem;     /* 32px */
--space-12: 3rem;    /* 48px */
--space-16: 4rem;    /* 64px */
```

### **Component Styles**

```css
/* Button */
.button {
  padding: var(--space-2) var(--space-4);
  border-radius: 4px;
  font-weight: var(--font-medium);
  transition: all 0.2s;
}

.button-primary {
  background: var(--color-primary);
  color: white;
}

.button-secondary {
  background: transparent;
  border: 1px solid var(--color-gray-200);
  color: var(--color-gray-700);
}

/* Card */
.card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: var(--space-6);
}

/* Badge */
.badge {
  display: inline-block;
  padding: var(--space-1) var(--space-2);
  border-radius: 12px;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
}

.badge-success { background: #107C10; color: white; }
.badge-warning { background: #FFB900; color: black; }
.badge-error { background: #D13438; color: white; }
```

---

## Routing & Navigation

### **Route Configuration**

```jsx
// App.jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

const App = () => (
  <BrowserRouter>
    <Routes>
      {/* Public Routes */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Protected Routes */}
      <Route element={<ProtectedRoute />}>
        <Route path="/complete-profile" element={<CompleteProfile />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/connections" element={<ConnectionsList />} />
        <Route path="/connections/:id" element={<ConnectionDetails />} />
        <Route path="/discovery" element={<Discovery />} />
        <Route path="/discoveries" element={<DiscoveriesList />} />
        <Route path="/discoveries/:id" element={<DiscoveryDetails />} />
        <Route path="/discoveries/:id/graph" element={<GraphView />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  </BrowserRouter>
);
```

### **Navigation Component**

```jsx
// components/layout/Header.jsx
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

const Header = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="header">
      <div className="header-left">
        <h1>AgenticCloudDisc</h1>
        <nav>
          <Link to="/dashboard">Dashboard</Link>
          <Link to="/connections">Connections</Link>
          <Link to="/discoveries">Discoveries</Link>
        </nav>
      </div>
      <div className="header-right">
        <span>Welcome, {user?.name}</span>
        <button onClick={handleLogout}>Logout</button>
      </div>
    </header>
  );
};
```

---

## API Integration

### **API Client**

```javascript
// api.js
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

async function request(path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    credentials: 'include', // Send cookies
    ...options,
  });

  const contentType = resp.headers.get('content-type') || '';
  const data = contentType.includes('application/json')
    ? await resp.json()
    : {};

  if (!resp.ok) {
    const message = data?.detail || 'Request failed';
    throw new Error(message);
  }

  return data;
}

export const api = {
  // Auth
  loginEmail: (payload) => request('/auth/login-email', { method: 'POST', body: JSON.stringify(payload) }),
  registerEmail: (payload) => request('/auth/register-email', { method: 'POST', body: JSON.stringify(payload) }),
  me: () => request('/me'),

  // Connections
  listConnections: () => request('/connections'),
  getConnection: (id) => request(`/connections/${id}`),
  createConnection: (payload) => request('/connections', { method: 'POST', body: JSON.stringify(payload) }),
  deleteConnection: (id) => request(`/connections/${id}`, { method: 'DELETE' }),

  // Discoveries
  listDiscoveries: () => request('/discoveries'),
  getDiscovery: (id) => request(`/discoveries/${id}`),
  getDiscoveryGraph: (id) => request(`/discoveries/${id}/graph`),
  chat: (payload) => request('/chat', { method: 'POST', body: JSON.stringify(payload) }),
};
```

---

## Performance Considerations

### **Bundle Optimization**

```javascript
// vite.config.js
export default {
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-viz': ['d3', 'recharts', 'reactflow'],
        },
      },
    },
  },
};
```

### **Code Splitting**

```jsx
import { lazy, Suspense } from 'react';

// Lazy load heavy visualization components
const D3ForceGraph = lazy(() => import('./components/visualizations/D3ForceGraph'));
const CostDashboard = lazy(() => import('./components/visualizations/CostDashboard'));

const DiscoveryDetails = () => (
  <Suspense fallback={<LoadingSkeleton />}>
    {tier === 'inventory' && <D3ForceGraph data={data} />}
    {tier === 'cost' && <CostDashboard data={data} />}
  </Suspense>
);
```

### **Image Optimization**

```jsx
// Use WebP with fallback
<picture>
  <source srcSet="/images/logo.webp" type="image/webp" />
  <img src="/images/logo.png" alt="Logo" />
</picture>
```

---

## Future Roadmap

### **Phase 1: Essential UX (Weeks 1-2)**
- [ ] Navigation header with user menu
- [ ] Connections list page
- [ ] Discovery history page
- [ ] Logout functionality

### **Phase 2: Visualizations (Weeks 3-4)**
- [ ] D3.js force graph for inventory
- [ ] Recharts cost dashboard
- [ ] Security findings dashboard
- [ ] Sankey diagram for cost flow

### **Phase 3: Enhanced Features (Weeks 5-6)**
- [ ] Toast notifications
- [ ] Search and filter
- [ ] Export to CSV/PDF
- [ ] Dark mode toggle

### **Phase 4: Advanced (Months 2-3)**
- [ ] React Flow graph editor
- [ ] Comparison view (compare 2 discoveries)
- [ ] Time-based animations
- [ ] Mobile responsive design

---

## Summary

**Current State:**
- ✅ React 18 + Vite setup
- ✅ Basic auth flows (OAuth + email)
- ✅ Protected routing
- ✅ Session management
- ✅ Discovery execution UI

**Visualization Strategy:**
- 🎨 **D3.js** for custom interactivity
- 🎨 **React Flow** for node graphs
- 🎨 **Recharts** for standard charts

**Design System:**
- Azure color palette
- Segoe UI typography
- 8px spacing scale
- Component library (cards, buttons, tables)

**Next Focus:**
1. Build navigation header
2. Create connections/discoveries list pages
3. Implement tier-specific visualizers
4. Add toast notifications

---

**The UI is evolving from functional to visually stunning! 🚀**
