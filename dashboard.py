"""Command Center v2 — Chat-first interactive dashboard for investor demo."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

dashboard_router = APIRouter()

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autopilot Command Center — Kairox AI</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
    <style>
        /* ============================================ */
        /* DESIGN SYSTEM — Linear.app Inspired         */
        /* ============================================ */

        :root {
            /* Colors — Neutral Scale */
            --color-bg-primary: #06060b;
            --color-bg-secondary: #0a0a14;
            --color-bg-tertiary: #0d0d1a;
            --color-bg-elevated: rgba(26, 26, 48, 0.8);
            --color-bg-card: #0d0d1a;

            /* Colors — Semantic */
            --color-primary: #6366f1;
            --color-primary-hover: #818cf8;
            --color-primary-subtle: #6366f120;
            --color-success: #22c55e;
            --color-success-hover: #16a34a;
            --color-warning: #f59e0b;
            --color-danger: #ef4444;
            --color-info: #06b6d4;

            /* Colors — Text */
            --color-text-primary: #e0e0f0;
            --color-text-secondary: #c8c8e0;
            --color-text-tertiary: #8888aa;
            --color-text-muted: #6b7280;
            --color-text-disabled: #555;

            /* Typography */
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-size-xs: 10px;
            --font-size-sm: 12px;
            --font-size-base: 14px;
            --font-size-lg: 16px;
            --font-size-xl: 20px;
            --font-size-2xl: 24px;
            --font-size-3xl: 32px;
            --font-size-4xl: 48px;

            --font-weight-normal: 400;
            --font-weight-medium: 500;
            --font-weight-semibold: 600;
            --font-weight-bold: 700;
            --font-weight-extrabold: 800;

            /* Spacing — 4px base unit */
            --space-1: 4px;
            --space-2: 8px;
            --space-3: 12px;
            --space-4: 16px;
            --space-5: 20px;
            --space-6: 24px;
            --space-8: 32px;
            --space-10: 40px;
            --space-12: 48px;
            --space-16: 64px;

            /* Border Radius */
            --radius-sm: 6px;
            --radius-md: 8px;
            --radius-lg: 10px;
            --radius-xl: 12px;
            --radius-2xl: 16px;
            --radius-full: 9999px;

            /* Shadows — Linear-inspired elevation */
            --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.2);
            --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.4);
            --shadow-lg: 0 12px 24px rgba(0, 0, 0, 0.5);
            --shadow-xl: 0 20px 40px rgba(0, 0, 0, 0.6);

            /* Transitions */
            --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
            --transition-base: 200ms cubic-bezier(0.4, 0, 0.2, 1);
            --transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1);

            /* Glassmorphism */
            --glass-border: 1px solid rgba(255, 255, 255, 0.08);
            --glass-bg: rgba(13, 13, 26, 0.6);
            --glass-bg-hover: rgba(26, 26, 48, 0.8);
            --glass-blur: blur(12px);

            /* Z-index layers */
            --z-dropdown: 1000;
            --z-modal: 2000;
            --z-toast: 3000;
        }

        *, *::before, *::after {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        html, body {
            height: 100%;
            overflow: hidden;
        }

        body {
            font-family: var(--font-sans);
            background: var(--color-bg-primary);
            color: var(--color-text-secondary);
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        /* ── Glassmorphism Components ──────────────── */
        .glass-card {
            background: var(--glass-bg);
            backdrop-filter: var(--glass-blur);
            border: var(--glass-border);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-md);
            transition: all var(--transition-base);
        }

        .glass-card:hover {
            background: var(--glass-bg-hover);
            border-color: rgba(99, 102, 241, 0.3);
            box-shadow: var(--shadow-lg);
            transform: translateY(-2px);
        }

        .glass-card.clickable {
            cursor: pointer;
        }

        /* ── Interactive State System ──────────────── */
        .interactive {
            cursor: pointer;
            user-select: none;
            transition: all var(--transition-fast);
        }

        .interactive:hover {
            transform: scale(1.02);
        }

        .interactive:active {
            transform: scale(0.98);
        }

        /* ── Skeleton Loading ──────────────────────── */
        .skeleton {
            background: linear-gradient(
                90deg,
                var(--color-bg-tertiary) 0%,
                rgba(99, 102, 241, 0.1) 50%,
                var(--color-bg-tertiary) 100%
            );
            background-size: 200% 100%;
            animation: skeleton-loading 1.5s ease-in-out infinite;
            border-radius: var(--radius-md);
        }

        @keyframes skeleton-loading {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }

        /* ── Layout ──────────────────────────────────────── */
        .app-layout {
            display: flex; height: 100vh; width: 100vw;
        }

        /* ── Sidebar ─────────────────────────────────────── */
        .sidebar {
            width: 64px; min-width: 64px;
            background: var(--color-bg-secondary);
            border-right: var(--glass-border);
            display: flex; flex-direction: column; align-items: center;
            padding: var(--space-3) 0;
            z-index: 10;
        }
        .sidebar-logo {
            width: 40px; height: 40px; border-radius: 10px;
            background: linear-gradient(135deg, #6366f1, #7C3AED);
            display: flex; align-items: center; justify-content: center;
            font-weight: 800; font-size: 20px; color: #fff;
            margin-bottom: 20px; cursor: pointer;
        }
        .sidebar-divider {
            width: 32px; height: 1px; background: #1a1a30; margin: 8px 0;
        }
        .sidebar-btn {
            width: 44px; height: 44px; border-radius: var(--radius-lg);
            display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: all var(--transition-fast);
            color: var(--color-text-disabled); font-size: 20px; position: relative;
            border: none; background: none; margin: var(--space-1) 0;
        }
        .sidebar-btn:hover {
            background: var(--color-bg-tertiary);
            color: var(--color-primary-hover);
            transform: scale(1.1);
        }
        .sidebar-btn.active {
            background: var(--color-primary-subtle);
            color: var(--color-primary-hover);
            box-shadow: var(--shadow-sm);
        }
        .sidebar-btn .tooltip {
            position: absolute; left: 56px; top: 50%; transform: translateY(-50%);
            background: var(--glass-bg-hover);
            backdrop-filter: var(--glass-blur);
            color: var(--color-text-primary);
            padding: var(--space-1) var(--space-3);
            border-radius: var(--radius-sm);
            font-size: var(--font-size-sm);
            font-weight: var(--font-weight-medium);
            white-space: nowrap;
            pointer-events: none;
            opacity: 0;
            transition: opacity var(--transition-fast);
            border: var(--glass-border);
            box-shadow: var(--shadow-lg);
        }
        .sidebar-btn:hover .tooltip {
            opacity: 1;
            animation: tooltipSlideIn var(--transition-base) ease-out;
        }

        @keyframes tooltipSlideIn {
            from {
                opacity: 0;
                transform: translate(-4px, -50%);
            }
            to {
                opacity: 1;
                transform: translate(0, -50%);
            }
        }
        .sidebar-status {
            margin-top: auto; margin-bottom: 8px;
            display: flex; flex-direction: column; align-items: center; gap: 4px;
        }
        .status-dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: #22c55e;
            animation: pulse 2s ease-in-out infinite;
            box-shadow: 0 0 6px #22c55e80;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(0.85); }
        }
        .status-label { font-size: 9px; color: #555; text-transform: uppercase; letter-spacing: 0.5px; }

        /* ── Main Area ───────────────────────────────────── */
        .main-area {
            flex: 1; display: flex; flex-direction: column; min-width: 0;
        }

        /* ── Header Bar ──────────────────────────────────── */
        .header-bar {
            height: 48px;
            min-height: 48px;
            background: var(--color-bg-secondary);
            border-bottom: var(--glass-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 var(--space-5);
            backdrop-filter: var(--glass-blur);
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: var(--space-3);
        }

        .header-brand {
            font-size: var(--font-size-lg);
            font-weight: var(--font-weight-bold);
            color: var(--color-text-primary);
        }

        .header-sub {
            font-size: var(--font-size-sm);
            color: var(--color-primary);
            font-weight: var(--font-weight-medium);
        }

        .header-right {
            display: flex;
            align-items: center;
            gap: var(--space-4);
            font-size: var(--font-size-sm);
            color: var(--color-text-muted);
        }

        .header-status {
            display: flex;
            align-items: center;
            gap: var(--space-2);
            padding: var(--space-1) var(--space-3);
            background: rgba(34, 197, 94, 0.1);
            border-radius: var(--radius-full);
            cursor: pointer;
            transition: all var(--transition-fast);
        }

        .header-status:hover {
            background: rgba(34, 197, 94, 0.15);
        }

        .header-status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--color-success);
        }

        .header-uptime {
            font-variant-numeric: tabular-nums;
            font-family: 'SF Mono', 'Monaco', 'Courier New', monospace;
        }

        /* ── View Container ──────────────────────────────── */
        .view-container {
            flex: 1; overflow: hidden; position: relative;
        }
        .view {
            position: absolute; inset: 0;
            display: none; flex-direction: column;
            overflow: hidden;
        }
        .view.active { display: flex; }

        /* ── Common Elements ──────────────────────────────── */
        .btn {
            height: 32px;
            padding: 0 var(--space-4);
            border: none;
            border-radius: var(--radius-sm);
            font-family: inherit;
            font-size: var(--font-size-sm);
            font-weight: var(--font-weight-semibold);
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: var(--space-2);
            transition: all var(--transition-fast);
            box-shadow: var(--shadow-xs);
        }

        .btn:hover {
            transform: translateY(-1px);
            box-shadow: var(--shadow-sm);
        }

        .btn:active {
            transform: translateY(0);
            box-shadow: var(--shadow-xs);
        }

        .btn-primary {
            background: var(--color-primary);
            color: #fff;
        }
        .btn-primary:hover {
            background: var(--color-primary-hover);
        }

        .btn-success {
            background: var(--color-success);
            color: #fff;
        }
        .btn-success:hover {
            background: var(--color-success-hover);
        }

        .btn-danger {
            background: var(--color-danger);
            color: #fff;
        }
        .btn-danger:hover {
            background: #dc2626;
        }

        .btn-ghost {
            background: transparent;
            color: var(--color-text-tertiary);
            border: var(--glass-border);
            box-shadow: none;
        }
        .btn-ghost:hover {
            background: var(--color-bg-tertiary);
            color: var(--color-text-secondary);
            border-color: rgba(99, 102, 241, 0.3);
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
        }
        .btn .spinner {
            width: 14px; height: 14px; border: 2px solid transparent;
            border-top-color: currentColor; border-radius: 50%;
            animation: spin 0.6s linear infinite; display: inline-block;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .badge {
            display: inline-flex;
            align-items: center;
            padding: var(--space-1) var(--space-2);
            border-radius: var(--radius-full);
            font-size: var(--font-size-xs);
            font-weight: var(--font-weight-semibold);
            border: 1px solid transparent;
            transition: all var(--transition-fast);
        }

        .badge-indigo {
            background: var(--color-primary-subtle);
            color: var(--color-primary-hover);
            border-color: rgba(99, 102, 241, 0.3);
        }

        .badge-green {
            background: rgba(34, 197, 94, 0.15);
            color: #4ade80;
            border-color: rgba(34, 197, 94, 0.3);
        }

        .badge-red {
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border-color: rgba(239, 68, 68, 0.3);
        }

        .badge-yellow {
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border-color: rgba(245, 158, 11, 0.3);
        }

        .badge-cyan {
            background: rgba(6, 182, 212, 0.15);
            color: #22d3ee;
            border-color: rgba(6, 182, 212, 0.3);
        }
        .card {
            background: var(--color-bg-card);
            border: var(--glass-border);
            border-radius: var(--radius-lg);
            padding: var(--space-4);
            position: relative;
            overflow: hidden;
            transition: all var(--transition-base);
        }

        .card-glass {
            background: var(--glass-bg);
            backdrop-filter: var(--glass-blur);
            border: var(--glass-border);
            border-radius: var(--radius-lg);
            padding: var(--space-4);
        }

        .card:hover {
            border-color: rgba(99, 102, 241, 0.2);
        }
        .filter-chip {
            font-family: inherit;
            font-size: var(--font-size-xs);
            padding: var(--space-1) var(--space-3);
            border-radius: var(--radius-full);
            background: var(--color-bg-tertiary);
            color: var(--color-text-muted);
            border: 1px solid transparent;
            cursor: pointer;
            transition: all var(--transition-fast);
            font-weight: var(--font-weight-medium);
        }

        .filter-chip.active {
            background: var(--color-primary-subtle);
            color: var(--color-primary-hover);
            border-color: var(--color-primary);
        }

        .filter-chip:hover {
            border-color: rgba(99, 102, 241, 0.5);
            background: rgba(99, 102, 241, 0.1);
        }

        .section-title {
            font-size: var(--font-size-lg);
            font-weight: var(--font-weight-bold);
            color: var(--color-text-primary);
        }

        .tabular {
            font-variant-numeric: tabular-nums;
        }

        /* ── Scrollbar Styling ──────────────────────────── */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: var(--color-primary-subtle);
            border-radius: var(--radius-full);
            transition: background var(--transition-fast);
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(99, 102, 241, 0.4);
        }

        /* ── Utility Classes ─────────────────────────────── */
        .text-primary { color: var(--color-text-primary); }
        .text-secondary { color: var(--color-text-secondary); }
        .text-tertiary { color: var(--color-text-tertiary); }
        .text-muted { color: var(--color-text-muted); }

        .bg-elevated { background: var(--color-bg-elevated); }

        /* Smooth scroll */
        html {
            scroll-behavior: smooth;
        }

        /* Reduce motion for accessibility */
        @media (prefers-reduced-motion: reduce) {
            *,
            *::before,
            *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
        }

        /* ── View 1: Chat ────────────────────────────────── */
        .chat-view {
            display: flex;
            flex-direction: column;
        }

        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: var(--space-5) var(--space-6);
            display: flex;
            flex-direction: column;
            gap: var(--space-4);
        }

        .chat-empty {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: var(--space-6);
            padding: var(--space-10);
        }

        .chat-empty-title {
            font-size: var(--font-size-xl);
            font-weight: var(--font-weight-bold);
            color: var(--color-text-primary);
        }

        .chat-empty-sub {
            font-size: var(--font-size-base);
            color: var(--color-text-muted);
            text-align: center;
            max-width: 400px;
            line-height: 1.5;
        }

        .prompt-cards {
            display: flex;
            gap: var(--space-3);
            flex-wrap: wrap;
            justify-content: center;
        }

        .prompt-card {
            background: var(--glass-bg);
            backdrop-filter: var(--glass-blur);
            border: var(--glass-border);
            border-radius: var(--radius-lg);
            padding: var(--space-4);
            cursor: pointer;
            transition: all var(--transition-base);
            max-width: 260px;
            font-size: var(--font-size-sm);
            color: var(--color-primary-hover);
            line-height: 1.4;
        }

        .prompt-card:hover {
            border-color: var(--color-primary);
            background: var(--color-primary-subtle);
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }

        .msg {
            max-width: 85%;
            animation: msgIn var(--transition-slow) ease-out;
        }

        @keyframes msgIn {
            from {
                opacity: 0;
                transform: translateY(8px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .msg-user {
            align-self: flex-end;
            background: linear-gradient(135deg, var(--color-primary), #818cf8);
            color: #fff;
            border-radius: 16px 16px 4px 16px;
            padding: var(--space-3) var(--space-4);
            font-size: var(--font-size-base);
            line-height: 1.5;
            box-shadow: var(--shadow-sm);
        }

        .msg-assistant {
            align-self: flex-start;
            background: var(--glass-bg);
            backdrop-filter: var(--glass-blur);
            border: var(--glass-border);
            border-radius: 16px 16px 16px 4px;
            padding: var(--space-4);
            font-size: var(--font-size-base);
            line-height: 1.6;
            color: var(--color-text-primary);
            box-shadow: var(--shadow-sm);
        }

        .msg-assistant p {
            margin-bottom: var(--space-2);
        }

        .msg-assistant p:last-child {
            margin-bottom: 0;
        }

        .msg-assistant ul,
        .msg-assistant ol {
            margin: var(--space-1) 0 var(--space-2) var(--space-5);
        }

        .msg-assistant li {
            margin-bottom: var(--space-1);
        }

        .msg-assistant strong {
            color: var(--color-text-primary);
            font-weight: var(--font-weight-semibold);
        }

        .msg-assistant code {
            background: var(--color-bg-tertiary);
            padding: var(--space-1) var(--space-2);
            border-radius: var(--radius-sm);
            font-size: var(--font-size-sm);
            color: var(--color-primary-hover);
            border: 1px solid rgba(99, 102, 241, 0.2);
        }

        .tool-block {
            background: var(--color-bg-tertiary);
            border: var(--glass-border);
            border-radius: var(--radius-md);
            margin: var(--space-2) 0;
            overflow: hidden;
            font-size: var(--font-size-sm);
            transition: all var(--transition-base);
        }

        .tool-block:hover {
            border-color: rgba(99, 102, 241, 0.3);
        }

        .tool-header {
            display: flex;
            align-items: center;
            gap: var(--space-2);
            padding: var(--space-2) var(--space-3);
            border-bottom: var(--glass-border);
            background: rgba(0, 0, 0, 0.2);
        }

        .tool-icon {
            font-size: var(--font-size-base);
        }

        .tool-name {
            color: var(--color-primary-hover);
            font-weight: var(--font-weight-semibold);
        }

        .tool-status {
            margin-left: auto;
            font-size: var(--font-size-xs);
            display: flex;
            align-items: center;
            gap: var(--space-1);
        }

        .tool-status.running {
            color: var(--color-warning);
        }

        .tool-status.done {
            color: var(--color-success);
        }

        .tool-status.error {
            color: var(--color-danger);
        }

        .tool-body {
            padding: var(--space-2) var(--space-3);
            color: var(--color-text-muted);
            font-family: 'SF Mono', 'Monaco', 'Courier New', monospace;
            font-size: var(--font-size-xs);
        }

        .tool-body.hidden {
            display: none;
        }

        .chat-input-area {
            padding: var(--space-3) var(--space-5) var(--space-4);
            border-top: var(--glass-border);
            background: var(--color-bg-secondary);
        }

        .chat-input-row {
            display: flex;
            gap: var(--space-2);
            align-items: flex-end;
        }

        .chat-textarea {
            flex: 1;
            background: var(--color-bg-tertiary);
            border: var(--glass-border);
            border-radius: var(--radius-lg);
            padding: var(--space-3);
            color: var(--color-text-primary);
            font-family: inherit;
            font-size: var(--font-size-base);
            resize: none;
            outline: none;
            min-height: 42px;
            max-height: 120px;
            transition: all var(--transition-fast);
        }

        .chat-textarea:focus {
            border-color: var(--color-primary);
            background: var(--color-bg-card);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }

        .chat-textarea::placeholder {
            color: var(--color-text-disabled);
        }

        .chat-send {
            width: 42px;
            height: 42px;
            border-radius: var(--radius-lg);
            background: linear-gradient(135deg, var(--color-primary), #818cf8);
            border: none;
            color: #fff;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all var(--transition-fast);
            font-size: 18px;
            flex-shrink: 0;
            box-shadow: var(--shadow-sm);
        }

        .chat-send:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }

        .chat-send:active {
            transform: translateY(0);
        }

        .chat-send:disabled {
            opacity: 0.4;
            cursor: not-allowed;
            transform: none !important;
        }
        .typing-indicator { display: none; align-self: flex-start; padding: 10px 16px; }
        .typing-indicator.show { display: flex; }
        .typing-dots { display: flex; gap: 4px; }
        .typing-dots span {
            width: 6px; height: 6px; border-radius: 50%; background: #6366f1;
            animation: typingBounce 1.4s ease-in-out infinite;
        }
        .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typingBounce {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-6px); }
        }

        /* ── View 2: Pipeline ────────────────────────────── */
        .pipeline-view {
            overflow-y: auto;
            padding: var(--space-5) var(--space-6);
            gap: var(--space-5);
        }

        .pipeline-svg-wrap {
            background: var(--color-bg-card);
            border: var(--glass-border);
            border-radius: var(--radius-xl);
            padding: var(--space-6);
            text-align: center;
            position: relative;
        }

        .pipeline-svg {
            max-width: 100%;
            height: auto;
        }

        .pipeline-metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: var(--space-3);
        }

        .metric-card {
            background: var(--glass-bg);
            backdrop-filter: var(--glass-blur);
            border: var(--glass-border);
            border-radius: var(--radius-lg);
            padding: var(--space-4);
            display: flex;
            flex-direction: column;
            gap: var(--space-1);
            position: relative;
            overflow: hidden;
            cursor: pointer;
            transition: all var(--transition-base);
        }

        .metric-card:hover {
            border-color: rgba(99, 102, 241, 0.3);
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
        }

        .metric-card.mc-blue::before { background: #3b82f6; }
        .metric-card.mc-purple::before { background: #8b5cf6; }
        .metric-card.mc-green::before { background: var(--color-success); }
        .metric-card.mc-yellow::before { background: var(--color-warning); }
        .metric-card.mc-cyan::before { background: var(--color-info); }
        .metric-card.mc-indigo::before { background: var(--color-primary); }

        .metric-label {
            font-size: var(--font-size-xs);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--color-text-muted);
            font-weight: var(--font-weight-semibold);
        }

        .metric-value {
            font-size: var(--font-size-3xl);
            font-weight: var(--font-weight-extrabold);
            color: var(--color-text-primary);
            font-variant-numeric: tabular-nums;
            line-height: 1.1;
        }

        .metric-sub {
            font-size: var(--font-size-xs);
            color: var(--color-text-disabled);
        }

        .pipeline-actions {
            display: flex;
            align-items: center;
            gap: var(--space-3);
        }

        /* Agent Detail Panel (Bottom Sheet) */
        .agent-detail-panel {
            position: fixed;
            bottom: 0;
            left: 64px;
            right: 0;
            height: 0;
            background: var(--glass-bg-hover);
            backdrop-filter: var(--glass-blur);
            border-top: var(--glass-border);
            box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.6);
            z-index: 100;
            overflow: hidden;
            transition: height var(--transition-slow);
        }

        .agent-detail-panel.open {
            height: 400px;
        }

        .agent-detail-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: var(--space-4) var(--space-6);
            border-bottom: var(--glass-border);
        }

        .agent-detail-title {
            font-size: var(--font-size-lg);
            font-weight: var(--font-weight-bold);
            color: var(--color-text-primary);
            display: flex;
            align-items: center;
            gap: var(--space-2);
        }

        .agent-detail-close {
            width: 32px;
            height: 32px;
            border-radius: var(--radius-md);
            background: transparent;
            border: var(--glass-border);
            color: var(--color-text-tertiary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all var(--transition-fast);
            font-size: 20px;
        }

        .agent-detail-close:hover {
            background: var(--color-bg-tertiary);
            color: var(--color-text-primary);
        }

        .agent-detail-content {
            padding: var(--space-6);
            overflow-y: auto;
            height: calc(400px - 60px);
        }

        .agent-detail-section {
            margin-bottom: var(--space-6);
        }

        .agent-detail-section-title {
            font-size: var(--font-size-sm);
            font-weight: var(--font-weight-semibold);
            color: var(--color-text-secondary);
            margin-bottom: var(--space-3);
        }

        .agent-work-item {
            background: var(--color-bg-tertiary);
            border: var(--glass-border);
            border-radius: var(--radius-md);
            padding: var(--space-3);
            margin-bottom: var(--space-2);
            font-size: var(--font-size-sm);
        }

        .agent-work-item-title {
            font-weight: var(--font-weight-medium);
            color: var(--color-text-primary);
            margin-bottom: var(--space-1);
        }

        .agent-work-item-meta {
            font-size: var(--font-size-xs);
            color: var(--color-text-muted);
        }

        /* ── View 3: Discoveries ─────────────────────────── */
        .disc-view { overflow-y: auto; padding: 20px 24px; gap: 16px; }
        .disc-filters { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .disc-table { width: 100%; border-collapse: collapse; }
        .disc-table th {
            text-align: left; padding: 8px 12px; font-size: 11px; font-weight: 600;
            color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;
            border-bottom: 1px solid #1a1a30;
        }
        .disc-table td {
            padding: 10px 12px; font-size: 13px; border-bottom: 1px solid #1a1a3020;
            vertical-align: top;
        }
        .disc-table tr { cursor: pointer; transition: background 0.1s; }
        .disc-table tr:hover { background: #6366f108; }
        .disc-expand {
            display: none; padding: 12px 16px; background: #0a0a14;
            border-bottom: 1px solid #1a1a30;
        }
        .disc-expand.open { display: table-row; }
        .score-bar {
            width: 60px; height: 4px; background: #1a1a30; border-radius: 2px;
            display: inline-block; vertical-align: middle; margin-left: 6px;
        }
        .score-fill { height: 100%; border-radius: 2px; }
        .source-badge {
            font-size: var(--font-size-xs);
            padding: var(--space-1) var(--space-2);
            border-radius: var(--radius-sm);
            font-weight: var(--font-weight-semibold);
            display: inline-block;
            border: 1px solid;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }

        .source-hackernews {
            background: rgba(255, 102, 0, 0.15);
            color: #ff9040;
            border-color: rgba(255, 102, 0, 0.3);
        }

        .source-reddit {
            background: rgba(255, 69, 0, 0.15);
            color: #ff7060;
            border-color: rgba(255, 69, 0, 0.3);
        }

        .source-github_trending {
            background: rgba(240, 246, 252, 0.1);
            color: #8b949e;
            border-color: rgba(139, 148, 158, 0.3);
        }

        .source-lobsters {
            background: rgba(130, 32, 0, 0.15);
            color: #cc5050;
            border-color: rgba(130, 32, 0, 0.3);
        }

        .source-arxiv {
            background: rgba(179, 27, 27, 0.15);
            color: #e04040;
            border-color: rgba(179, 27, 27, 0.3);
        }

        .source-company_blogs {
            background: var(--color-primary-subtle);
            color: var(--color-primary-hover);
            border-color: rgba(99, 102, 241, 0.3);
        }

        .source-producthunt {
            background: rgba(218, 85, 47, 0.15);
            color: #da7050;
            border-color: rgba(218, 85, 47, 0.3);
        }

        /* Platform-specific badges for publications */
        .source-linkedin {
            background: rgba(10, 102, 194, 0.15);
            color: #60a5fa;
            border-color: rgba(10, 102, 194, 0.3);
        }

        .source-twitter, .source-x {
            background: rgba(29, 155, 240, 0.15);
            color: #60a5fa;
            border-color: rgba(29, 155, 240, 0.3);
        }

        .source-youtube {
            background: rgba(255, 0, 0, 0.15);
            color: #ff6b6b;
            border-color: rgba(255, 0, 0, 0.3);
        }

        .source-medium {
            background: rgba(255, 255, 255, 0.1);
            color: #e0e0e0;
            border-color: rgba(255, 255, 255, 0.2);
        }

        .source-tiktok {
            background: rgba(255, 0, 80, 0.15);
            color: #ff6b9d;
            border-color: rgba(255, 0, 80, 0.3);
        }
        .risk-low { color: #22c55e; }
        .risk-medium { color: #f59e0b; }
        .risk-high { color: #ef4444; }

        /* ── Approval Queue Redesign ───────────────────────── */
        .approval-filter-bar {
            display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 4px;
        }
        .approval-filter-pill {
            padding: 6px 14px; border-radius: var(--radius-full);
            font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold);
            cursor: pointer; border: 1px solid rgba(255,255,255,0.1);
            background: transparent; color: var(--color-text-tertiary);
            transition: all var(--transition-fast);
        }
        .approval-filter-pill:hover {
            background: rgba(255,255,255,0.05); color: var(--color-text-secondary);
        }
        .approval-filter-pill.active {
            background: var(--color-primary); color: #fff;
            border-color: var(--color-primary);
        }
        .approval-group {
            background: var(--color-bg-card); border: var(--glass-border);
            border-radius: var(--radius-lg); overflow: hidden;
        }
        .approval-group-header {
            display: flex; align-items: center; gap: 10px; padding: 14px 16px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .approval-group-header .source-title {
            font-size: 13px; color: var(--color-text-secondary);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            max-width: 460px;
        }
        .approval-group-header .format-badge {
            font-size: 10px; padding: 2px 8px; border-radius: var(--radius-full);
            background: rgba(255,255,255,0.06); color: var(--color-text-tertiary);
            font-weight: 500; text-transform: lowercase;
        }
        .approval-group-header .timestamp {
            font-size: 11px; color: #555; margin-left: auto; white-space: nowrap;
        }
        .approval-group-header .btn-reject-group {
            background: transparent; color: var(--color-text-tertiary);
            border: 1px solid rgba(239,68,68,0.25); font-size: 11px;
            padding: 4px 12px; border-radius: var(--radius-sm); cursor: pointer;
            font-weight: 500; transition: all var(--transition-fast); margin-left: 8px;
        }
        .approval-group-header .btn-reject-group:hover {
            background: rgba(239,68,68,0.12); color: #f87171;
            border-color: rgba(239,68,68,0.5);
        }
        .approval-variants-grid {
            display: grid; grid-template-columns: repeat(2, 1fr); gap: 0;
        }
        .approval-variant {
            padding: 16px; border-left: 4px solid transparent;
            position: relative;
        }
        .approval-variant:first-child {
            border-right: 1px solid rgba(255,255,255,0.06);
        }
        .approval-variant.variant-a {
            border-left-color: #6366f1;
            background: rgba(99,102,241,0.03);
        }
        .approval-variant.variant-b {
            border-left-color: #10b981;
            background: rgba(16,185,129,0.03);
        }
        .variant-label {
            display: inline-flex; align-items: center; justify-content: center;
            width: 24px; height: 24px; border-radius: var(--radius-sm);
            font-size: 12px; font-weight: 700; margin-bottom: 8px;
        }
        .variant-a .variant-label {
            background: rgba(99,102,241,0.2); color: #818cf8;
        }
        .variant-b .variant-label {
            background: rgba(16,185,129,0.2); color: #34d399;
        }
        .variant-title {
            font-size: 15px; font-weight: 600; color: var(--color-text-primary);
            margin-bottom: 10px; line-height: 1.3;
        }
        .approval-image {
            width: 100%; max-height: 240px; object-fit: cover;
            border-radius: var(--radius-md); margin-bottom: 10px;
            background: #0a0a14;
        }
        .approval-images-row {
            display: flex; gap: 8px; margin-bottom: 10px;
        }
        .approval-images-row img {
            height: 160px; flex: 1; min-width: 0; object-fit: cover;
            border-radius: var(--radius-md); background: #0a0a14;
        }
        .text-clamp {
            font-size: 13px; color: var(--color-text-tertiary); line-height: 1.6;
            display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
            overflow: hidden; white-space: pre-wrap; word-break: break-word;
        }
        .text-clamp.expanded {
            -webkit-line-clamp: unset; max-height: 400px; overflow-y: auto;
        }
        .show-more-link {
            font-size: 12px; color: var(--color-primary); cursor: pointer;
            margin-top: 4px; display: inline-block; font-weight: 500;
        }
        .show-more-link:hover { color: var(--color-primary-hover); }
        .video-indicator {
            display: flex; align-items: center; gap: 8px;
            padding: 8px 12px; margin-top: 10px;
            background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.18);
            border-radius: var(--radius-sm); font-size: 12px; color: #a5b4fc;
        }
        .video-indicator svg { flex-shrink: 0; }
        .video-placeholder {
            width: 100%; height: 140px; border-radius: var(--radius-md);
            background: #0a0a14; display: flex; flex-direction: column;
            align-items: center; justify-content: center; gap: 8px;
            margin-bottom: 10px; border: 1px dashed rgba(255,255,255,0.1);
        }
        .video-placeholder svg { opacity: 0.4; }
        .video-placeholder span { font-size: 11px; color: var(--color-text-tertiary); }
        .approval-variant .btn-select {
            display: inline-flex; align-items: center; gap: 6px;
            padding: 7px 16px; font-size: 12px; font-weight: 600;
            background: var(--color-success); color: #fff;
            border: none; border-radius: var(--radius-sm); cursor: pointer;
            transition: all var(--transition-fast); float: right; margin-top: 12px;
        }
        .approval-variant .btn-select:hover {
            background: var(--color-success-hover); transform: translateY(-1px);
        }

        /* Ungrouped approval cards */
        .approval-single {
            background: var(--color-bg-card); border: var(--glass-border);
            border-radius: var(--radius-lg); padding: 16px;
        }

        /* ── View 4: Content Queue ───────────────────────── */
        .content-view { overflow-y: auto; padding: 20px 24px; gap: 16px; }
        .content-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 12px; }
        .content-card {
            background: #0d0d1a; border: 1px solid #1a1a30; border-radius: 10px;
            padding: 16px; transition: all 0.3s ease;
        }
        .content-card.approved { opacity: 0.5; border-color: #22c55e40; }
        .content-card.rejected { opacity: 0.5; border-color: #ef444440; }
        .content-card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
        .content-platform { font-weight: 600; font-size: 13px; color: #a5b4fc; }
        .content-body { font-size: 12px; color: #999; line-height: 1.5; margin-bottom: 12px; }
        .content-risk-bar {
            height: 4px; background: #1a1a30; border-radius: 2px; margin-bottom: 8px;
        }
        .content-risk-fill { height: 100%; border-radius: 2px; transition: width 0.5s; }
        .content-flags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
        .content-flag {
            font-size: 10px; padding: 2px 6px; border-radius: 4px;
            background: #f59e0b20; color: #fbbf24;
        }
        .content-actions { display: flex; gap: 8px; }

        /* ── View 5: Skills Observatory ──────────────────── */
        .skills-view {
            overflow-y: auto;
            padding: var(--space-5) var(--space-6);
            gap: var(--space-4);
        }

        /* Evolution Showcase Section */
        .skills-evolution-showcase {
            margin-bottom: var(--space-8);
        }

        .evolution-showcase-title {
            font-size: var(--font-size-base);
            font-weight: var(--font-weight-bold);
            color: var(--color-text-primary);
            margin-bottom: var(--space-4);
            display: flex;
            align-items: center;
            gap: var(--space-2);
        }

        .evolution-showcase-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: var(--space-4);
        }

        /* Evolution Card */
        .evolution-card {
            background: var(--glass-bg);
            backdrop-filter: var(--glass-blur);
            border: var(--glass-border);
            border-radius: var(--radius-xl);
            padding: var(--space-5);
            cursor: pointer;
            transition: all var(--transition-base);
            box-shadow: var(--shadow-md);
            position: relative;
            overflow: hidden;
        }

        .evolution-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--color-primary), var(--color-info));
        }

        .evolution-card:hover {
            background: var(--glass-bg-hover);
            border-color: rgba(99, 102, 241, 0.4);
            box-shadow: var(--shadow-lg);
            transform: translateY(-4px);
        }

        .evolution-card-name {
            font-size: var(--font-size-base);
            font-weight: var(--font-weight-semibold);
            color: var(--color-text-primary);
            margin-bottom: var(--space-2);
        }

        /* Version Timeline */
        .version-timeline {
            display: flex;
            align-items: center;
            gap: var(--space-2);
            margin: var(--space-4) 0;
        }

        .version-node {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: var(--space-1);
        }

        .version-badge {
            width: 32px;
            height: 32px;
            border-radius: var(--radius-full);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: var(--font-size-xs);
            font-weight: var(--font-weight-bold);
            border: 2px solid;
            transition: all var(--transition-fast);
        }

        .version-badge.v1 {
            background: rgba(239, 68, 68, 0.2);
            border-color: #ef4444;
            color: #f87171;
        }

        .version-badge.v2 {
            background: rgba(245, 158, 11, 0.2);
            border-color: #f59e0b;
            color: #fbbf24;
        }

        .version-badge.v3 {
            background: rgba(34, 197, 94, 0.2);
            border-color: #22c55e;
            color: #4ade80;
        }

        .version-arrow {
            color: var(--color-text-muted);
            font-size: var(--font-size-sm);
        }

        /* Confidence Progress */
        .evolution-progress {
            position: relative;
            height: 6px;
            background: var(--color-bg-tertiary);
            border-radius: var(--radius-full);
            overflow: hidden;
            margin: var(--space-3) 0;
        }

        .evolution-progress-fill {
            height: 100%;
            border-radius: var(--radius-full);
            background: linear-gradient(90deg, #22c55e, #10b981);
            transition: width 1.5s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }

        .evolution-progress-fill::after {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(
                90deg,
                transparent,
                rgba(255, 255, 255, 0.3),
                transparent
            );
            animation: shimmer 2s infinite;
        }

        .evolution-stats {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .evolution-confidence {
            font-size: var(--font-size-2xl);
            font-weight: var(--font-weight-extrabold);
            color: var(--color-success);
            font-variant-numeric: tabular-nums;
        }

        .evolution-delta {
            display: inline-flex;
            align-items: center;
            gap: var(--space-1);
            padding: var(--space-1) var(--space-2);
            background: rgba(34, 197, 94, 0.15);
            border-radius: var(--radius-sm);
            font-size: var(--font-size-sm);
            font-weight: var(--font-weight-semibold);
            color: var(--color-success);
        }

        .evolution-uses {
            font-size: var(--font-size-sm);
            color: var(--color-text-muted);
            margin-top: var(--space-2);
        }

        /* Regular Skills Section */
        .skills-category {
            margin-bottom: var(--space-6);
        }

        .skills-category-title {
            font-size: var(--font-size-sm);
            font-weight: var(--font-weight-bold);
            color: var(--color-text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: var(--space-3);
            display: flex;
            align-items: center;
            gap: var(--space-2);
        }

        .skills-category-title::after {
            content: '';
            flex: 1;
            height: 1px;
            background: var(--glass-border);
        }

        .skills-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: var(--space-3);
        }

        .skill-card {
            background: var(--color-bg-card);
            border: var(--glass-border);
            border-radius: var(--radius-lg);
            padding: var(--space-4);
            cursor: pointer;
            transition: all var(--transition-base);
        }

        .skill-card:hover {
            border-color: rgba(99, 102, 241, 0.3);
            transform: translateY(-2px);
            box-shadow: var(--shadow-sm);
        }

        .skill-card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .skill-name {
            font-size: var(--font-size-sm);
            font-weight: var(--font-weight-semibold);
            color: var(--color-text-primary);
        }

        .skill-version {
            font-size: var(--font-size-xs);
            color: var(--color-text-disabled);
        }

        .skill-meta {
            font-size: var(--font-size-xs);
            color: var(--color-text-muted);
            margin-top: var(--space-1);
        }

        .confidence-bar {
            height: 4px;
            background: var(--color-bg-tertiary);
            border-radius: var(--radius-full);
            margin-top: var(--space-2);
            overflow: hidden;
        }

        .confidence-fill {
            height: 100%;
            border-radius: var(--radius-full);
            transition: width 1s ease, background 1s ease;
        }

        .skill-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: var(--space-2);
        }

        .skill-conf {
            font-size: var(--font-size-xs);
            font-weight: var(--font-weight-semibold);
        }

        .skill-health-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            display: inline-block;
            margin-right: var(--space-1);
        }

        .health-ok { background: var(--color-success); }
        .health-warn { background: var(--color-warning); }
        .health-bad { background: var(--color-danger); }

        .skill-detail-panel {
            display: none;
            margin-top: var(--space-3);
            padding-top: var(--space-3);
            border-top: var(--glass-border);
            font-size: var(--font-size-sm);
            color: var(--color-text-tertiary);
        }

        .skill-detail-panel.open {
            display: block;
            animation: slideIn var(--transition-base) ease-out;
        }

        /* ── View 6: Brand Config ────────────────────────── */
        .brand-view { overflow-y: auto; padding: 20px 24px; gap: 20px; }
        .brand-wizard {
            max-width: 700px; margin: 0 auto;
        }
        .wizard-steps { display: flex; gap: 4px; margin-bottom: 24px; }
        .wizard-step {
            flex: 1; height: 4px; border-radius: 2px; background: #1a1a30;
            transition: background 0.3s;
        }
        .wizard-step.active { background: #6366f1; }
        .wizard-step.done { background: #22c55e; }
        .wizard-panel { display: none; }
        .wizard-panel.active { display: block; }
        .wizard-label {
            font-size: 16px; font-weight: 700; color: #fff; margin-bottom: 4px;
        }
        .wizard-desc { font-size: 13px; color: #6b7280; margin-bottom: 16px; }
        .wizard-input {
            width: 100%; background: #0d0d1a; border: 1px solid #1a1a30;
            border-radius: 8px; padding: 10px 14px; color: #e0e0f0;
            font-family: inherit; font-size: 14px; outline: none;
            transition: border-color 0.15s;
        }
        .wizard-input:focus { border-color: #6366f1; }
        .wizard-textarea {
            width: 100%; background: #0d0d1a; border: 1px solid #1a1a30;
            border-radius: 8px; padding: 10px 14px; color: #e0e0f0;
            font-family: inherit; font-size: 14px; outline: none;
            resize: vertical; min-height: 100px; transition: border-color 0.15s;
        }
        .wizard-textarea:focus { border-color: #6366f1; }
        .tag-input-wrap {
            display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
            background: #0d0d1a; border: 1px solid #1a1a30; border-radius: 8px;
            padding: 8px 10px; min-height: 42px;
        }
        .tag-input-wrap:focus-within { border-color: #6366f1; }
        .tag {
            display: flex; align-items: center; gap: 4px;
            background: #6366f120; color: #a5b4fc; padding: 3px 8px;
            border-radius: 6px; font-size: 12px; font-weight: 500;
        }
        .tag-remove {
            cursor: pointer; font-size: 14px; color: #a5b4fc80; line-height: 1;
        }
        .tag-remove:hover { color: #ef4444; }
        .tag-text-input {
            border: none; background: none; color: #e0e0f0;
            font-family: inherit; font-size: 13px; outline: none;
            flex: 1; min-width: 80px;
        }
        .wizard-nav { display: flex; justify-content: space-between; margin-top: 24px; }
        .wizard-preview {
            margin-top: 16px; padding: 14px; background: #06060b;
            border: 1px dashed #1a1a30; border-radius: 8px;
            font-size: 12px; color: #666;
        }

        /* ── View 7: Performance ─────────────────────────── */
        .perf-view {
            overflow-y: auto;
            padding: var(--space-5) var(--space-6);
            gap: var(--space-5);
        }

        .perf-scoreboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: var(--space-4);
            margin-bottom: var(--space-6);
        }

        .perf-card {
            background: var(--glass-bg);
            backdrop-filter: var(--glass-blur);
            border: var(--glass-border);
            border-radius: var(--radius-xl);
            padding: var(--space-8);
            text-align: center;
            position: relative;
            overflow: hidden;
            transition: all var(--transition-base);
        }

        .perf-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--color-info), var(--color-primary));
        }

        .perf-card:hover {
            border-color: rgba(6, 182, 212, 0.4);
            transform: translateY(-4px);
            box-shadow: var(--shadow-xl);
        }

        .perf-card.highlight {
            border-color: rgba(6, 182, 212, 0.3);
        }

        .perf-value {
            font-size: var(--font-size-4xl);
            font-weight: var(--font-weight-extrabold);
            color: var(--color-text-primary);
            font-variant-numeric: tabular-nums;
            line-height: 1;
            margin-bottom: var(--space-2);
            background: linear-gradient(135deg, #06b6d4, #a5b4fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .perf-label {
            font-size: var(--font-size-sm);
            color: var(--color-text-muted);
            margin-top: var(--space-2);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: var(--font-weight-medium);
        }

        .perf-subtitle {
            font-size: var(--font-size-xs);
            color: var(--color-text-disabled);
            margin-top: var(--space-1);
        }

        /* Comparison bar */
        .perf-comparison {
            margin-top: var(--space-4);
            height: 6px;
            background: var(--color-bg-tertiary);
            border-radius: var(--radius-full);
            overflow: hidden;
            position: relative;
        }

        .perf-comparison-fill {
            height: 100%;
            background: linear-gradient(90deg, #22c55e, #10b981);
            border-radius: var(--radius-full);
            transition: width 1.5s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .perf-comparison-label {
            font-size: var(--font-size-xs);
            color: var(--color-text-muted);
            margin-top: var(--space-2);
            display: flex;
            justify-content: space-between;
        }

        .perf-table {
            width: 100%;
            border-collapse: collapse;
        }

        .perf-table th {
            text-align: left;
            padding: var(--space-2) var(--space-3);
            font-size: var(--font-size-xs);
            font-weight: var(--font-weight-semibold);
            color: var(--color-text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: var(--glass-border);
        }

        .perf-table td {
            padding: var(--space-2) var(--space-3);
            font-size: var(--font-size-sm);
            border-bottom: 1px solid rgba(26, 26, 48, 0.3);
            color: var(--color-text-secondary);
        }

        .perf-table tr {
            transition: background var(--transition-fast);
        }

        .perf-table tr:hover {
            background: rgba(99, 102, 241, 0.05);
        }

        /* ── Animation utilities ─────────────────────────── */
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes slideInFromRight {
            from {
                opacity: 0;
                transform: translateX(20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes scaleIn {
            from {
                opacity: 0;
                transform: scale(0.95);
            }
            to {
                opacity: 1;
                transform: scale(1);
            }
        }

        @keyframes shimmer {
            0% {
                background-position: -200% 0;
            }
            100% {
                background-position: 200% 0;
            }
        }

        .anim-in { animation: slideIn var(--transition-slow) ease-out; }
        .anim-slide-right { animation: slideInFromRight var(--transition-slow) ease-out; }
        .anim-fade { animation: fadeIn var(--transition-base) ease-out; }
        .anim-scale { animation: scaleIn var(--transition-base) ease-out; }

        /* Stagger children animations */
        .stagger-children > * {
            animation: slideIn var(--transition-slow) ease-out;
        }
        .stagger-children > *:nth-child(1) { animation-delay: 0ms; }
        .stagger-children > *:nth-child(2) { animation-delay: 50ms; }
        .stagger-children > *:nth-child(3) { animation-delay: 100ms; }
        .stagger-children > *:nth-child(4) { animation-delay: 150ms; }
        .stagger-children > *:nth-child(5) { animation-delay: 200ms; }
        .stagger-children > *:nth-child(6) { animation-delay: 250ms; }

        /* ── Pipeline SVG styles ─────────────────────────── */
        .node-rect {
            rx: 12;
            ry: 12;
            fill: var(--color-bg-card);
            stroke: var(--glass-border);
            stroke-width: 1.5;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .node-rect:hover {
            fill: var(--color-bg-elevated);
            stroke: var(--color-primary);
            stroke-width: 2;
            filter: drop-shadow(0 4px 12px rgba(99, 102, 241, 0.3));
        }

        .node-rect.active {
            stroke: var(--color-success);
            fill: rgba(34, 197, 94, 0.1);
            filter: drop-shadow(0 0 8px rgba(34, 197, 94, 0.5));
        }

        .node-label {
            fill: var(--color-text-primary);
            font-size: 12px;
            font-weight: 600;
            font-family: var(--font-sans);
            pointer-events: none;
        }

        .node-icon {
            font-size: 16px;
            pointer-events: none;
        }

        .node-count {
            fill: var(--color-primary-hover);
            font-size: 10px;
            font-weight: 600;
            font-family: var(--font-sans);
            pointer-events: none;
        }

        .flow-path {
            stroke: rgba(99, 102, 241, 0.2);
            stroke-width: 2;
            fill: none;
            stroke-dasharray: 8, 4;
        }

        .flow-path.active {
            stroke: rgba(99, 102, 241, 0.4);
        }

        .flow-particle {
            fill: var(--color-primary);
            opacity: 0.8;
            filter: drop-shadow(0 0 4px var(--color-primary));
        }

        .feedback-path {
            stroke: rgba(6, 182, 212, 0.3);
            stroke-width: 1.5;
            fill: none;
            stroke-dasharray: 4, 4;
        }
    </style>
</head>
<body>
<div class="app-layout">
    <!-- Sidebar -->
    <nav class="sidebar">
        <div class="sidebar-logo" onclick="App.navigate('chat')">K</div>
        <div class="sidebar-divider"></div>
        <button class="sidebar-btn active" data-view="chat" onclick="App.navigate('chat')">
            <span>&#x1F4AC;</span><span class="tooltip">Chat</span>
        </button>
        <button class="sidebar-btn" data-view="pipeline" onclick="App.navigate('pipeline')">
            <span>&#x1F500;</span><span class="tooltip">Pipeline</span>
        </button>
        <button class="sidebar-btn" data-view="discoveries" onclick="App.navigate('discoveries')">
            <span>&#x1F50D;</span><span class="tooltip">Discoveries</span>
        </button>
        <button class="sidebar-btn" data-view="approval" onclick="App.navigate('approval')">
            <span>&#x2705;</span><span class="tooltip">Approval</span>
        </button>
        <button class="sidebar-btn" data-view="content" onclick="App.navigate('content')">
            <span>&#x1F4C4;</span><span class="tooltip">Content</span>
        </button>
        <button class="sidebar-btn" data-view="skills" onclick="App.navigate('skills')">
            <span>&#x1F9E0;</span><span class="tooltip">Skills</span>
        </button>
        <button class="sidebar-btn" data-view="brand" onclick="App.navigate('brand')">
            <span>&#x1F3A8;</span><span class="tooltip">Brand</span>
        </button>
        <button class="sidebar-btn" data-view="performance" onclick="App.navigate('performance')">
            <span>&#x1F4CA;</span><span class="tooltip">Performance</span>
        </button>
        <div class="sidebar-status">
            <div class="status-dot" id="globalStatusDot"></div>
            <span class="status-label">Active</span>
        </div>
    </nav>

    <!-- Main -->
    <div class="main-area">
        <div class="header-bar">
            <div class="header-left">
                <span class="header-brand">Autopilot</span>
                <span class="header-sub">by Kairox AI</span>
            </div>
            <div class="header-right">
                <div class="header-status" id="headerStatus">
                    <span class="header-status-dot" id="headerStatusDot"></span>
                    <span id="headerStatusText">Pipeline Active</span>
                </div>
                <span class="header-uptime tabular" id="headerUptime">0:00:00</span>
            </div>
        </div>

        <div class="view-container">
            <!-- Chat View -->
            <div class="view active" id="view-chat">
                <div class="chat-messages" id="chatMessages">
                    <div class="chat-empty" id="chatEmpty">
                        <div class="chat-empty-title">Autopilot Agent</div>
                        <div class="chat-empty-sub">I can manage your content pipeline, check performance, approve content, and configure your brand. What would you like to do?</div>
                        <div class="prompt-cards">
                            <div class="prompt-card" onclick="App.sendPrompt('Run the content pipeline and show me what\\'s trending')">Run the content pipeline and show me what's trending</div>
                            <div class="prompt-card" onclick="App.sendPrompt('What skills are performing best right now?')">What skills are performing best right now?</div>
                            <div class="prompt-card" onclick="App.sendPrompt('Show me the pipeline status and latest discoveries')">Show me the pipeline status and latest discoveries</div>
                        </div>
                    </div>
                </div>
                <div class="typing-indicator" id="typingIndicator">
                    <div class="msg msg-assistant" style="padding:10px 16px">
                        <div class="typing-dots"><span></span><span></span><span></span></div>
                    </div>
                </div>
                <div class="chat-input-area">
                    <div class="chat-input-row">
                        <textarea class="chat-textarea" id="chatInput" placeholder="Ask the agent anything..." rows="1"
                            onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();App.sendMessage()}"></textarea>
                        <button class="chat-send" id="chatSendBtn" onclick="App.sendMessage()">&#x27A4;</button>
                    </div>
                </div>
            </div>

            <!-- Pipeline View -->
            <div class="view" id="view-pipeline">
                <div class="pipeline-view" style="display:flex;flex-direction:column;overflow-y:auto;padding:20px 24px;gap:20px">
                    <div style="display:flex;align-items:center;justify-content:space-between">
                        <span class="section-title">Content Pipeline</span>
                        <div class="pipeline-actions">
                            <button class="btn btn-primary" id="pipelineRunBtn" onclick="App.triggerScout()">
                                <span id="pipelineRunText">Run Full Pipeline</span>
                            </button>
                        </div>
                    </div>
                    <div class="pipeline-svg-wrap">
                        <svg id="pipelineSvg" viewBox="0 0 900 200" class="pipeline-svg"></svg>
                    </div>
                    <div class="pipeline-metrics" id="pipelineMetrics"></div>
                </div>
            </div>

            <!-- Agent Detail Panel (Bottom Sheet) -->
            <div class="agent-detail-panel" id="agentDetailPanel">
                <div class="agent-detail-header">
                    <div class="agent-detail-title" id="agentDetailTitle">Agent Details</div>
                    <button class="agent-detail-close" onclick="App.closeAgentDetail()">×</button>
                </div>
                <div class="agent-detail-content" id="agentDetailContent"></div>
            </div>

            <!-- Discoveries View -->
            <div class="view" id="view-discoveries">
                <div class="disc-view" style="display:flex;flex-direction:column;overflow-y:auto;padding:20px 24px;gap:16px">
                    <div style="display:flex;align-items:center;justify-content:space-between">
                        <span class="section-title">Discoveries</span>
                        <div class="disc-filters" id="discFilters">
                            <span class="filter-chip active" data-status="" onclick="App.filterDiscoveries(this)">All</span>
                            <span class="filter-chip" data-status="new" onclick="App.filterDiscoveries(this)">New</span>
                            <span class="filter-chip" data-status="analyzed" onclick="App.filterDiscoveries(this)">Analyzed</span>
                            <span class="filter-chip" data-status="queued" onclick="App.filterDiscoveries(this)">Queued</span>
                            <span class="filter-chip" data-status="published" onclick="App.filterDiscoveries(this)">Published</span>
                        </div>
                    </div>
                    <div class="card" style="overflow-x:auto">
                        <table class="disc-table">
                            <thead><tr>
                                <th>Source</th><th>Title</th><th>Relevance</th><th>Velocity</th><th>Risk</th><th>Status</th><th>Time</th>
                            </tr></thead>
                            <tbody id="discTableBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Approval View -->
            <div class="view" id="view-approval">
                <div class="approval-view" style="display:flex;flex-direction:column;overflow-y:auto;padding:20px 24px;gap:16px">
                    <div style="display:flex;align-items:center;justify-content:space-between">
                        <span class="section-title">Approval Queue</span>
                        <span class="badge badge-indigo" id="approvalCountBadge">0 pending</span>
                    </div>
                    <div class="approval-filter-bar" id="approvalFilterBar"></div>
                    <div id="approvalGroups" style="display:flex;flex-direction:column;gap:16px"></div>
                    <div id="approvalEmpty" style="display:none;text-align:center;padding:40px;color:var(--color-text-tertiary)">
                        No content pending approval.
                    </div>
                </div>
            </div>

            <!-- Content View -->
            <div class="view" id="view-content">
                <div class="content-view" style="display:flex;flex-direction:column;overflow-y:auto;padding:20px 24px;gap:16px">
                    <span class="section-title">Pending Review</span>
                    <div class="content-grid" id="contentPending"></div>
                    <details style="margin-top:12px">
                        <summary style="font-size:13px;color:#6b7280;cursor:pointer;margin-bottom:8px">Recently Processed</summary>
                        <div class="content-grid" id="contentProcessed"></div>
                    </details>
                </div>
            </div>

            <!-- Skills View -->
            <div class="view" id="view-skills">
                <div class="skills-view" style="display:flex;flex-direction:column;overflow-y:auto;padding:20px 24px;gap:16px">
                    <div style="display:flex;align-items:center;justify-content:space-between">
                        <span class="section-title">Skills Observatory</span>
                        <span class="badge badge-indigo" id="skillsCountBadge">0 skills</span>
                    </div>
                    <div id="skillsContainer"></div>
                </div>
            </div>

            <!-- Brand View -->
            <div class="view" id="view-brand">
                <div class="brand-view" style="display:flex;flex-direction:column;overflow-y:auto;padding:20px 24px;gap:20px">
                    <span class="section-title">Brand Configuration</span>
                    <div class="brand-wizard" id="brandWizard">
                        <div class="wizard-steps" id="wizardSteps">
                            <div class="wizard-step active" data-step="0"></div>
                            <div class="wizard-step" data-step="1"></div>
                            <div class="wizard-step" data-step="2"></div>
                            <div class="wizard-step" data-step="3"></div>
                        </div>
                        <!-- Step 0: Brand Identity -->
                        <div class="wizard-panel active" data-step="0">
                            <div class="wizard-label">Brand Identity</div>
                            <div class="wizard-desc">Set your brand name and description</div>
                            <div style="margin-bottom:12px">
                                <label style="font-size:12px;color:#6b7280;display:block;margin-bottom:4px">Brand Name</label>
                                <input class="wizard-input" id="brandName" placeholder="e.g. Autopilot by Kairox AI">
                            </div>
                        </div>
                        <!-- Step 1: Voice -->
                        <div class="wizard-panel" data-step="1">
                            <div class="wizard-label">Voice & Tone</div>
                            <div class="wizard-desc">Define how your content should sound</div>
                            <textarea class="wizard-textarea" id="brandVoice" placeholder="e.g. Professional but approachable. Use data-driven insights. Avoid jargon unless talking to developers."></textarea>
                            <div class="wizard-preview" id="voicePreview">Preview will appear as you type...</div>
                        </div>
                        <!-- Step 2: Topics -->
                        <div class="wizard-panel" data-step="2">
                            <div class="wizard-label">Topics</div>
                            <div class="wizard-desc">Focus topics (press Enter to add)</div>
                            <div class="tag-input-wrap" id="topicsWrap">
                                <input class="tag-text-input" id="topicsInput" placeholder="Add topic...">
                            </div>
                            <div style="margin-top:16px">
                                <label style="font-size:12px;color:#6b7280;display:block;margin-bottom:4px">Topics to Avoid</label>
                                <div class="tag-input-wrap" id="avoidTopicsWrap">
                                    <input class="tag-text-input" id="avoidTopicsInput" placeholder="Add topic to avoid...">
                                </div>
                            </div>
                        </div>
                        <!-- Step 3: Competitors -->
                        <div class="wizard-panel" data-step="3">
                            <div class="wizard-label">Competitors</div>
                            <div class="wizard-desc">Competitor names feed into risk assessment (press Enter to add)</div>
                            <div class="tag-input-wrap" id="competitorsWrap">
                                <input class="tag-text-input" id="competitorsInput" placeholder="Add competitor...">
                            </div>
                        </div>
                        <div class="wizard-nav">
                            <button class="btn btn-ghost" id="wizardPrev" onclick="App.wizardPrev()" disabled>Back</button>
                            <button class="btn btn-primary" id="wizardNext" onclick="App.wizardNext()">Next</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Performance View -->
            <div class="view" id="view-performance">
                <div class="perf-view" style="display:flex;flex-direction:column;overflow-y:auto;padding:20px 24px;gap:20px">
                    <span class="section-title">Performance & Arbitrage</span>
                    <div class="perf-scoreboard" id="perfScoreboard"></div>
                    <div class="card">
                        <div class="section-title" style="margin-bottom:12px">Recent Publications</div>
                        <table class="perf-table">
                            <thead><tr>
                                <th>Platform</th><th>Arbitrage Window</th><th>Published</th>
                            </tr></thead>
                            <tbody id="perfTableBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
const App = {
    state: {
        activeView: 'chat',
        ws: null,
        messages: [],
        isAgentRunning: false,
        currentAssistantMsg: null,
        pipeline: null,
        skills: [],
        discoveries: [],
        creations: [],
        publications: [],
        arbitrage: null,
        playbook: null,
        costs: null,
        discFilter: '',
        wizardStep: 0,
        brandTopics: [],
        brandAvoidTopics: [],
        brandCompetitors: [],
        startTime: Date.now(),
        pollTimer: null,
    },

    // ── Navigation ─────────────────────────────────────

    navigate(viewId) {
        this.state.activeView = viewId;
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById('view-' + viewId).classList.add('active');
        document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
        const btn = document.querySelector(`.sidebar-btn[data-view="${viewId}"]`);
        if (btn) btn.classList.add('active');

        // Refresh data for the view
        if (viewId !== 'chat') this.fetchViewData(viewId);
    },

    // ── WebSocket Chat ─────────────────────────────────

    connectChat() {
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        this.state.ws = new WebSocket(`${proto}://${location.host}/ws/chat`);
        this.state.ws.onmessage = (e) => this.handleWsMessage(JSON.parse(e.data));
        this.state.ws.onclose = () => {
            setTimeout(() => this.connectChat(), 2000);
        };
        this.state.ws.onerror = () => {};
    },

    sendMessage() {
        const input = document.getElementById('chatInput');
        const content = input.value.trim();
        if (!content || this.state.isAgentRunning) return;
        if (!this.state.ws || this.state.ws.readyState !== WebSocket.OPEN) {
            this.connectChat();
            setTimeout(() => this.sendMessage(), 500);
            return;
        }

        // Hide empty state
        const empty = document.getElementById('chatEmpty');
        if (empty) empty.style.display = 'none';

        // Add user message
        this.addChatMessage('user', content);
        input.value = '';
        input.style.height = 'auto';

        // Send to server
        this.state.ws.send(JSON.stringify({ type: 'message', content }));
        this.state.isAgentRunning = true;
        this.state.currentAssistantMsg = null;
        document.getElementById('chatSendBtn').disabled = true;
        document.getElementById('typingIndicator').classList.add('show');
    },

    sendPrompt(text) {
        document.getElementById('chatInput').value = text;
        this.sendMessage();
    },

    handleWsMessage(msg) {
        const indicator = document.getElementById('typingIndicator');

        if (msg.type === 'text') {
            indicator.classList.remove('show');
            if (!this.state.currentAssistantMsg) {
                this.state.currentAssistantMsg = this.addChatMessage('assistant', msg.content);
            } else {
                // Append to existing message
                const el = this.state.currentAssistantMsg;
                const contentDiv = el.querySelector('.msg-content');
                contentDiv.innerHTML += this.formatMarkdown(msg.content);
                this.scrollChatBottom();
            }
        } else if (msg.type === 'tool_start') {
            indicator.classList.remove('show');
            if (!this.state.currentAssistantMsg) {
                this.state.currentAssistantMsg = this.addChatMessage('assistant', '');
            }
            const el = this.state.currentAssistantMsg;
            const contentDiv = el.querySelector('.msg-content');
            const toolId = 'tool-' + Date.now();
            contentDiv.innerHTML += `
                <div class="tool-block" id="${toolId}">
                    <div class="tool-header">
                        <span class="tool-icon">&#x1F50D;</span>
                        <span class="tool-name">${this.escapeHtml(msg.name)}</span>
                        <span class="tool-status running">
                            <span class="spinner" style="width:10px;height:10px;border-width:1.5px"></span>
                            ${this.escapeHtml(msg.display || 'Running...')}
                        </span>
                    </div>
                    <div class="tool-body hidden"></div>
                </div>`;
            this.state._lastToolId = toolId;
            this.scrollChatBottom();
        } else if (msg.type === 'tool_end') {
            const toolEl = this.state._lastToolId && document.getElementById(this.state._lastToolId);
            if (toolEl) {
                const statusEl = toolEl.querySelector('.tool-status');
                const bodyEl = toolEl.querySelector('.tool-body');
                if (msg.success) {
                    statusEl.className = 'tool-status done';
                    statusEl.innerHTML = '&#x2713; Complete';
                } else {
                    statusEl.className = 'tool-status error';
                    statusEl.innerHTML = '&#x2717; Error';
                }
                // Show summary of result
                if (msg.result) {
                    const summary = this.summarizeToolResult(msg.name, msg.result);
                    if (summary) {
                        bodyEl.classList.remove('hidden');
                        bodyEl.textContent = summary;
                    }
                }
            }
            this.scrollChatBottom();
        } else if (msg.type === 'done') {
            this.state.isAgentRunning = false;
            this.state.currentAssistantMsg = null;
            document.getElementById('chatSendBtn').disabled = false;
            indicator.classList.remove('show');
        }
    },

    addChatMessage(role, content) {
        const container = document.getElementById('chatMessages');
        const div = document.createElement('div');
        div.className = 'msg ' + (role === 'user' ? 'msg-user' : 'msg-assistant');
        if (role === 'user') {
            div.textContent = content;
        } else {
            div.innerHTML = '<div class="msg-content">' + this.formatMarkdown(content) + '</div>';
        }
        container.appendChild(div);
        this.scrollChatBottom();
        this.state.messages.push({ role, content });
        return div;
    },

    scrollChatBottom() {
        const el = document.getElementById('chatMessages');
        el.scrollTop = el.scrollHeight;
    },

    summarizeToolResult(name, result) {
        if (result.error) return 'Error: ' + result.error;
        if (name === 'get_pipeline_status') {
            const c = result.counts || {};
            return `Pipeline: ${c.discoveries || 0} discoveries, ${c.creations || 0} creations, ${c.publications || 0} publications`;
        }
        if (name === 'get_discoveries') return `Found ${result.total || 0} discoveries`;
        if (name === 'get_skills') return `${result.total || 0} skills loaded`;
        if (name === 'get_arbitrage') return `Avg ${result.avg_arbitrage_minutes || 0}min ahead, ${result.total_publications_with_arbitrage || 0} publications`;
        if (name === 'trigger_scout') return result.status === 'completed' ? 'Scout completed successfully' : JSON.stringify(result);
        if (name === 'get_creations') return `${result.total || 0} content items`;
        if (name === 'approve_content') return `Content #${result.id} approved`;
        if (name === 'reject_content') return `Content #${result.id} rejected`;
        if (name === 'update_brand') return `Brand "${result.brand_name}" updated`;
        if (name === 'get_publications') return `${result.total || 0} publications`;
        return null;
    },

    formatMarkdown(text) {
        if (!text) return '';
        let html = this.escapeHtml(text);
        // Bold
        html = html.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Line breaks -> paragraphs
        html = html.replace(/\\n\\n/g, '</p><p>');
        html = html.replace(/\\n/g, '<br>');
        // Bullet lists
        html = html.replace(/^- (.+)/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\\/li>)/s, '<ul>$1</ul>');
        if (!html.startsWith('<')) html = '<p>' + html + '</p>';
        return html;
    },

    // ── Data Fetching ──────────────────────────────────

    async api(url, opts) {
        try {
            const r = await fetch(url, opts);
            if (!r.ok) return null;
            return await r.json();
        } catch { return null; }
    },

    async fetchAll() {
        const [pipeline, skills, arbitrage, costs] = await Promise.all([
            this.api('/pipeline'),
            this.api('/skills'),
            this.api('/arbitrage'),
            this.api('/costs'),
        ]);
        this.state.pipeline = pipeline;
        this.state.skills = skills || [];
        this.state.arbitrage = arbitrage;
        this.state.costs = costs;

        // Update header status
        const running = pipeline?.running !== false;
        const statusText = document.getElementById('headerStatusText');
        const statusDot = document.getElementById('headerStatusDot');
        const statusContainer = document.getElementById('headerStatus');

        statusText.textContent = running ? 'Pipeline Active' : 'Pipeline Stopped';
        statusDot.style.background = running ? '#22c55e' : '#ef4444';
        statusContainer.style.background = running ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)';

        const globalDot = document.getElementById('globalStatusDot');
        if (!running) {
            globalDot.style.background = '#ef4444';
            globalDot.style.animation = 'none';
        }
    },

    async fetchViewData(viewId) {
        if (viewId === 'pipeline') {
            await this.fetchAll();
            this.renderPipeline();
        } else if (viewId === 'discoveries') {
            this.state.discoveries = await this.api('/discoveries?limit=50&' + (this.state.discFilter ? 'status=' + this.state.discFilter : '')) || [];
            this.renderDiscoveries();
        } else if (viewId === 'approval') {
            this.state.approvalData = await this.api('/approval/pending') || {};
            this.renderApproval();
        } else if (viewId === 'content') {
            this.state.creations = await this.api('/creations?limit=50') || [];
            this.renderContent();
        } else if (viewId === 'skills') {
            this.state.skills = await this.api('/skills') || [];
            this.renderSkills();
        } else if (viewId === 'brand') {
            this.state.playbook = await this.api('/playbook');
            this.renderBrand();
        } else if (viewId === 'performance') {
            const [arb, pubs] = await Promise.all([
                this.api('/arbitrage'),
                this.api('/publications?limit=30'),
            ]);
            this.state.arbitrage = arb;
            this.state.publications = pubs || [];
            this.renderPerformance();
        }
    },

    // ── View Renderers ─────────────────────────────────

    renderPipeline() {
        const p = this.state.pipeline;
        const counts = p?.counts || {};
        const skillsCount = p?.skills_loaded || this.state.skills.length || 0;
        const arb = this.state.arbitrage || {};
        const avgHrs = ((arb.avg_arbitrage_minutes || 0) / 60).toFixed(1);

        // SVG
        this.renderPipelineSvg(p);

        // Metrics
        document.getElementById('pipelineMetrics').innerHTML = `
            <div class="metric-card mc-blue">
                <div class="metric-label">Discoveries</div>
                <div class="metric-value tabular">${counts.discoveries || 0}</div>
                <div class="metric-sub">Total items found</div>
            </div>
            <div class="metric-card mc-purple">
                <div class="metric-label">Creations</div>
                <div class="metric-value tabular">${counts.creations || 0}</div>
                <div class="metric-sub">Content generated</div>
            </div>
            <div class="metric-card mc-green">
                <div class="metric-label">Publications</div>
                <div class="metric-value tabular">${counts.publications || 0}</div>
                <div class="metric-sub">Posts published</div>
            </div>
            <div class="metric-card mc-yellow">
                <div class="metric-label">Skills Active</div>
                <div class="metric-value tabular">${skillsCount}</div>
                <div class="metric-sub">Self-improving</div>
            </div>
            <div class="metric-card mc-cyan">
                <div class="metric-label">Arbitrage Avg</div>
                <div class="metric-value tabular">${avgHrs}h</div>
                <div class="metric-sub">Time ahead</div>
            </div>
            <div class="metric-card mc-indigo">
                <div class="metric-label">Arb Publications</div>
                <div class="metric-value tabular">${arb.total_publications_with_arbitrage || 0}</div>
                <div class="metric-sub">With time advantage</div>
            </div>`;
    },

    renderPipelineSvg(pipeline) {
        const nodes = [
            { id: 'scout', label: 'Scout', icon: '🔍', x: 30, y: 70, w: 110, h: 60 },
            { id: 'analyst', label: 'Analyst', icon: '📊', x: 180, y: 70, w: 110, h: 60 },
            { id: 'creator', label: 'Creator', icon: '✍️', x: 330, y: 70, w: 110, h: 60 },
            { id: 'approval', label: 'Approval', icon: '✅', x: 480, y: 70, w: 110, h: 60 },
            { id: 'publisher', label: 'Publisher', icon: '📤', x: 630, y: 70, w: 110, h: 60 },
            { id: 'metrics', label: 'Metrics', icon: '📈', x: 780, y: 70, w: 100, h: 60 },
        ];

        const counts = pipeline?.counts || {};
        const countMap = {
            scout: counts.discoveries || 0,
            analyst: '-',
            creator: counts.creations || 0,
            approval: '-',
            publisher: counts.publications || 0,
            metrics: '-',
        };

        const isActive = (name) => {
            const lr = pipeline?.last_runs || {};
            if (name === 'scout' && lr.scout) {
                const diff = Date.now() - new Date(lr.scout).getTime();
                return diff < 300000; // 5 min
            }
            return false;
        };

        let svg = '<defs>';
        svg += '<filter id="glow"><feGaussianBlur stdDeviation="3" result="coloredBlur"/>';
        svg += '<feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>';
        svg += '</defs>';

        // Flow paths
        for (let i = 0; i < nodes.length - 1; i++) {
            const a = nodes[i], b = nodes[i + 1];
            const x1 = a.x + a.w, y1 = a.y + a.h / 2;
            const x2 = b.x, y2 = b.y + b.h / 2;
            svg += `<line class="flow-path active" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
        }

        // Feedback loop
        const first = nodes[0], last = nodes[nodes.length - 1];
        svg += `<path class="feedback-path" d="M${last.x + last.w/2},${last.y + last.h} C${last.x + last.w/2},${last.y + last.h + 60} ${first.x + first.w/2},${first.y + first.h + 60} ${first.x + first.w/2},${first.y + first.h}" />`;
        svg += `<text x="${(first.x + last.x + last.w) / 2}" y="${last.y + last.h + 48}" text-anchor="middle" fill="rgba(6, 182, 212, 0.4)" font-size="10" font-family="Inter,sans-serif">Feedback Loop</text>`;

        // Particle animation
        for (let i = 0; i < nodes.length - 1; i++) {
            const a = nodes[i], b = nodes[i + 1];
            const x1 = a.x + a.w, y1 = a.y + a.h / 2;
            const x2 = b.x, y2 = b.y + b.h / 2;
            svg += `<circle class="flow-particle" r="3" filter="url(#glow)">
                <animate attributeName="cx" from="${x1}" to="${x2}" dur="${2 + i * 0.3}s" repeatCount="indefinite"/>
                <animate attributeName="cy" from="${y1}" to="${y2}" dur="${2 + i * 0.3}s" repeatCount="indefinite"/>
                <animate attributeName="opacity" values="0;0.8;0" dur="${2 + i * 0.3}s" repeatCount="indefinite"/>
            </circle>`;
        }

        // Nodes (with click handlers)
        nodes.forEach(n => {
            const active = isActive(n.id);
            svg += `<g onclick="App.openAgentDetail('${n.id}')" style="cursor:pointer">`;
            svg += `<rect class="node-rect${active ? ' active' : ''}" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" ${active ? 'filter="url(#glow)"' : ''}/>`;
            svg += `<text class="node-label" x="${n.x + n.w/2}" y="${n.y + 28}" text-anchor="middle">${n.icon} ${n.label}</text>`;
            const ct = countMap[n.id];
            if (ct !== '-') {
                svg += `<text class="node-count" x="${n.x + n.w/2}" y="${n.y + 46}" text-anchor="middle">${ct}</text>`;
            }
            svg += `</g>`;
        });

        document.getElementById('pipelineSvg').innerHTML = svg;
    },

    async openAgentDetail(agentId) {
        const panel = document.getElementById('agentDetailPanel');
        const title = document.getElementById('agentDetailTitle');
        const content = document.getElementById('agentDetailContent');

        const agentIcons = {
            scout: '🔍',
            analyst: '📊',
            creator: '✍️',
            approval: '✅',
            publisher: '📤',
            metrics: '📈'
        };

        const agentNames = {
            scout: 'Scout Agent',
            analyst: 'Analyst Agent',
            creator: 'Creator Agent',
            approval: 'Approval Queue',
            publisher: 'Publisher Agent',
            metrics: 'Metrics Collector'
        };

        title.innerHTML = `${agentIcons[agentId] || ''} ${agentNames[agentId] || agentId}`;

        // Fetch recent work for this agent
        let html = '<div class="agent-detail-section">';
        html += '<div class="agent-detail-section-title">Recent Work</div>';

        if (agentId === 'scout') {
            const discoveries = await this.api('/discoveries?limit=5');
            if (discoveries && discoveries.length) {
                discoveries.forEach(d => {
                    const score = Math.round((d.relevance_score || 0) * 100);
                    html += `<div class="agent-work-item">
                        <div class="agent-work-item-title">${this.escapeHtml(d.title || 'Untitled')}</div>
                        <div class="agent-work-item-meta">
                            ${d.source} • Score: ${score}% • ${this.timeAgo(d.discovered_at)}
                        </div>
                    </div>`;
                });
            } else {
                html += '<div style="color:var(--color-text-muted);padding:var(--space-4)">No recent discoveries</div>';
            }
        } else if (agentId === 'creator') {
            const creations = await this.api('/creations?limit=5');
            if (creations && creations.length) {
                creations.forEach(c => {
                    html += `<div class="agent-work-item">
                        <div class="agent-work-item-title">${c.platform || 'Unknown'} ${c.format || 'post'}</div>
                        <div class="agent-work-item-meta">
                            ${c.approval_status || 'pending'} • ${this.timeAgo(c.created_at)}
                        </div>
                    </div>`;
                });
            } else {
                html += '<div style="color:var(--color-text-muted);padding:var(--space-4)">No recent creations</div>';
            }
        } else if (agentId === 'publisher') {
            const pubs = await this.api('/publications?limit=5');
            if (pubs && pubs.length) {
                pubs.forEach(p => {
                    html += `<div class="agent-work-item">
                        <div class="agent-work-item-title">${p.platform || 'Unknown'} publication</div>
                        <div class="agent-work-item-meta">
                            ${p.arbitrage_window_minutes ? p.arbitrage_window_minutes + ' min ahead' : 'No arbitrage'} • ${this.timeAgo(p.published_at)}
                        </div>
                    </div>`;
                });
            } else {
                html += '<div style="color:var(--color-text-muted);padding:var(--space-4)">No recent publications</div>';
            }
        } else {
            html += '<div style="color:var(--color-text-muted);padding:var(--space-4)">Agent details not available</div>';
        }

        html += '</div>';
        content.innerHTML = html;
        panel.classList.add('open');
    },

    closeAgentDetail() {
        document.getElementById('agentDetailPanel').classList.remove('open');
    },

    renderDiscoveries() {
        const items = Array.isArray(this.state.discoveries) ? this.state.discoveries : [];
        const tbody = document.getElementById('discTableBody');
        if (!items.length) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#555;padding:30px">No discoveries yet. Run the scout to find trending content.</td></tr>';
            return;
        }
        tbody.innerHTML = items.map(d => {
            const relPct = Math.round((d.relevance_score || 0) * 100);
            const velPct = Math.round((d.velocity_score || 0) * 100);
            const relColor = relPct >= 60 ? '#22c55e' : relPct >= 30 ? '#f59e0b' : '#ef4444';
            const velColor = velPct >= 60 ? '#22c55e' : velPct >= 30 ? '#f59e0b' : '#ef4444';
            const riskClass = d.risk_level === 'low' ? 'risk-low' : d.risk_level === 'medium' ? 'risk-medium' : 'risk-high';
            return `<tr onclick="App.toggleDiscovery(this)" data-id="${d.id}">
                <td><span class="source-badge source-${d.source}">${d.source}</span></td>
                <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${this.escapeHtml(d.title || '')}</td>
                <td>${relPct}%<span class="score-bar"><span class="score-fill" style="width:${relPct}%;background:${relColor}"></span></span></td>
                <td>${velPct}%<span class="score-bar"><span class="score-fill" style="width:${velPct}%;background:${velColor}"></span></span></td>
                <td class="${riskClass}">${d.risk_level || '—'}</td>
                <td><span class="badge badge-indigo">${d.status || 'new'}</span></td>
                <td class="tabular" style="color:#555">${this.timeAgo(d.discovered_at)}</td>
            </tr>`;
        }).join('');
    },

    toggleDiscovery(row) {
        // Simple toggle - for a full implementation, would show expanded detail below the row
        row.classList.toggle('expanded');
    },

    filterDiscoveries(chip) {
        document.querySelectorAll('#discFilters .filter-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        this.state.discFilter = chip.dataset.status;
        this.fetchViewData('discoveries');
    },

    renderApproval() {
        const data = this.state.approvalData || {};
        const groups = data.variant_groups || [];
        const ungrouped = data.ungrouped || [];
        const total = data.total || 0;

        if (!this.state.approvalFilter) this.state.approvalFilter = 'all';

        document.getElementById('approvalCountBadge').textContent = total + ' pending';

        if (total === 0) {
            document.getElementById('approvalGroups').innerHTML = '';
            document.getElementById('approvalFilterBar').innerHTML = '';
            document.getElementById('approvalEmpty').style.display = 'block';
            return;
        }
        document.getElementById('approvalEmpty').style.display = 'none';

        // Count platforms for filter pills
        const platformCounts = {};
        const allItems = [];
        for (const g of groups) {
            for (const v of (g.variants || [])) {
                const p = (v.platform || 'unknown').toLowerCase();
                platformCounts[p] = (platformCounts[p] || 0) + 1;
                allItems.push(v);
            }
        }
        for (const c of ungrouped) {
            const p = (c.platform || 'unknown').toLowerCase();
            platformCounts[p] = (platformCounts[p] || 0) + 1;
            allItems.push(c);
        }

        // Render filter pills
        const af = this.state.approvalFilter;
        let filterHtml = `<button class="approval-filter-pill ${af === 'all' ? 'active' : ''}" onclick="App.filterApproval('all')">All (${total})</button>`;
        for (const [plat, count] of Object.entries(platformCounts).sort((a,b) => b[1] - a[1])) {
            filterHtml += `<button class="approval-filter-pill ${af === plat ? 'active' : ''}" onclick="App.filterApproval('${plat}')">${plat.charAt(0).toUpperCase() + plat.slice(1)} (${count})</button>`;
        }
        document.getElementById('approvalFilterBar').innerHTML = filterHtml;

        const activeFilter = this.state.approvalFilter;
        let html = '';

        // Render variant groups
        for (const group of groups) {
            const variants = group.variants || [];
            if (variants.length === 0) continue;
            const first = variants[0];
            const platform = (first.platform || '').toLowerCase();

            // Filter
            if (activeFilter !== 'all' && platform !== activeFilter) continue;

            const variantHtmlParts = variants.map((v, idx) => {
                const label = v.variant_label || String.fromCharCode(65 + idx);
                const varClass = idx === 0 ? 'variant-a' : 'variant-b';
                const mediaHtml = this._renderApprovalMedia(v.media_urls);
                const videoIndicator = (v.video_script && (v.format === 'short' || v.format === 'short-form'))
                    ? `<div class="video-indicator">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2"/><polygon points="10,8 16,12 10,16"/></svg>
                        Selecting this variant will generate a video
                    </div>` : '';
                const bodyId = 'body-' + v.id;
                const bodyText = this.escapeHtml(v.body || v.body_preview || '');
                return `<div class="approval-variant ${varClass}">
                    <div class="variant-label">${this.escapeHtml(label)}</div>
                    <div class="variant-title">${this.escapeHtml(v.title || '')}</div>
                    ${mediaHtml}
                    <div class="text-clamp" id="${bodyId}">${bodyText}</div>
                    <span class="show-more-link" onclick="App.toggleTextExpand('${bodyId}', this)">Show more</span>
                    ${videoIndicator}
                    <div style="overflow:hidden">
                        <button class="btn-select" onclick="App.selectVariant(${v.id})">&#x2713; Select This</button>
                    </div>
                </div>`;
            });

            const formatBadge = first.format ? `<span class="format-badge">${this.escapeHtml(first.format)}</span>` : '';

            html += `<div class="approval-group" data-platform="${platform}">
                <div class="approval-group-header">
                    <span class="source-badge source-${first.platform || ''}">${(first.platform || '?').toUpperCase()}</span>
                    <span class="source-title">${this.escapeHtml(first.discovery_title || first.title || 'Untitled')}</span>
                    ${formatBadge}
                    <span class="timestamp">${this.timeAgo(first.created_at)}</span>
                    <button class="btn-reject-group" onclick="App.rejectGroup(${first.id})">Reject</button>
                </div>
                <div class="approval-variants-grid">
                    ${variantHtmlParts.join('')}
                </div>
            </div>`;
        }

        // Render ungrouped items
        for (const c of ungrouped) {
            const platform = (c.platform || '').toLowerCase();
            if (activeFilter !== 'all' && platform !== activeFilter) continue;

            const mediaHtml = this._renderApprovalMedia(c.media_urls);
            const videoIndicator = (c.video_script && (c.format === 'short' || c.format === 'short-form'))
                ? `<div class="video-indicator">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2"/><polygon points="10,8 16,12 10,16"/></svg>
                    Approving will generate a video
                </div>` : '';
            const bodyId = 'body-u-' + c.id;
            const bodyText = this.escapeHtml(c.body || c.body_preview || '');
            const formatBadge = c.format ? `<span class="format-badge">${this.escapeHtml(c.format)}</span>` : '';

            html += `<div class="approval-single" data-platform="${platform}">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
                    <span class="source-badge source-${c.platform || ''}">${(c.platform || '?').toUpperCase()}</span>
                    <span style="font-size:13px;color:var(--color-text-secondary)">${this.escapeHtml(c.discovery_title || '')}</span>
                    ${formatBadge}
                    <span style="margin-left:auto;font-size:11px;color:#555">${this.timeAgo(c.created_at)}</span>
                </div>
                <div class="variant-title">${this.escapeHtml(c.title || '')}</div>
                ${mediaHtml}
                <div class="text-clamp" id="${bodyId}">${bodyText}</div>
                <span class="show-more-link" onclick="App.toggleTextExpand('${bodyId}', this)">Show more</span>
                ${videoIndicator}
                <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
                    <button class="btn btn-success" style="font-size:12px;padding:6px 16px" onclick="App.approveCreation(${c.id})">&#x2713; Approve</button>
                    <button class="btn-reject-group" onclick="App.rejectCreation(${c.id})">Reject</button>
                </div>
            </div>`;
        }

        document.getElementById('approvalGroups').innerHTML = html;
    },

    toggleTextExpand(id, linkEl) {
        const el = document.getElementById(id);
        if (!el) return;
        const expanded = el.classList.toggle('expanded');
        if (linkEl) linkEl.textContent = expanded ? 'Show less' : 'Show more';
    },

    filterApproval(platform) {
        this.state.approvalFilter = platform;
        this.renderApproval();
    },

    _renderApprovalMedia(mediaUrls) {
        if (!mediaUrls || !Array.isArray(mediaUrls) || mediaUrls.length === 0) return '';
        const images = mediaUrls.filter(m => m.type === 'image' && m.url);
        const videos = mediaUrls.filter(m => m.type === 'video' && m.url);

        let html = '';
        if (images.length === 1) {
            html += `<img class="approval-image" src="${this.escapeHtml(images[0].url)}" alt="" loading="lazy" />`;
        } else if (images.length > 1) {
            html += '<div class="approval-images-row">';
            for (const img of images) {
                html += `<img src="${this.escapeHtml(img.url)}" alt="" loading="lazy" />`;
            }
            html += '</div>';
        }

        for (const v of videos) {
            html += `<div class="video-placeholder">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="5,3 19,12 5,21"/></svg>
                <span>Video ready &middot; <a href="${this.escapeHtml(v.url)}" target="_blank" style="color:var(--color-primary);text-decoration:none">${v.source || 'view'}</a></span>
            </div>`;
        }

        return html;
    },

    _renderMediaPreview(mediaUrls) {
        if (!mediaUrls || !Array.isArray(mediaUrls) || mediaUrls.length === 0) return '';
        let html = '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">';
        for (const m of mediaUrls) {
            if (m.type === 'image' && m.url) {
                html += `<img src="${this.escapeHtml(m.url)}" style="max-width:120px;max-height:80px;border-radius:var(--radius-sm);object-fit:cover" />`;
            } else if (m.type === 'video' && m.url) {
                html += `<a href="${this.escapeHtml(m.url)}" target="_blank" style="display:inline-flex;align-items:center;gap:4px;font-size:11px;color:var(--color-primary);text-decoration:none">&#x25B6; Video (${m.source || 'video'})</a>`;
            }
        }
        html += '</div>';
        return html;
    },

    async selectVariant(id) {
        await this.api('/approval/' + id + '/select', { method: 'POST' });
        this.fetchViewData('approval');
    },

    async rejectGroup(id) {
        await this.api('/approval/' + id + '/reject-group', { method: 'POST' });
        this.fetchViewData('approval');
    },

    renderContent() {
        const items = Array.isArray(this.state.creations) ? this.state.creations : [];
        const pending = items.filter(c => c.approval_status === 'pending');
        const processed = items.filter(c => c.approval_status !== 'pending');

        const renderCard = (c) => {
            const riskPct = Math.round((c.risk_score || 0) * 100);
            const riskColor = riskPct >= 60 ? '#ef4444' : riskPct >= 30 ? '#f59e0b' : '#22c55e';
            const flags = (c.risk_flags || []).map(f => `<span class="content-flag">${this.escapeHtml(f)}</span>`).join('');
            const isPending = c.approval_status === 'pending';
            return `<div class="content-card ${c.approval_status}" data-id="${c.id}">
                <div class="content-card-header">
                    <span class="source-badge source-${c.platform || ''}">${c.platform || '?'}</span>
                    <span class="content-platform">${c.format || ''}</span>
                    <span style="margin-left:auto;font-size:11px;color:#555">${this.timeAgo(c.created_at)}</span>
                </div>
                <div class="content-body">${this.escapeHtml(c.body_preview || c.body || '')}</div>
                <div class="content-risk-bar"><div class="content-risk-fill" style="width:${riskPct}%;background:${riskColor}"></div></div>
                ${flags ? '<div class="content-flags">' + flags + '</div>' : ''}
                ${isPending ? `<div class="content-actions">
                    <button class="btn btn-success" onclick="App.approveCreation(${c.id})">Approve</button>
                    <button class="btn btn-danger" onclick="App.rejectCreation(${c.id})">Reject</button>
                </div>` : `<span class="badge ${c.approval_status === 'approved' ? 'badge-green' : 'badge-red'}">${c.approval_status}</span>`}
            </div>`;
        };

        document.getElementById('contentPending').innerHTML = pending.length
            ? pending.map(renderCard).join('')
            : '<div style="color:#555;font-size:13px;padding:20px;text-align:center">No pending content</div>';
        document.getElementById('contentProcessed').innerHTML = processed.length
            ? processed.map(renderCard).join('')
            : '<div style="color:#555;font-size:13px;padding:20px;text-align:center">No processed content</div>';
    },

    renderSkills() {
        const skills = this.state.skills || [];
        document.getElementById('skillsCountBadge').textContent = skills.length + ' skills';

        // Identify evolved skills (version > 1)
        const evolvedSkills = skills.filter(s => s.version > 1).sort((a, b) => b.confidence - a.confidence).slice(0, 6);
        const regularSkills = skills;

        // Group by category
        const grouped = {};
        regularSkills.forEach(s => {
            const cat = s.category || 'other';
            (grouped[cat] = grouped[cat] || []).push(s);
        });

        const catIcons = {
            sources: '🔍',
            creation: '✍️',
            platform: '📱',
            tools: '🛠',
            engagement: '💬',
            timing: '⏰'
        };

        let html = '';

        // Evolution Showcase Section
        if (evolvedSkills.length > 0) {
            html += `<div class="skills-evolution-showcase">
                <div class="evolution-showcase-title">
                    ✨ Evolved Skills (${evolvedSkills.length})
                </div>
                <div class="evolution-showcase-grid stagger-children">`;

            evolvedSkills.forEach(s => {
                const currentConf = Math.round((s.confidence || 0) * 100);
                const initialConf = 50; // Assume all skills start at 0.5
                const delta = currentConf - initialConf;
                const version = s.version || 1;

                html += `<div class="evolution-card" onclick="App.toggleSkillDetail(this, '${s.name}')">
                    <div class="evolution-card-name">${s.name}</div>

                    <div class="version-timeline">
                        <div class="version-node">
                            <div class="version-badge v1">v1</div>
                        </div>
                        <div class="version-arrow">→</div>
                        <div class="version-node">
                            <div class="version-badge v2">v2</div>
                        </div>
                        ${version >= 3 ? `
                        <div class="version-arrow">→</div>
                        <div class="version-node">
                            <div class="version-badge v3">v3</div>
                        </div>` : ''}
                    </div>

                    <div class="evolution-progress">
                        <div class="evolution-progress-fill" style="width:${currentConf}%"></div>
                    </div>

                    <div class="evolution-stats">
                        <div class="evolution-confidence">${currentConf}%</div>
                        <div class="evolution-delta">
                            ↑ ${delta > 0 ? '+' : ''}${delta}%
                        </div>
                    </div>

                    <div class="evolution-uses">${s.total_uses || 0} uses</div>
                    <div class="skill-detail-panel" data-skill="${s.name}"></div>
                </div>`;
            });

            html += '</div></div>';
        }

        // Regular Skills by Category
        for (const [cat, items] of Object.entries(grouped)) {
            html += `<div class="skills-category">
                <div class="skills-category-title">${catIcons[cat] || ''} ${cat.toUpperCase()}</div>
                <div class="skills-grid">`;

            items.forEach(s => {
                const pct = Math.round((s.confidence || 0) * 100);
                const barColor = pct >= 60 ? '#22c55e' : pct >= 30 ? '#f59e0b' : '#ef4444';
                const healthStatus = s.health?.status || 'unknown';
                const healthDot = healthStatus === 'healthy' ? 'health-ok' : healthStatus === 'stale' ? 'health-warn' : 'health-bad';

                html += `<div class="skill-card" onclick="App.toggleSkillDetail(this, '${s.name}')">
                    <div class="skill-card-header">
                        <span class="skill-name">${s.name}</span>
                        <span class="skill-version">v${s.version}</span>
                    </div>
                    <div class="skill-meta">${s.total_uses || 0} uses</div>
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width:${pct}%;background:${barColor}"></div>
                    </div>
                    <div class="skill-footer">
                        <span class="skill-conf" style="color:${barColor}">${pct}%</span>
                        <span style="font-size:11px;color:var(--color-text-disabled)">
                            <span class="skill-health-dot ${healthDot}"></span>${healthStatus}
                        </span>
                    </div>
                    <div class="skill-detail-panel" data-skill="${s.name}"></div>
                </div>`;
            });

            html += '</div></div>';
        }

        document.getElementById('skillsContainer').innerHTML = html || '<div style="color:var(--color-text-disabled);text-align:center;padding:30px">No skills loaded</div>';
    },

    async toggleSkillDetail(card, name) {
        const panel = card.querySelector('.skill-detail-panel');
        if (panel.classList.contains('open')) {
            panel.classList.remove('open');
            return;
        }
        // Load detail + history
        const [detail, history] = await Promise.all([
            this.api('/skills/' + encodeURIComponent(name)),
            this.api('/skills/' + encodeURIComponent(name) + '/history'),
        ]);
        let html = '';
        if (detail) {
            html += `<div style="margin-bottom:8px"><strong>Tags:</strong> ${(detail.tags || []).join(', ') || 'none'}</div>`;
            html += `<div style="margin-bottom:8px"><strong>Success count:</strong> ${detail.success_count || 0} / ${detail.total_uses || 0}</div>`;
        }
        if (history && history.history && history.history.length) {
            html += '<div style="margin-top:8px"><strong>Recent outcomes:</strong></div>';
            history.history.slice(0, 5).forEach(h => {
                const color = h.outcome === 'success' ? '#22c55e' : h.outcome === 'failure' ? '#ef4444' : '#f59e0b';
                html += `<div style="font-size:11px;margin-top:2px"><span style="color:${color}">${h.outcome}</span> — ${h.agent} — ${this.timeAgo(h.recorded_at)}</div>`;
            });
        }
        html += `<button class="btn btn-ghost" style="margin-top:8px;font-size:11px;height:26px" onclick="event.stopPropagation();App.forceReview('${name}')">Force Review</button>`;
        panel.innerHTML = html;
        panel.classList.add('open');
    },

    renderBrand() {
        const pb = this.state.playbook || {};
        document.getElementById('brandName').value = pb.brand_name || '';
        document.getElementById('brandVoice').value = pb.voice_guide || '';
        this.state.brandTopics = pb.topics || [];
        this.state.brandAvoidTopics = pb.avoid_topics || [];
        this.state.brandCompetitors = pb.competitors || [];
        this.renderTags('topicsWrap', this.state.brandTopics);
        this.renderTags('avoidTopicsWrap', this.state.brandAvoidTopics);
        this.renderTags('competitorsWrap', this.state.brandCompetitors);
    },

    renderPerformance() {
        const arb = this.state.arbitrage || {};
        const costs = this.state.costs || {};
        const avgHrs = ((arb.avg_arbitrage_minutes || 0) / 60).toFixed(1);
        const maxHrs = ((arb.max_arbitrage_minutes || 0) / 60).toFixed(1);
        const totalPubs = arb.total_publications_with_arbitrage || 0;
        const totalCost = costs.total_cost || 127;
        const savings = ((45000 - totalCost) / 45000 * 100).toFixed(1);

        document.getElementById('perfScoreboard').innerHTML = `
            <div class="perf-card highlight anim-scale">
                <div class="perf-value">${avgHrs}h</div>
                <div class="perf-label">Avg Time Ahead</div>
                <div class="perf-subtitle">vs competitors at 0.0h</div>
                <div class="perf-comparison">
                    <div class="perf-comparison-fill" style="width:100%"></div>
                </div>
            </div>
            <div class="perf-card highlight anim-scale" style="animation-delay: 50ms">
                <div class="perf-value">${maxHrs}h</div>
                <div class="perf-label">Max Arbitrage Window</div>
                <div class="perf-subtitle">Record time advantage</div>
            </div>
            <div class="perf-card highlight anim-scale" style="animation-delay: 100ms">
                <div class="perf-value">${totalPubs}</div>
                <div class="perf-label">Posts with Arbitrage</div>
                <div class="perf-subtitle">Out of ${this.state.pipeline?.counts?.publications || totalPubs} total</div>
            </div>
            <div class="perf-card highlight anim-scale" style="animation-delay: 150ms">
                <div class="perf-value">${savings}%</div>
                <div class="perf-label">Cost Savings</div>
                <div class="perf-subtitle">$${totalCost.toFixed(2)} vs $45K/month</div>
                <div class="perf-comparison">
                    <div class="perf-comparison-fill" style="width:${savings}%"></div>
                </div>
                <div class="perf-comparison-label">
                    <span>Autopilot</span>
                    <span>Human team</span>
                </div>
            </div>`;

        const pubs = Array.isArray(this.state.publications) ? this.state.publications : [];
        document.getElementById('perfTableBody').innerHTML = pubs.length
            ? pubs.map(p => {
                const arbMin = p.arbitrage_window_minutes || 0;
                const arbHrs = (arbMin / 60).toFixed(1);
                const arbColor = arbMin > 360 ? '#22c55e' : arbMin > 120 ? '#f59e0b' : '#6b7280';
                return `<tr>
                    <td><span class="source-badge source-${p.platform || ''}">${p.platform || '?'}</span></td>
                    <td class="tabular" style="color:${arbColor};font-weight:600">
                        ${arbMin ? arbHrs + 'h ahead' : '—'}
                    </td>
                    <td class="tabular" style="color:var(--color-text-disabled)">${this.timeAgo(p.published_at)}</td>
                </tr>`;
            }).join('')
            : '<tr><td colspan="3" style="text-align:center;color:var(--color-text-disabled);padding:var(--space-6)">No publications yet</td></tr>';
    },

    // ── Actions ────────────────────────────────────────

    async triggerScout() {
        const btn = document.getElementById('pipelineRunBtn');
        const text = document.getElementById('pipelineRunText');
        btn.disabled = true;
        text.innerHTML = '<span class="spinner"></span> Running...';
        await this.api('/discover', { method: 'POST' });
        btn.disabled = false;
        text.textContent = 'Run Full Pipeline';
        this.fetchViewData('pipeline');
    },

    async approveCreation(id) {
        await this.api('/creations/' + id + '/approve', { method: 'POST' });
        this.fetchViewData('content');
    },

    async rejectCreation(id) {
        await this.api('/creations/' + id + '/reject', { method: 'POST' });
        this.fetchViewData('content');
    },

    async forceReview(name) {
        await this.api('/skills/' + encodeURIComponent(name) + '/review', { method: 'POST' });
        this.fetchViewData('skills');
    },

    // ── Brand Wizard ───────────────────────────────────

    wizardNext() {
        if (this.state.wizardStep === 3) {
            this.savePlaybook();
            return;
        }
        this.state.wizardStep++;
        this.updateWizard();
    },

    wizardPrev() {
        if (this.state.wizardStep === 0) return;
        this.state.wizardStep--;
        this.updateWizard();
    },

    updateWizard() {
        const step = this.state.wizardStep;
        document.querySelectorAll('.wizard-step').forEach((el, i) => {
            el.className = 'wizard-step' + (i < step ? ' done' : i === step ? ' active' : '');
        });
        document.querySelectorAll('.wizard-panel').forEach((el, i) => {
            el.classList.toggle('active', i === step);
        });
        document.getElementById('wizardPrev').disabled = step === 0;
        document.getElementById('wizardNext').textContent = step === 3 ? 'Save & Activate' : 'Next';
    },

    async savePlaybook() {
        const data = {
            brand_name: document.getElementById('brandName').value || null,
            voice_guide: document.getElementById('brandVoice').value || null,
            topics: this.state.brandTopics.length ? this.state.brandTopics : null,
            avoid_topics: this.state.brandAvoidTopics.length ? this.state.brandAvoidTopics : null,
            competitors: this.state.brandCompetitors.length ? this.state.brandCompetitors : null,
        };
        await this.api('/playbook', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        // Show confirmation
        const btn = document.getElementById('wizardNext');
        btn.textContent = 'Saved!';
        btn.style.background = '#22c55e';
        setTimeout(() => {
            btn.textContent = 'Save & Activate';
            btn.style.background = '';
        }, 2000);
    },

    // ── Tag Input ──────────────────────────────────────

    renderTags(wrapId, tags) {
        const wrap = document.getElementById(wrapId);
        const input = wrap.querySelector('.tag-text-input');
        // Remove existing tags
        wrap.querySelectorAll('.tag').forEach(t => t.remove());
        // Add tags before input
        tags.forEach((t, i) => {
            const el = document.createElement('span');
            el.className = 'tag';
            el.innerHTML = this.escapeHtml(t) + ' <span class="tag-remove" onclick="App.removeTag(\\'' + wrapId + '\\',' + i + ')">&times;</span>';
            wrap.insertBefore(el, input);
        });
    },

    removeTag(wrapId, index) {
        const key = wrapId === 'topicsWrap' ? 'brandTopics' : wrapId === 'avoidTopicsWrap' ? 'brandAvoidTopics' : 'brandCompetitors';
        this.state[key].splice(index, 1);
        this.renderTags(wrapId, this.state[key]);
    },

    setupTagInputs() {
        const configs = [
            { inputId: 'topicsInput', wrapId: 'topicsWrap', key: 'brandTopics' },
            { inputId: 'avoidTopicsInput', wrapId: 'avoidTopicsWrap', key: 'brandAvoidTopics' },
            { inputId: 'competitorsInput', wrapId: 'competitorsWrap', key: 'brandCompetitors' },
        ];
        configs.forEach(({ inputId, wrapId, key }) => {
            document.getElementById(inputId).addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const val = e.target.value.trim();
                    if (val) {
                        this.state[key].push(val);
                        e.target.value = '';
                        this.renderTags(wrapId, this.state[key]);
                    }
                }
            });
        });
    },

    // ── Utils ──────────────────────────────────────────

    escapeHtml(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    },

    timeAgo(isoStr) {
        if (!isoStr) return '—';
        const diff = Date.now() - new Date(isoStr).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return 'just now';
        if (mins < 60) return mins + 'm ago';
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return hrs + 'h ago';
        return Math.floor(hrs / 24) + 'd ago';
    },

    updateUptime() {
        const elapsed = Math.floor((Date.now() - this.state.startTime) / 1000);
        const d = Math.floor(elapsed / 86400);
        const h = Math.floor((elapsed % 86400) / 3600);
        const m = Math.floor((elapsed % 3600) / 60);
        const s = elapsed % 60;

        let uptime = '';
        if (d > 0) {
            uptime = `${d}d ${h}h ${m}m`;
        } else if (h > 0) {
            uptime = `${h}h ${m}m ${s}s`;
        } else {
            uptime = `${m}m ${s}s`;
        }

        document.getElementById('headerUptime').textContent = uptime;
    },

    // ── Init ───────────────────────────────────────────

    async init() {
        this.connectChat();
        this.setupTagInputs();
        setInterval(() => this.updateUptime(), 1000);

        // Initial data fetch
        await this.fetchAll();

        // Background polling for active view data
        this.state.pollTimer = setInterval(() => {
            if (this.state.activeView !== 'chat') {
                this.fetchViewData(this.state.activeView);
            }
        }, 5000);

        // Voice preview
        document.getElementById('brandVoice').addEventListener('input', (e) => {
            const preview = document.getElementById('voicePreview');
            if (e.target.value) {
                preview.textContent = 'Voice guide: "' + e.target.value.substring(0, 100) + (e.target.value.length > 100 ? '...' : '') + '"';
            } else {
                preview.textContent = 'Preview will appear as you type...';
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Escape to close agent detail panel
            if (e.key === 'Escape') {
                const panel = document.getElementById('agentDetailPanel');
                if (panel.classList.contains('open')) {
                    this.closeAgentDetail();
                }
            }
        });
    },
};

document.addEventListener('DOMContentLoaded', () => App.init());
</script>
</body>
</html>
"""


@dashboard_router.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML
