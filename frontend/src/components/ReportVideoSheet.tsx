// src/components/ReportVideoSheet.tsx
//
// The video counterpart to ReportPhotoSheet -- same reason set (see
// backend/app/db/models/video_report.py), same low-ceremony pattern:
// pick a reason, done, always reports success (including on the
// server's "already_reported") so nobody is tempted to spam it hoping
// for a different result.
//
// Thin wrapper around the shared ReportSheet -- see ReportSheet.tsx for
// the actual Modal/backdrop/submit implementation.
import React from 'react';

import { ReportSheet } from './ReportSheet';
import { REPORT_REASONS, ReportReason, reportVideo } from '../api/social';

interface Props {
  visible: boolean;
  videoId: string | null;
  onClose: () => void;
  onReported?: () => void;
}

export function ReportVideoSheet({ visible, videoId, onClose, onReported }: Props) {
  return (
    <ReportSheet<ReportReason>
      visible={visible}
      entityId={videoId}
      onClose={onClose}
      onReported={onReported}
      config={{
        reasons: REPORT_REASONS,
        title: 'Report this video',
        subtitle:
          'Thanks — reports are reviewed, and videos flagged by several people are hidden while we look.',
        signInMessage: 'Sign in to report a video.',
        submit: reportVideo,
      }}
    />
  );
}
