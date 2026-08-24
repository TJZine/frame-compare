const Inspector = {
    create(viewer) {
        return {
            viewer,
            focusableVisibility: null,

            cacheDOM() {
                return {
                    btnInspector: document.getElementById('btn-inspector'),
                    inspector: document.getElementById('rv-inspector'),
                    btnInspectorClose: document.getElementById('btn-inspector-close'),
                    inspectorTabs: document.querySelectorAll('[data-inspector-tab]'),
                    inspectorPanels: document.querySelectorAll('.rv-inspector-panel'),
                    inspectorFrameLabel: document.querySelector('[data-inspector-frame-label]'),
                    inspectorFrameNumber: document.querySelector('[data-inspector-frame-number]'),
                    inspectorFrameCategory: document.querySelector('[data-inspector-frame-category]'),
                    inspectorFrameDetail: document.querySelector('[data-inspector-frame-detail]'),
                    inspectorFramePosition: document.querySelector('[data-inspector-frame-position]'),
                    inspectorSourceFrames: document.querySelector('[data-inspector-source-frames]'),
                    inspectorClips: document.querySelector('[data-inspector-clips]'),
                    inspectorAlignPair: document.querySelector('[data-inspector-align-pair]'),
                    inspectorAlignPreset: document.querySelector('[data-inspector-align-preset]'),
                    inspectorAlignX: document.querySelector('[data-inspector-align-x]'),
                    inspectorAlignY: document.querySelector('[data-inspector-align-y]'),
                    btnInspectorResetCurrentAlign: document.getElementById('btn-inspector-reset-current-align'),
                    btnInspectorResetAllAlign: document.getElementById('btn-inspector-reset-all-align'),
                    inspectorExportTitle: document.querySelector('[data-inspector-export-title]'),
                    inspectorExportId: document.querySelector('[data-inspector-export-id]'),
                    inspectorExportGenerated: document.querySelector('[data-inspector-export-generated]'),
                    inspectorExportSlowpics: document.querySelector('[data-inspector-export-slowpics]'),
                    inspectorExportSummary: document.querySelector('[data-inspector-export-summary]'),
                };
            },

            bind() {
                const { dom } = viewer;
                dom.btnInspector.addEventListener('click', () => this.setOpen(!viewer.state.inspectorOpen));
                dom.btnInspectorClose.addEventListener('click', () => this.setOpen(false));
                dom.inspectorTabs.forEach(tab => {
                    tab.addEventListener('click', () => this.setTab(tab.dataset.inspectorTab));
                    tab.addEventListener('keydown', event => this.handleTabKey(event));
                });
                dom.btnInspectorResetCurrentAlign.addEventListener('click', () => viewer.resetCurrentPairAlignment());
                dom.btnInspectorResetAllAlign.addEventListener('click', () => viewer.resetAllPairAlignments());
                dom.inspector.addEventListener('keydown', event => {
                    if (event.key !== 'Escape') return;
                    event.preventDefault();
                    event.stopPropagation();
                    this.setOpen(false);
                });
            },

            validTab(tab) {
                return ['frame', 'clips', 'align', 'review', 'export'].includes(tab);
            },

            setOpen(open, options = {}) {
                const nextOpen = Boolean(open);
                const wasOpen = viewer.state.inspectorOpen;
                if (nextOpen && viewer.state.inspectorTab === 'review') viewer.ensureReviewController();
                if (nextOpen && !wasOpen && options.focus !== false) {
                    const activeElement = document.activeElement;
                    const canRestoreFocus = activeElement
                        && activeElement !== document.body
                        && activeElement !== document.documentElement
                        && activeElement.isConnected !== false
                        && activeElement.disabled !== true
                        && typeof activeElement.focus === 'function'
                        && activeElement.tabIndex >= 0;
                    viewer.state.inspectorRestoreFocus = canRestoreFocus ? activeElement : viewer.dom.btnInspector;
                }
                viewer.state.inspectorOpen = nextOpen;
                if (nextOpen) this.render();
                else this.updateVisibility();
                if (options.save !== false) viewer.persistViewportState();
                if (nextOpen && options.focus !== false) {
                    viewer.focusElement(Array.from(viewer.dom.inspectorTabs)
                        .find(tab => tab.dataset.inspectorTab === viewer.state.inspectorTab));
                } else if (!nextOpen && wasOpen) {
                    const restoreTarget = viewer.state.inspectorRestoreFocus?.isConnected
                        ? viewer.state.inspectorRestoreFocus
                        : viewer.dom.btnInspector;
                    viewer.state.inspectorRestoreFocus = null;
                    if (options.focus !== false && restoreTarget) viewer.focusElement(restoreTarget);
                }
            },

            isVisible() {
                return viewer.state.inspectorOpen;
            },

            focusableElements() {
                return Array.from(viewer.dom.inspector.querySelectorAll('button, [href], input, select, textarea, [tabindex]'));
            },

            setFocusable(enabled) {
                viewer.dom.inspector.inert = !enabled;
                this.focusableElements().forEach(element => {
                    if (enabled) {
                        if (Object.hasOwn(element.dataset, 'inspectorPreviousTabindex')) {
                            const previous = element.dataset.inspectorPreviousTabindex;
                            if (previous === '' || previous === '-1') element.removeAttribute('tabindex');
                            else element.setAttribute('tabindex', previous);
                            delete element.dataset.inspectorPreviousTabindex;
                        } else if (element.getAttribute('tabindex') === '-1') {
                            element.removeAttribute('tabindex');
                        }
                        return;
                    }
                    if (!Object.hasOwn(element.dataset, 'inspectorPreviousTabindex')) {
                        element.dataset.inspectorPreviousTabindex = element.getAttribute('tabindex') ?? '';
                    }
                    element.setAttribute('tabindex', '-1');
                });
            },

            updateVisibility() {
                const visible = this.isVisible();
                document.body?.classList?.toggle('rv-inspector-open', visible);
                viewer.dom.inspector.classList.toggle('open', visible);
                viewer.dom.inspector.setAttribute('aria-hidden', visible ? 'false' : 'true');
                viewer.dom.btnInspector.classList.toggle('active', visible);
                viewer.dom.btnInspector.setAttribute('aria-expanded', String(visible));
                if (this.focusableVisibility !== visible) {
                    this.setFocusable(visible);
                    this.focusableVisibility = visible;
                }
                this.updateTabs();
            },

            setTab(tab, options = {}) {
                viewer.state.inspectorTab = this.validTab(tab) ? tab : 'frame';
                if (viewer.state.inspectorTab === 'review' && viewer.state.inspectorOpen) {
                    viewer.ensureReviewController().render();
                }
                this.updateTabs();
                if (options.save !== false) viewer.persistViewportState();
            },

            handleTabKey(event) {
                const tabs = Array.from(viewer.dom.inspectorTabs);
                const currentIndex = tabs.indexOf(event.currentTarget);
                if (currentIndex === -1) return;
                let nextIndex = null;
                if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
                if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % tabs.length;
                if (event.key === 'Home') nextIndex = 0;
                if (event.key === 'End') nextIndex = tabs.length - 1;
                if (nextIndex === null) return;
                event.preventDefault();
                event.stopPropagation();
                const nextTab = tabs[nextIndex];
                this.setTab(nextTab.dataset.inspectorTab);
                viewer.focusElement(nextTab);
            },

            updateTabs() {
                viewer.dom.inspectorTabs.forEach(tab => {
                    const active = tab.dataset.inspectorTab === viewer.state.inspectorTab;
                    tab.classList.toggle('active', active);
                    tab.setAttribute('aria-selected', active ? 'true' : 'false');
                    tab.tabIndex = viewer.state.inspectorOpen && active ? 0 : -1;
                });
                viewer.dom.inspectorPanels.forEach(panel => {
                    const active = panel.id === `inspector-panel-${viewer.state.inspectorTab}`;
                    panel.hidden = !active;
                    panel.tabIndex = viewer.state.inspectorOpen && active ? 0 : -1;
                });
            },

            safeHttpUrl(url) {
                if (typeof url !== 'string' || url.length === 0) return null;
                try {
                    const parsed = new URL(url);
                    return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : null;
                } catch {
                    return null;
                }
            },

            renderSlowpics() {
                if (!viewer.dom.inspectorExportSlowpics) return;
                const slowpicsUrl = viewer.state.data.slowpics_url;
                const safeUrl = this.safeHttpUrl(slowpicsUrl);
                if (!safeUrl) {
                    viewer.dom.inspectorExportSlowpics.replaceChildren(document.createTextNode(slowpicsUrl || 'Not uploaded'));
                    return;
                }
                const link = document.createElement('a');
                link.href = safeUrl;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.className = 'rv-link';
                link.textContent = slowpicsUrl;
                viewer.dom.inspectorExportSlowpics.replaceChildren(link);
            },

            currentClipRole(index) {
                const roles = [];
                if (viewer.state.mode === 'grid' && viewer.gridView?.indexes().includes(index)) {
                    if (index === viewer.referenceClipIndex()) roles.push('Reference');
                    if (index === viewer.state.activeClipIdx) roles.push('Active');
                    roles.push('Visible');
                }
                if (index === viewer.state.leftClipIdx && !['overlay', 'grid'].includes(viewer.state.mode)) roles.push('Left');
                if (index === viewer.state.rightClipIdx && !['overlay', 'grid'].includes(viewer.state.mode)) roles.push('Right');
                if (index === viewer.state.activeClipIdx && (viewer.state.mode === 'overlay' || viewer.state.mode === 'blink')) {
                    roles.push(viewer.state.mode === 'overlay' ? 'Active' : 'Visible');
                }
                return roles.length > 0 ? roles.join(', ') : 'Available';
            },

            render() {
                if (!viewer.dom.inspector) return;
                this.updateVisibility();
                if (!viewer.state.inspectorOpen) return;
                viewer.updateRenderingSummary();
                const frame = viewer.currentFrame();
                viewer.setText(viewer.dom.inspectorFrameLabel, frame?.label || 'No frame selected');
                viewer.setText(viewer.dom.inspectorFrameNumber, frame?.number ?? '');
                viewer.setText(viewer.dom.inspectorFrameCategory, frame?.category ? viewer.humanizeCategory(frame.category) : '');
                viewer.setText(viewer.dom.inspectorFrameDetail, frame?.detail || '');
                viewer.setText(viewer.dom.inspectorFramePosition, viewer.visibleFramePositionText());

                if (viewer.dom.inspectorSourceFrames) {
                    const rows = viewer.visibleSourceIndexes().map(clipIndex => {
                        const clip = viewer.state.data.clips[clipIndex];
                        const image = frame?.images?.[clipIndex];
                        const item = document.createElement('li');
                        item.className = 'rv-inspector-source';
                        const sourceFrame = Number.isInteger(image?.source_frame) ? image.source_frame : 'Unknown';
                        const total = Number.isInteger(clip?.frame_count) ? ` / ${clip.frame_count}` : '';
                        const pictureType = image?.picture_type ? `${image.picture_type}-frame` : 'type unknown';
                        const dolbyVision = image?.dolby_vision_rpu === true ? ' · DV RPU' : '';
                        item.textContent = `${viewer.clipDisplay(clip)} — ${sourceFrame}${total} · ${pictureType}${dolbyVision}`;
                        return item;
                    });
                    viewer.dom.inspectorSourceFrames.replaceChildren(...rows);
                }

                if (viewer.dom.inspectorClips) {
                    viewer.dom.inspectorClips.replaceChildren(...viewer.state.data.clips.map((clip, index) => {
                        const item = document.createElement('li');
                        item.className = 'rv-inspector-clip';
                        item.dataset.clipIndex = String(index);
                        item.innerHTML = `
                            <div class="rv-inspector-clip-heading"><span></span><span></span></div>
                            <div class="rv-inspector-clip-primary"></div>
                            <div class="rv-inspector-clip-release" hidden></div>
                            <dl class="rv-inspector-list">
                                <div><dt>View role</dt><dd></dd></div><div><dt>File</dt><dd></dd></div>
                                <div><dt>Resolution</dt><dd></dd></div><div><dt>FPS</dt><dd></dd></div>
                                <div><dt>File size</dt><dd></dd></div><div><dt>Signal</dt><dd></dd></div>
                                <div><dt>Presentation</dt><dd></dd></div>
                            </dl>`;
                        const heading = item.querySelectorAll('.rv-inspector-clip-heading span');
                        heading[0].textContent = ViewerFormat.stableClipRole(index, viewer.referenceClipIndex());
                        heading[1].textContent = clip.signal?.is_hdr ? 'HDR' : 'SDR';
                        const primary = ViewerFormat.clipDisplay(clip, 'primary');
                        const release = ViewerFormat.clipDisplay(clip, 'release');
                        item.querySelector('.rv-inspector-clip-primary').textContent = primary;
                        const releaseElement = item.querySelector('.rv-inspector-clip-release');
                        const normalizedPrimary = viewer.normalizedDisplayToken(primary);
                        const normalizedRelease = viewer.normalizedDisplayToken(release);
                        const showRelease = Boolean(normalizedRelease && normalizedPrimary !== normalizedRelease
                            && !normalizedPrimary.endsWith(`| ${normalizedRelease}`));
                        releaseElement.hidden = !showRelease;
                        releaseElement.textContent = showRelease ? release : '';
                        const values = item.querySelectorAll('dd');
                        values[0].textContent = this.currentClipRole(index);
                        values[1].textContent = ViewerFormat.clipFilename(clip);
                        values[2].textContent = ViewerFormat.formatResolution(clip.resolution);
                        values[3].textContent = ViewerFormat.formatFps(clip.fps);
                        values[4].textContent = ViewerFormat.formatFileSize(clip.size_bytes);
                        values[5].textContent = ViewerFormat.formatSignal(clip.signal);
                        values[6].textContent = ViewerFormat.formatPresentation(clip);
                        const activePicture = ViewerFormat.formatActivePicture(clip.active_picture);
                        const clipList = item.querySelector('dl');
                        if (activePicture && clipList?.appendChild) {
                            const row = document.createElement('div');
                            row.innerHTML = '<dt>Active picture</dt><dd></dd>';
                            row.querySelector('dd').textContent = activePicture;
                            clipList.appendChild(row);
                        }
                        return item;
                    }));
                }

                viewer.setText(viewer.dom.inspectorAlignPair, `${viewer.currentPairLabel()} (${viewer.viewport.currentPairAlignmentKey()})`);
                viewer.setText(viewer.dom.inspectorAlignPreset, viewer.viewport.alignmentPresetLabel(viewer.state.alignmentPreset));
                viewer.setText(viewer.dom.inspectorAlignX, viewer.viewport.formatSignedPixels(viewer.state.alignX, 'x'));
                viewer.setText(viewer.dom.inspectorAlignY, viewer.viewport.formatSignedPixels(viewer.state.alignY, 'y'));
                viewer.setText(viewer.dom.inspectorExportTitle, viewer.state.data.title || '');
                viewer.setText(viewer.dom.inspectorExportId, viewer.state.data.report_id || '');
                viewer.setText(viewer.dom.inspectorExportGenerated, viewer.state.data.generated_at || '');
                this.renderSlowpics();
                viewer.setText(viewer.dom.inspectorExportSummary,
                    `${viewer.state.data.title || 'Report'} • ${viewer.state.data.stats.frame_count} frames • ${viewer.state.data.stats.clip_count} clips • ${ViewerFormat.modeLabel(viewer.state.mode)}`);
                viewer.reviewController?.render();
            },
        };
    },
};
