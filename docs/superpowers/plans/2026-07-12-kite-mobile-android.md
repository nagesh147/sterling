# Kite Mobile (Android) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a modular, performance-optimized, and premium React Native (Android) app using Expo and TypeScript that mirrors the Sterling core trading architecture (Kite + Crypto tracks) and replicates its Bloomberg-dark Flat-Pro terminal styling.

**Architecture:** The mobile app will run in the `/mobile` directory, communicating with the existing FastAPI backend (`http://localhost:8000`). It utilizes Zustand for global state, React Native StyleSheet + design tokens for high-density Bloomberg-dark styling, and React Navigation (Expo Router) for file-based navigation.

**Tech Stack:** React Native (0.75+), Expo (SDK 52), Expo Router, TypeScript, Zustand, TanStack Query, React Native Reanimated.

---

### File Structure Map

```
mobile/
├── package.json
├── app.json
├── tsconfig.json
├── app/
│   ├── _layout.tsx                     # Root app layout + context provider setup
│   ├── (tabs)/
│   │   ├── _layout.tsx                 # Tab navigation definition
│   │   ├── index.tsx                   # Kite Tab (Indian Equities/Derivatives)
│   │   ├── crypto.tsx                  # Crypto Tab (Sterling Engine, Grok Signals)
│   │   └── settings.tsx                # App/API Configurations
│   └── order-modal.tsx                 # Full-screen modal for order entry
├── src/
│   ├── components/
│   │   ├── kite/
│   │   │   ├── ConnectPane.tsx         # Kite authentication status
│   │   │   ├── PositionsPane.tsx       # Active holdings & positions
│   │   │   └── OrdersPane.tsx          # Order book pane
│   │   ├── crypto/
│   │   │   ├── EngineStatus.tsx        # Auto-trade & VCP toggles
│   │   │   └── GrokSignalsPane.tsx     # Active signals & tracks
│   │   └── common/
│   │       ├── Card.tsx                # Styled Bloomberg-dark Flat-Pro card
│   │       ├── Toggle.tsx              # Segmented control or switch
│   │       └── Header.tsx              # Screen title + quick status bar
│   ├── store/
│   │   └── useStore.ts                 # Zustand store matching Web app store
│   ├── services/
│   │   ├── api.ts                      # Axios/Fetch wrapper for FastAPI requests
│   │   └── sse.ts                      # EventSource connector for SSE streams
│   └── styles/
│       └── theme.ts                    # UI Tokens (colors, spacing, typography)
```

---

### Task 1: Project Configuration & Bootstrap

**Files:**
- Create: `mobile/package.json`
- Create: `mobile/app.json`
- Create: `mobile/tsconfig.json`

- [ ] **Step 1: Create `mobile/package.json`**
  Write the package definition with necessary Expo, React, React Native, Zustand, TanStack Query, and layout dependencies.

- [ ] **Step 2: Create `mobile/app.json`**
  Define Expo configurations, setting up custom package names, orientation restrictions (portrait-only for dashboard), and splash screen values.

- [ ] **Step 3: Create `mobile/tsconfig.json`**
  Set up TypeScript compiler settings for strict React Native and Expo Router configuration.

- [ ] **Step 4: Commit**
  ```bash
  git add mobile/package.json mobile/app.json mobile/tsconfig.json
  git commit -m "feat(mobile): bootstrap mobile configuration and package files"
  ```

---

### Task 2: Store & API Configuration Layer

**Files:**
- Create: `mobile/src/styles/theme.ts`
- Create: `mobile/src/store/useStore.ts`
- Create: `mobile/src/services/api.ts`

- [ ] **Step 1: Implement `mobile/src/styles/theme.ts`**
  Translate the CSS variables in the web `terminal.css` (Bloomberg-dark) into React Native style variables.

- [ ] **Step 2: Implement `mobile/src/store/useStore.ts`**
  Build the Zustand store managing application settings, connection states, and caching.

- [ ] **Step 3: Implement `mobile/src/services/api.ts`**
  Develop the fetch API wrapper communicating with the FastAPI backend.

- [ ] **Step 4: Commit**
  ```bash
  git add mobile/src/styles/theme.ts mobile/src/store/useStore.ts mobile/src/services/api.ts
  git commit -m "feat(mobile): setup styles, state management and API services"
  ```

