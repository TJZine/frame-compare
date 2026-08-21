const ViewerFormat = {
    clipDisplay(clip, profile = 'control') {
        return clip.display[profile];
    },

    clipFilename(clip) {
        return clip.display.filename;
    },

    clipAccessibleName(clip) {
        const primary = this.clipDisplay(clip, 'primary');
        const filename = this.clipFilename(clip);
        return filename && filename !== primary ? `${primary} — ${filename}` : primary;
    },

    formatFps(value) {
        const fps = Number(value);
        if (!Number.isFinite(fps)) return '';
        return `${Number.isInteger(fps) ? fps : fps.toString()} fps`;
    },

    formatFileSize(value) {
        const bytes = Number(value);
        if (!Number.isFinite(bytes) || bytes <= 0) return '';
        const unit = 1024;
        if (bytes >= unit ** 4) return `${(bytes / unit ** 4).toFixed(2)} TiB`;
        if (bytes >= unit ** 3) return `${(bytes / unit ** 3).toFixed(2)} GiB`;
        return `${(bytes / unit ** 2).toFixed(2)} MiB`;
    },

    sourceHudLabel(clip, profile = 'control') {
        const isHdr = clip.signal?.is_hdr === true;
        return [
            this.clipDisplay(clip, profile),
            `${clip.resolution[0]}×${clip.resolution[1]}`,
            isHdr ? 'HDR' : 'SDR',
            this.formatFileSize(clip.size_bytes),
        ].filter(Boolean).join(' • ');
    },

    signalCodeLabel(kind, value) {
        const labels = {
            primaries: { 1: 'BT.709', 9: 'BT.2020' },
            transfer: { 1: 'BT.709', 13: 'sRGB', 16: 'PQ', 18: 'HLG' },
            matrix: { 0: 'GBR', 1: 'BT.709', 9: 'BT.2020nc', 10: 'BT.2020c' },
        };
        return labels[kind]?.[String(value)] || null;
    },

    formatSignal(signal) {
        if (!signal || typeof signal !== 'object') return '';
        const parts = [signal.is_hdr ? 'HDR' : 'SDR'];
        const color = [
            this.signalCodeLabel('primaries', signal.primaries),
            this.signalCodeLabel('transfer', signal.transfer),
            this.signalCodeLabel('matrix', signal.matrix),
        ].filter(Boolean).join(' / ');
        if (color) parts.push(color);
        if (signal.range === 'limited' || signal.range === 'full') {
            parts.push(signal.range[0].toUpperCase() + signal.range.slice(1));
        }
        if (signal.dolby_vision_rpu === true) parts.push('DV RPU');
        return parts.join(' · ');
    },

    formatToneCurve(value) {
        if (!value) return null;
        const normalized = String(value).toLowerCase();
        if (normalized === 'bt2390') return 'BT.2390';
        if (normalized === 'reinhard') return 'Reinhard';
        if (normalized === 'spline') return 'Spline';
        return normalized.replaceAll('_', ' ');
    },

    formatPresentation(clip) {
        const presentation = clip?.presentation;
        if (!presentation || typeof presentation !== 'object') {
            return clip?.signal?.is_hdr ? 'HDR' : 'SDR';
        }
        if (presentation.state === 'hdr_tonemapped') {
            const curve = this.formatToneCurve(presentation.tone_curve);
            const target = Number.isInteger(presentation.target_nits)
                ? ` → ${presentation.target_nits} nits`
                : '';
            return `Tonemapped${curve ? ` · ${curve}` : ''}${target}`;
        }
        if (presentation.state === 'hdr_tonemap_off') return 'HDR · Tonemap off';
        return 'SDR';
    },

    formatActivePicture(active) {
        if (!active || active.is_full_frame) return '';
        const provenance = active.provenance === 'dolby_vision_l5' ? ' · DV L5' : '';
        return `${active.width}×${active.height} @ ${active.x},${active.y}${provenance}`;
    },

    formatTonemapSummary(tonemap) {
        const settings = tonemap?.settings;
        if (!tonemap?.applied || !settings) return 'Not applied';
        const preset = settings.preset
            ? String(settings.preset).replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase())
            : '';
        const curve = this.formatToneCurve(settings.tone_curve) || '';
        const target = Number.isInteger(settings.target_nits) ? ` · ${settings.target_nits} nits` : '';
        return [preset, curve].filter(Boolean).join(' · ') + target;
    },

    modeLabel(mode) {
        return ({ slider: 'Slider', overlay: 'Single', diff: 'Diff', blink: 'Blink', grid: 'Grid' })[mode] || mode;
    },

    stableClipRole(index, referenceIndex) {
        if (index === referenceIndex) return 'Reference';
        return `Comparison ${index < referenceIndex ? index + 1 : index}`;
    },
};
