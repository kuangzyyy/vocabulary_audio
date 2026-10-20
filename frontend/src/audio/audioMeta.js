export const ACCENT_LABELS = {
  us: '美式',
  uk: '英式',
  unknown: '口音未标注',
};

export function accentLabel(accent) {
  return ACCENT_LABELS[accent] ?? ACCENT_LABELS.unknown;
}

export function accentOptions(metadata) {
  const raw = Array.isArray(metadata?.available_accents)
    ? metadata.available_accents
    : [];
  const available = [...new Set(raw)].filter(
    (accent) => Object.prototype.hasOwnProperty.call(ACCENT_LABELS, accent),
  );
  return {
    available,
    canChoose: available.includes('us') && available.includes('uk'),
  };
}

export function sourceLicenseText(metadata) {
  if (!metadata) {
    return '';
  }
  return [metadata.license, metadata.attribution].filter(Boolean).join(' · ');
}