---

### Task 3: Navigation Layout and Root App Setup

**Files:**
- Create: `mobile/app/_layout.tsx`
- Create: `mobile/app/(tabs)/_layout.tsx`

- [ ] **Step 1: Implement root layout `mobile/app/_layout.tsx`**
  Define the root layout wrapper wrapping the app in context providers (Zustand store initializer, QueryClientProvider, and SafeAreaProvider).

- [ ] **Step 2: Implement tab layout `mobile/app/(tabs)/_layout.tsx`**
  Configure the bottom tabs navigation (Kite, Crypto, Settings).

- [ ] **Step 3: Commit**
  ```bash
  git add mobile/app/_layout.tsx mobile/app/(tabs)/_layout.tsx
  git commit -m "feat(mobile): build bottom tab navigation and app layouts"
  ```

---

### Task 4: Custom Design Elements and Modals

**Files:**
- Create: `mobile/src/components/common/Card.tsx`
- Create: `mobile/src/components/common/Toggle.tsx`
- Create: `mobile/app/order-modal.tsx`

- [ ] **Step 1: Implement `mobile/src/components/common/Card.tsx`**
  Create reusable card wrappers styling elements with Bloomberg-dark background colors, border styling, and dynamic hover/active states.

- [ ] **Step 2: Implement `mobile/src/components/common/Toggle.tsx`**
  Create custom Segmented Controls or Switches to mirror the Web's Paper/Live and toggle elements.

- [ ] **Step 3: Implement `mobile/app/order-modal.tsx`**
  Create the order placement dialog.

- [ ] **Step 4: Commit**
  ```bash
  git add mobile/src/components/common/Card.tsx mobile/src/components/common/Toggle.tsx mobile/app/order-modal.tsx
  git commit -m "feat(mobile): add cards, toggles and order submission modal"
  ```

---

### Task 5: Kite (Indian Equities/Derivatives) Screen

**Files:**
- Create: `mobile/src/components/kite/ConnectPane.tsx`
- Create: `mobile/src/components/kite/PositionsPane.tsx`
- Create: `mobile/src/components/kite/OrdersPane.tsx`
- Create: `mobile/app/(tabs)/index.tsx`

- [ ] **Step 1: Create `mobile/src/components/kite/ConnectPane.tsx`**
  Add status indicators and controls for Kite session validation.

- [ ] **Step 2: Create `mobile/src/components/kite/PositionsPane.tsx`**
  Build positions component display.

- [ ] **Step 3: Create `mobile/src/components/kite/OrdersPane.tsx`**
  Implement the order logs list.

- [ ] **Step 4: Implement `mobile/app/(tabs)/index.tsx`**
  Assemble the components into the main Kite layout.

- [ ] **Step 5: Commit**
  ```bash
  git add mobile/src/components/kite/ mobile/app/(tabs)/index.tsx
  git commit -m "feat(mobile): construct Zerodha Kite dashboard and order manager"
  ```

---

### Task 6: Crypto & Grok Tab + System Settings

**Files:**
- Create: `mobile/src/components/crypto/EngineStatus.tsx`
- Create: `mobile/src/components/crypto/GrokSignalsPane.tsx`
- Create: `mobile/app/(tabs)/crypto.tsx`
- Create: `mobile/app/(tabs)/settings.tsx`

- [ ] **Step 1: Create `mobile/src/components/crypto/EngineStatus.tsx`**
  Implement controls for algo modes.

- [ ] **Step 2: Create `mobile/src/components/crypto/GrokSignalsPane.tsx`**
  Construct signals table displaying active trade states.

- [ ] **Step 3: Implement `mobile/app/(tabs)/crypto.tsx`**
  Develop the layout for Crypto tab.

- [ ] **Step 4: Implement `mobile/app/(tabs)/settings.tsx`**
  Build settings page for API connection parameters.

- [ ] **Step 5: Commit**
  ```bash
  git add mobile/src/components/crypto/ mobile/app/(tabs)/crypto.tsx mobile/app/(tabs)/settings.tsx
  git commit -m "feat(mobile): add crypto engine, signals monitoring, and API settings screen"
  ```
