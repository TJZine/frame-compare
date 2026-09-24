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
        return `${Math.round(fps * 1000) / 1000} fps`;
    },

    formatRuntime(frameCount, fps) {
        const frames = Number(frameCount);
        const rate = Number(fps);
        if (!Number.isFinite(frames) || !Number.isFinite(rate) || frames < 0 || rate <= 0) return '';
        const totalSeconds = Math.floor(frames / rate);
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    },

    formatTimestamp(value) {
        if (typeof value !== 'string' || !value) return '';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '';
        return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
    },

    formatFileSize(value) {
        const bytes = Number(value);
        if (!Number.isFinite(bytes) || bytes <= 0) return '';
        const unit = 1024;
        if (bytes >= unit ** 4) return `${(bytes / unit ** 4).toFixed(2)} TiB`;
        if (bytes >= unit ** 3) return `${(bytes / unit ** 3).toFixed(2)} GiB`;
        if (bytes >= unit ** 2) return `${(bytes / unit ** 2).toFixed(2)} MiB`;
        if (bytes >= unit) return `${(bytes / unit).toFixed(2)} KiB`;
        return `${bytes.toFixed(2)} B`;
    },

    formatResolution(resolution) {
        if (!Array.isArray(resolution) || resolution.length !== 2) return '';
        const [width, height] = resolution;
        if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
            return '';
        }
        return `${width}×${height}`;
    },

    stageDynamicRangeWords() {
        return ['HDR', 'HDR10', 'HDR10+', 'DV', 'HLG', 'SDR'];
    },

    stageLabelNeedsRangeWord(name) {
        const words = new Set(
            String(name ?? '').split(/[^A-Za-z0-9+]+/).filter(Boolean),
        );
        return !this.stageDynamicRangeWords().some(word => words.has(word));
    },

    stageLabelSegments(clip, profile = 'control') {
        const name = this.clipDisplay(clip, profile);
        const meta = [
            this.formatResolution(clip.resolution),
            this.stageLabelNeedsRangeWord(name) ? (clip.signal?.is_hdr === true ? 'HDR' : 'SDR') : '',
            this.formatFileSize(clip.size_bytes),
        ].filter(Boolean).join(' · ');
        return { name, meta };
    },

    sourceHudLabel(clip, profile = 'control') {
        const { name, meta } = this.stageLabelSegments(clip, profile);
        if (!name) return meta;
        return meta ? `${name} · ${meta}` : name;
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

    formatActivePicture(active, resolution) {
        const frame = this.formatResolution(resolution);
        if (!frame) return '';
        if (!active) return `${frame} · full frame`;
        const left = Number(active.x) ? `, ${active.x} px left` : '';
        const provenance = active.provenance === 'dolby_vision_l5' ? ' · DV L5' : '';
        return `${frame} · active ${active.width}×${active.height}, ${active.y} px top${left}${provenance}`;
    },

    clipBadge(signal) {
        if (signal?.dolby_vision_rpu === true && signal?.is_hdr === true) return 'DV HDR';
        return signal?.is_hdr ? 'HDR' : 'SDR';
    },

    formatGroupedFrames(frameCount) {
        const frames = Number(frameCount);
        if (!Number.isFinite(frames) || frames < 0) return '';
        const whole = Math.floor(frames);
        return `${whole.toLocaleString('en-US')} ${whole === 1 ? 'frame' : 'frames'}`;
    },

    clipLengthText(clip) {
        const frames = this.formatGroupedFrames(clip?.frame_count);
        const runtime = this.formatRuntime(clip?.frame_count, clip?.fps);
        return [frames, runtime].filter(Boolean).join(' · ');
    },

    clipFpsText(clip) {
        const fps = this.formatFps(clip?.fps);
        if (!fps) return '';
        const num = clip?.fps_num;
        const den = clip?.fps_den;
        if (Number.isInteger(num) && Number.isInteger(den) && den !== 0) {
            return `${fps} (${num}/${den})`;
        }
        return fps;
    },

    sharedClipValues(clips) {
        const list = Array.isArray(clips) ? clips : [];
        const only = values => (values.size === 1 ? [...values][0] || null : null);
        const fpsValues = new Set(list.map(clip => this.clipFpsText(clip)));
        const presentationValues = new Set(list.map(clip => this.formatPresentation(clip)));
        return { fps: only(fpsValues), presentation: only(presentationValues) };
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
        return 'Comparison';
    },
};
