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
                    inspectorFrameIdentity: document.querySelector('[data-inspector-frame-identity]'),
                    inspectorFrameDetailRow: document.querySelector('[data-inspector-frame-detail-row]'),
                    inspectorFrameDetail: document.querySelector('[data-inspector-frame-detail]'),
                    inspectorFramePosition: document.querySelector('[data-inspector-frame-position]'),
                    inspectorSourceFrames: document.querySelector('[data-inspector-source-frames]'),
                    inspectorClipsShared: document.querySelector('[data-inspector-clips-shared]'),
                    inspectorClips: document.querySelector('[data-inspector-clips]'),
                    inspectorAlignPair: document.querySelector('[data-inspector-align-pair]'),
                    inspectorAlignPreset: document.querySelector('[data-inspector-align-preset]'),
                    inspectorAlignX: document.querySelector('[data-inspector-align-x]'),
                    inspectorAlignY: document.querySelector('[data-inspector-align-y]'),
                    btnInspectorResetCurrentAlign: document.getElementById('btn-inspector-reset-current-align'),
                    btnInspectorResetAllAlign: document.getElementById('btn-inspector-reset-all-align'),
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
                return ['frame', 'clips', 'align', 'review'].includes(tab);
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
                if (options.save !== false) viewer.persistViewerState();
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
                if (options.save !== false) viewer.persistViewerState();
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

            frameIdentityText(frame) {
                if (!frame) return 'No frame selected';
                const expected = `Frame ${frame.number}`;
                if (frame.label && frame.label !== expected) return frame.label;
                const category = frame.category ? viewer.humanizeCategory(frame.category) : '';
                return category ? `${frame.number} · ${category}` : `${frame.number}`;
            },

            framePositionText() {
                const visible = viewer.visibleFrameIndexes();
                const position = viewer.visibleFramePosition(visible);
                if (position < 0) return `Not shown in ${viewer.frameFilterName()}`;
                return `${position + 1} / ${visible.length} in ${viewer.frameFilterName()}`;
            },

            clipPlacement(index) {
                if (viewer.state.mode === 'overlay') {
                    return index === viewer.state.activeClipIdx ? 'shown' : 'not shown';
                }
                if (viewer.state.mode === 'grid') {
                    return (viewer.gridView?.indexes?.() || []).includes(index) ? 'shown' : 'not shown';
                }
                if (index === viewer.state.leftClipIdx) return 'shown left';
                if (index === viewer.state.rightClipIdx) return 'shown right';
                return 'not shown';
            },

            sourceVisibilityMark(index) {
                const placement = this.clipPlacement(index);
                if (placement === 'shown left') return 'Shown left';
                if (placement === 'shown right') return 'Shown right';
                if (placement === 'shown') return 'Shown';
                return '';
            },

            clipCardRows(clip, shared) {
                const rows = [
                    ['Picture', ViewerFormat.formatActivePicture(clip.active_picture, clip.resolution)],
                    ['Length', ViewerFormat.clipLengthText(clip)],
                    ['Size', ViewerFormat.formatFileSize(clip.size_bytes)],
                ];
                if (!shared.fps) rows.push(['FPS', ViewerFormat.clipFpsText(clip)]);
                if (!shared.presentation) rows.push(['Presentation', ViewerFormat.formatPresentation(clip)]);
                return rows;
            },

            render() {
                if (!viewer.dom.inspector) return;
                this.updateVisibility();
                if (!viewer.state.inspectorOpen) return;
                viewer.updateRenderingSummary();
                const frame = viewer.currentFrame();
                viewer.setText(viewer.dom.inspectorFrameIdentity, this.frameIdentityText(frame));
                viewer.setText(viewer.dom.inspectorFramePosition, this.framePositionText());
                const detail = frame?.detail || '';
                const showDetail = Boolean(detail) && detail !== 'Selected comparison frame';
                if (viewer.dom.inspectorFrameDetailRow) {
                    viewer.dom.inspectorFrameDetailRow.hidden = !showDetail;
                }
                if (showDetail) viewer.setText(viewer.dom.inspectorFrameDetail, detail);

                if (viewer.dom.inspectorSourceFrames) {
                    const rows = viewer.state.data.clips.map((clip, clipIndex) => {
                        const image = frame?.images?.[clipIndex];
                        const row = document.createElement('tr');
                        const mark = this.sourceVisibilityMark(clipIndex);
                        row.classList.toggle('is-visible', Boolean(mark));
                        const sourceCell = document.createElement('td');
                        const name = document.createElement('div');
                        name.className = 'rv-source-name';
                        name.textContent = ViewerFormat.clipDisplay(clip, 'micro');
                        if (mark) {
                            const shown = document.createElement('div');
                            shown.className = 'rv-source-shown';
                            shown.textContent = mark;
                            sourceCell.replaceChildren(name, shown);
                        } else {
                            sourceCell.replaceChildren(name);
                        }
                        const frameCell = document.createElement('td');
                        frameCell.className = 'rv-source-frame';
                        if (!Number.isInteger(image?.source_frame)) {
                            frameCell.textContent = 'Unknown';
                        } else if (Number.isInteger(clip?.frame_count)) {
                            frameCell.textContent = `${image.source_frame} / ${clip.frame_count}`;
                        } else {
                            frameCell.textContent = `${image.source_frame}`;
                        }
                        const typeCell = document.createElement('td');
                        if (image?.picture_type) {
                            typeCell.textContent = image.dolby_vision_rpu === true
                                ? `${image.picture_type} · DV RPU`
                                : image.picture_type;
                        } else {
                            typeCell.textContent = 'unknown';
                        }
                        row.replaceChildren(sourceCell, frameCell, typeCell);
                        return row;
                    });
                    viewer.dom.inspectorSourceFrames.replaceChildren(...rows);
                }

                const clips = viewer.state.data.clips;
                const shared = ViewerFormat.sharedClipValues(clips);
                if (viewer.dom.inspectorClipsShared) {
                    const parts = [shared.fps, shared.presentation].filter(Boolean);
                    viewer.dom.inspectorClipsShared.hidden = parts.length === 0;
                    viewer.setText(
                        viewer.dom.inspectorClipsShared,
                        parts.length > 0 ? `All sources: ${parts.join(' · ')}` : '',
                    );
                }

                if (viewer.dom.inspectorClips) {
                    viewer.dom.inspectorClips.replaceChildren(...clips.map((clip, index) => {
                        const item = document.createElement('li');
                        item.className = 'rv-inspector-clip';
                        item.dataset.clipIndex = String(index);
                        const heading = document.createElement('div');
                        heading.className = 'rv-inspector-clip-heading';
                        const title = document.createElement('span');
                        title.textContent = `${ViewerFormat.stableClipRole(index, viewer.referenceClipIndex())} · ${this.clipPlacement(index)}`;
                        const badge = document.createElement('span');
                        badge.className = 'rv-badge';
                        badge.textContent = ViewerFormat.clipBadge(clip.signal);
                        heading.replaceChildren(title, badge);
                        const name = document.createElement('div');
                        name.className = 'rv-inspector-clip-primary';
                        name.textContent = ViewerFormat.clipDisplay(clip, 'control');
                        const file = document.createElement('div');
                        file.className = 'rv-inspector-clip-file';
                        file.textContent = ViewerFormat.clipFilename(clip);
                        const list = document.createElement('dl');
                        list.className = 'rv-inspector-list';
                        const rowElements = [
                            ...this.clipCardRows(clip, shared),
                            ['Signal', ViewerFormat.formatSignal(clip.signal)],
                        ]
                            .filter(([, value]) => Boolean(value))
                            .map(([term, value]) => {
                                const row = document.createElement('div');
                                const dt = document.createElement('dt');
                                dt.textContent = term;
                                const dd = document.createElement('dd');
                                dd.textContent = value;
                                row.replaceChildren(dt, dd);
                                return row;
                            });
                        list.replaceChildren(...rowElements);
                        item.replaceChildren(heading, name, file, list);
                        return item;
                    }));
                }

                viewer.setText(viewer.dom.inspectorAlignPair, `${viewer.currentPairLabel()} (${viewer.viewport.currentPairAlignmentKey()})`);
                viewer.setText(viewer.dom.inspectorAlignPreset, viewer.viewport.alignmentPresetLabel(viewer.state.alignmentPreset));
                viewer.setText(viewer.dom.inspectorAlignX, viewer.viewport.formatSignedPixels(viewer.state.alignX, 'x'));
                viewer.setText(viewer.dom.inspectorAlignY, viewer.viewport.formatSignedPixels(viewer.state.alignY, 'y'));
                viewer.reviewController?.render();
            },
        };
    },
};
