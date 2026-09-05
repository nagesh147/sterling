import React from 'react';

/**
 * The empty/idle/loading well.
 *
 * Exists as a primitive because the surface this replaced had one string —
 * "Replay stepping through bars... No signals triggered yet." — shown in every
 * case including the idle one, where nothing was stepping through anything.
 */
export function EmptyState({
  icon,
  title,
  detail,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  detail?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="rd-empty" role="status">
      {icon && <span className="rd-empty-icon">{icon}</span>}
      <span className="rd-empty-title">{title}</span>
      {detail && <span>{detail}</span>}
      {action}
    </div>
  );
}
