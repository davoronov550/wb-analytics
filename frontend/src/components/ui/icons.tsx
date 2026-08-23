import type { ReactNode, SVGProps } from "react";

/** Minimal stroke-icon set (currentColor, 1.6 stroke) — no icon dependency. */
type IconProps = SVGProps<SVGSVGElement>;

function Base({ children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export const IconOverview = (p: IconProps) => (
  <Base {...p}>
    <rect x="3" y="3" width="7" height="9" rx="1.5" />
    <rect x="14" y="3" width="7" height="5" rx="1.5" />
    <rect x="14" y="12" width="7" height="9" rx="1.5" />
    <rect x="3" y="16" width="7" height="5" rx="1.5" />
  </Base>
);

export const IconCatalog = (p: IconProps) => (
  <Base {...p}>
    <line x1="4" y1="6" x2="20" y2="6" />
    <line x1="4" y1="12" x2="20" y2="12" />
    <line x1="4" y1="18" x2="20" y2="18" />
    <circle cx="4" cy="6" r="0.6" fill="currentColor" />
    <circle cx="4" cy="12" r="0.6" fill="currentColor" />
    <circle cx="4" cy="18" r="0.6" fill="currentColor" />
  </Base>
);

export const IconAnalytics = (p: IconProps) => (
  <Base {...p}>
    <line x1="4" y1="20" x2="20" y2="20" />
    <rect x="6" y="11" width="3" height="6" rx="0.5" />
    <rect x="11" y="7" width="3" height="10" rx="0.5" />
    <rect x="16" y="13" width="3" height="4" rx="0.5" />
  </Base>
);

export const IconHistory = (p: IconProps) => (
  <Base {...p}>
    <polyline points="3 15 9 9 13 13 21 5" />
    <polyline points="16 5 21 5 21 10" />
  </Base>
);

export const IconSchedule = (p: IconProps) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="8" />
    <polyline points="12 8 12 12 15 14" />
  </Base>
);

export const IconAlert = (p: IconProps) => (
  <Base {...p}>
    <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.7 21a2 2 0 0 1-3.4 0" />
  </Base>
);

export const IconSaved = (p: IconProps) => (
  <Base {...p}>
    <path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z" />
  </Base>
);

export const IconSettings = (p: IconProps) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 6 19.4l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H2a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4 6l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V2a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H22a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
  </Base>
);

export const IconSearch = (p: IconProps) => (
  <Base {...p}>
    <circle cx="11" cy="11" r="7" />
    <line x1="16.5" y1="16.5" x2="21" y2="21" />
  </Base>
);

export const IconMenu = (p: IconProps) => (
  <Base {...p}>
    <line x1="4" y1="7" x2="20" y2="7" />
    <line x1="4" y1="12" x2="20" y2="12" />
    <line x1="4" y1="17" x2="20" y2="17" />
  </Base>
);

export const IconChevron = (p: IconProps) => (
  <Base {...p}>
    <polyline points="9 6 15 12 9 18" />
  </Base>
);

export const IconLogout = (p: IconProps) => (
  <Base {...p}>
    <path d="M15 4h3a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-3" />
    <polyline points="10 8 6 12 10 16" />
    <line x1="6" y1="12" x2="16" y2="12" />
  </Base>
);

export const IconLock = (p: IconProps) => (
  <Base {...p}>
    <rect x="5" y="11" width="14" height="9" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </Base>
);

export const IconClose = (p: IconProps) => (
  <Base {...p}>
    <line x1="6" y1="6" x2="18" y2="18" />
    <line x1="18" y1="6" x2="6" y2="18" />
  </Base>
);

export const IconCheck = (p: IconProps) => (
  <Base {...p}>
    <polyline points="4 12 10 18 20 6" />
  </Base>
);

export const IconSpark = (p: IconProps) => (
  <Base {...p}>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />
  </Base>
);

export const IconExternal = (p: IconProps) => (
  <Base {...p}>
    <path d="M14 4h6v6" />
    <path d="M20 4 10 14" />
    <path d="M18 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5" />
  </Base>
);

export const IconSort = (p: IconProps) => (
  <Base {...p}>
    <path d="M8 4v16M8 20l-3-3M8 4l3 3" />
    <path d="M16 20V4M16 4l3 3M16 20l-3-3" />
  </Base>
);

export const IconChevronsLeft = (p: IconProps) => (
  <Base {...p}>
    <polyline points="11 6 5 12 11 18" />
    <polyline points="18 6 12 12 18 18" />
  </Base>
);

export const IconChevronsRight = (p: IconProps) => (
  <Base {...p}>
    <polyline points="13 6 19 12 13 18" />
    <polyline points="6 6 12 12 6 18" />
  </Base>
);
