// src/components/MapMarker.tsx
import React from 'react';
import { CraveMapPin } from '../ui-v2/components';

interface Props {
  /**
   * Legacy compatibility prop. UI V2 no longer uses arbitrary tier colors for
   * ordinary map pins; presentation is semantic (normal / selected / closed /
   * cluster). Keep this prop until MapScreenCore is fully migrated so callers
   * do not need a broad synchronized rewrite.
   */
  color?: string;
  size?: number;
}

interface ClusterProps {
  count: number;
}

/**
 * Compatibility bridge for the legacy MapScreenCore call site.
 *
 * Cluster styling is now owned by CraveMapPin so map density no longer creates
 * a second visual language beside UI V2.
 */
export function MapClusterDot({ count }: ClusterProps) {
  return <CraveMapPin clusterCount={count} />;
}

/**
 * Compatibility bridge for the legacy MapScreenCore call site.
 *
 * `color` and `size` are intentionally ignored. Ranking tiers must not create
 * a rainbow of recommendation pins; normal pin appearance is owned by the
 * semantic UI V2 component. This adapter can be deleted once MapScreenCore
 * renders CraveMapPin directly.
 */
export function MapMarkerDot(_props: Props) {
  return <CraveMapPin />;
}
