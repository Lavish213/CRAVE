// src/components/ReportPhotoSheet.tsx
//
// The user-facing half of moderation. Automated screening catches what it
// can measure — unsafe, blurry, duplicate — but it cannot tell that a
// sharp, well-lit, perfectly safe photo is of the wrong restaurant. Only a
// person looking at it can, so there has to be somewhere for them to say so.
//
// Thin wrapper around the shared ReportSheet -- see ReportSheet.tsx for
// the actual Modal/backdrop/submit implementation.
import React from 'react';

import { ReportSheet } from './ReportSheet';
import { REPORT_REASONS, ReportReason, reportImage } from '../api/social';

interface Props {
  visible: boolean;
  imageId: string | null;
  onClose: () => void;
  onReported?: () => void;
}

export function ReportPhotoSheet({ visible, imageId, onClose, onReported }: Props) {
  return (
    <ReportSheet<ReportReason>
      visible={visible}
      entityId={imageId}
      onClose={onClose}
      onReported={onReported}
      config={{
        reasons: REPORT_REASONS,
        title: 'Report this photo',
        subtitle:
          'Thanks — reports are reviewed, and photos flagged by several people are hidden while we look.',
        signInMessage: 'Sign in to report a photo.',
        submit: reportImage,
      }}
    />
  );
}
