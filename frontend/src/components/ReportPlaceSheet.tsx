// src/components/ReportPlaceSheet.tsx
//
// Place-level counterpart to ReportPhotoSheet.tsx: that one is for a
// bad/wrong photo specifically, this is for something wrong about the
// place itself -- wrong hours, a closure, a duplicate listing, or wrong
// menu info. Neither automatically changes the place -- every report
// lands in a human review queue (see app/api/v1/routes/moderation.py's
// place-report endpoints).
//
// Thin wrapper around the shared ReportSheet -- see ReportSheet.tsx for
// the actual Modal/backdrop/submit implementation.
import React from 'react';

import { ReportSheet } from './ReportSheet';
import { PLACE_REPORT_REASONS, PlaceReportReason, reportPlace } from '../api/social';

interface Props {
  visible: boolean;
  placeId: string | null;
  onClose: () => void;
  onReported?: () => void;
}

export function ReportPlaceSheet({ visible, placeId, onClose, onReported }: Props) {
  return (
    <ReportSheet<PlaceReportReason>
      visible={visible}
      entityId={placeId}
      onClose={onClose}
      onReported={onReported}
      config={{
        reasons: PLACE_REPORT_REASONS,
        title: 'Report an issue',
        subtitle: 'Thanks — reports are reviewed by a person, not acted on automatically.',
        signInMessage: 'Sign in to report an issue.',
        submit: reportPlace,
        resetErrorOnClose: true,
      }}
    />
  );
}
