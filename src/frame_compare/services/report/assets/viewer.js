const ReportViewer = {
    state: {
        data: null,
        currentFrameIdx: 0,
        leftClipIdx: 0,
        rightClipIdx: 1,
        activeClipIdx: 0, // For overlay/blink
        mode: 'slider',
        zoom: 1.0,
        fitMode: 'actual',
        revealPercent: 50,
        blinkInterval: null,
        blinkPaused: false
    },

    init() {
        try {
            const scriptTag = document.getElementById('report-data');
            this.state.data = JSON.parse(scriptTag.textContent);
            this.state.mode = this.state.data.default_mode || 'slider';

            this.cacheDOM();
            this.bindEvents();
            this.setMode(this.state.mode); // Apply default mode UI state
            this.render();
            this.preloadImages();
        } catch (e) {
            console.error("Failed to initialize viewer:", e);
            alert("Failed to load report data.");
        }
    },

    cacheDOM() {
        this.dom = {
            stage: document.querySelector('.rv-viewer-stage'),
            canvas: document.querySelector('.rv-canvas'),
            sizerImg: document.querySelector('.rv-sizer'),
            leftLayer: document.querySelector('.rv-left'),
            rightLayer: document.querySelector('.rv-right'),
            divider: document.querySelector('.rv-divider'),
            leftImg: document.querySelector('.rv-left img'),
            rightImg: document.querySelector('.rv-right img'),
            frameSelect: document.getElementById('frame-select'),
            btnPrev: document.getElementById('btn-prev'),
            btnNext: document.getElementById('btn-next'),
            modeBtns: document.querySelectorAll('[data-mode]'),
            leftSelect: document.getElementById('left-select'),
            rightSelect: document.getElementById('right-select'),
            zoomRange: document.getElementById('zoom-range'),
            zoomVal: document.getElementById('zoom-val'),
            fitBtns: document.querySelectorAll('[data-fit]'),
            btnFullscreen: document.getElementById('btn-fullscreen'),
            filmstrip: document.querySelector('.rv-filmstrip'),
            labelLeft: document.getElementById('label-left'),
            labelRight: document.getElementById('label-right'),
            modal: document.getElementById('help-modal'),
            btnHelp: document.getElementById('btn-help'),
            btnCloseHelp: document.getElementById('btn-close-help'),
        };
    },

    bindEvents() {
        // Mode switching
        this.dom.modeBtns.forEach(btn => {
            btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
        });

        // Frame Navigation
        this.dom.btnPrev.addEventListener('click', () => this.prevFrame());
        this.dom.btnNext.addEventListener('click', () => this.nextFrame());
        this.dom.frameSelect.addEventListener('change', (e) => this.setFrame(parseInt(e.target.value)));

        // Clip Selection
        this.dom.leftSelect.addEventListener('change', (e) => {
            this.state.leftClipIdx = parseInt(e.target.value);
            this.state.activeClipIdx = this.state.leftClipIdx; // For overlay sync
            this.render();
        });
        this.dom.rightSelect.addEventListener('change', (e) => {
            this.state.rightClipIdx = parseInt(e.target.value);
            this.render();
        });

        // Zoom
        this.dom.zoomRange.addEventListener('input', (e) => this.setZoom(parseFloat(e.target.value)));
        document.getElementById('btn-zoom-out').addEventListener('click', () => this.setZoom(this.state.zoom - 0.1));
        document.getElementById('btn-zoom-in').addEventListener('click', () => this.setZoom(this.state.zoom + 0.1));
        document.getElementById('btn-zoom-reset').addEventListener('click', () => this.setZoom(1.0));

        // Fit and fullscreen controls
        this.dom.fitBtns.forEach(btn => {
            btn.addEventListener('click', () => this.setFitMode(btn.dataset.fit));
        });
        this.dom.sizerImg.addEventListener('load', () => this.applyFitMode());
        window.addEventListener('resize', () => this.applyFitMode());
        document.addEventListener('fullscreenchange', () => this.applyFitMode());
        this.dom.btnFullscreen.addEventListener('click', () => this.toggleFullscreen());

        // Help Modal
        const openModal = () => {
            this.dom.modal.classList.add('open');
            this.dom.modal.setAttribute('aria-hidden', 'false');
            this.dom.btnCloseHelp.focus();
        };
        const closeModal = () => {
            this.dom.modal.classList.remove('open');
            this.dom.modal.setAttribute('aria-hidden', 'true');
            this.dom.btnHelp.focus();
        };

        this.dom.btnHelp.addEventListener('click', openModal);
        this.dom.btnCloseHelp.addEventListener('click', closeModal);
        this.dom.modal.addEventListener('click', (e) => {
            if (e.target === this.dom.modal) closeModal();
        });

        // Focus Trap
        this.dom.modal.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                // Simple trap since only one button is interactive in MVP modal
                e.preventDefault();
                this.dom.btnCloseHelp.focus();
            }
            if (e.key === 'Escape') {
                closeModal();
            }
        });

        // Pointer interactions
        let isDragging = false;
        let activePointerId = null;
        const captureStagePointer = (e) => {
            activePointerId = e.pointerId;
            this.dom.stage.setPointerCapture?.(e.pointerId);
        };
        const updateSliderFromPointer = (e) => {
            const rect = this.dom.stage.getBoundingClientRect();
            if (rect.width <= 0) return;
            const x = e.clientX - rect.left;
            let percent = (1 - (x / rect.width)) * 100;
            percent = Math.max(0, Math.min(100, percent));

            this.state.revealPercent = percent;
            this.updateSlider();
        };
        const stopPointerInteraction = (e) => {
            if (activePointerId !== null && e.pointerId !== activePointerId) return;
            if (this.dom.stage.hasPointerCapture?.(e.pointerId)) {
                this.dom.stage.releasePointerCapture(e.pointerId);
            }
            isDragging = false;
            activePointerId = null;
            if (this.state.mode === 'blink') this.state.blinkPaused = false;
        };

        this.dom.stage.addEventListener('pointerdown', (e) => {
            if (this.state.mode === 'slider') {
                isDragging = true;
                captureStagePointer(e);
                updateSliderFromPointer(e);
                e.preventDefault();
            } else if (this.state.mode === 'overlay' || this.state.mode === 'diff') {
                 // Click to swap/cycle in overlay/diff
                 this.cycleClip();
            } else if (this.state.mode === 'blink') {
                 // Pause blink on hold
                 captureStagePointer(e);
                 this.state.blinkPaused = true;
            }
        });

        this.dom.stage.addEventListener('pointermove', (e) => {
            if (!isDragging || e.pointerId !== activePointerId) return;
            updateSliderFromPointer(e);
            e.preventDefault();
        });
        this.dom.stage.addEventListener('pointerup', stopPointerInteraction);
        this.dom.stage.addEventListener('pointercancel', stopPointerInteraction);

        // Filmstrip
        this.dom.filmstrip.addEventListener('click', (e) => {
            const item = e.target.closest('.rv-filmstrip-item');
            if (item) this.setFrame(parseInt(item.dataset.idx));
        });

        // Keyboard
        document.addEventListener('keydown', (e) => this.handleKey(e));
    },

    handleKey(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

        // Modal handling via global keydown if not caught by focus trap
        if (this.dom.modal.classList.contains('open')) return;

        if (e.key === '?' || (e.key === '/' && e.shiftKey)) {
            this.dom.btnHelp.click();
            return;
        }
        switch(e.key) {
            case 'ArrowLeft': this.prevFrame(); break;
            case 'ArrowRight': this.nextFrame(); break;
            case 'Home': this.setFrame(0); break;
            case 'End': this.setFrame(this.state.data.frames.length - 1); break;

            case 'ArrowUp': this.cycleClip(1); break;
            case 'ArrowDown': this.cycleClip(-1); break;

            case 's': case 'S': this.setMode('slider'); break;
            case 'o': case 'O': this.setMode('overlay'); break;
            case 'd': case 'D': this.setMode('diff'); break;
            case 'b': case 'B': this.setMode('blink'); break;

            case '=': case '+': this.setZoom(this.state.zoom + 0.1); break;
            case '-': this.setZoom(this.state.zoom - 0.1); break;
            case 'r': case 'R': this.setZoom(1.0); break;

            default:
                if (e.key >= '1' && e.key <= '9') {
                    const idx = parseInt(e.key) - 1;
                    if (idx < this.state.data.clips.length) {
                         if (this.state.mode === 'slider') this.state.leftClipIdx = idx;
                         else if (this.state.mode === 'diff') this.state.rightClipIdx = idx;
                         else this.state.activeClipIdx = idx;
                         this.render();
                    }
                }
        }
    },

    setMode(mode) {
        this.state.mode = mode;

        // Stop blink if leaving blink mode
        if (this.state.blinkInterval && mode !== 'blink') {
            clearInterval(this.state.blinkInterval);
            this.state.blinkInterval = null;
        }
        // Start blink if entering
        if (mode === 'blink' && !this.state.blinkInterval) {
            this.startBlink();
        }

        this.dom.modeBtns.forEach(btn => {
            const isActive = btn.dataset.mode === mode;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-checked', isActive);
        });

        this.dom.stage.className = `rv-viewer-stage rv-mode-${mode}`;
        this.render();
    },

    startBlink() {
        this.state.blinkInterval = setInterval(() => {
            if (this.state.blinkPaused) return;

            // Toggle between left and right clip indices for blink
            // Usually blink compares two, but can cycle. Spec says:
            // "activeClipIndex: number", "cycle through clips"
            // Let's cycle activeClip between left and right selected for MVP simplicity
            // or cycle through all? Spec 4.4 says "activeIndex = (activeIndex + 1) % clipCount"

            this.state.activeClipIdx = (this.state.activeClipIdx + 1) % this.state.data.clips.length;
            this.updateImages();

        }, 700);
    },

    setFrame(idx) {
        if (idx < 0 || idx >= this.state.data.frames.length) return;
        this.state.currentFrameIdx = idx;
        this.render();

        // Scroll filmstrip
        const item = this.dom.filmstrip.children[idx];
        if (item) item.scrollIntoView({ behavior: 'smooth', inline: 'center' });
    },

    nextFrame() { this.setFrame(this.state.currentFrameIdx + 1); },
    prevFrame() { this.setFrame(this.state.currentFrameIdx - 1); },

    cycleClip(direction = 1) {
        const count = this.state.data.clips.length;
        if (this.state.mode === 'slider') {
            // Cycle left clip
            this.state.leftClipIdx = (this.state.leftClipIdx + direction + count) % count;
            this.dom.leftSelect.value = this.state.leftClipIdx;
        } else if (this.state.mode === 'diff') {
            // Cycle right (compare) clip
            this.state.rightClipIdx = (this.state.rightClipIdx + direction + count) % count;
            this.dom.rightSelect.value = this.state.rightClipIdx;
        } else {
            this.state.activeClipIdx = (this.state.activeClipIdx + direction + count) % count;
        }
        this.render();
    },

    setZoom(level) {
        this.state.fitMode = 'custom';
        this.updateFitButtons();
        this.applyZoom(level);
    },

    applyZoom(level) {
        this.state.zoom = Math.max(0.25, Math.min(2.0, level));
        this.dom.zoomRange.value = this.state.zoom;
        this.dom.zoomRange.setAttribute('aria-valuenow', this.state.zoom);
        this.dom.zoomVal.textContent = Math.round(this.state.zoom * 100) + '%';
        this.dom.canvas.style.setProperty('--zoom-level', this.state.zoom);
    },

    setFitMode(mode, options = {}) {
        if (!['actual', 'width', 'height'].includes(mode)) return;

        this.state.fitMode = mode;
        this.updateFitButtons();

        if (options.updateZoom === false) return;
        this.applyFitMode();
    },

    updateFitButtons() {
        this.dom.fitBtns.forEach(btn => {
            const isActive = btn.dataset.fit === this.state.fitMode;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-checked', isActive);
        });
    },

    baseCanvasSize() {
        const rect = this.dom.sizerImg.getBoundingClientRect();
        const zoom = this.state.zoom || 1.0;
        return {
            width: rect.width / zoom,
            height: rect.height / zoom
        };
    },

    applyFitMode() {
        if (this.state.fitMode === 'custom') {
            return;
        }

        if (this.state.fitMode === 'actual') {
            this.applyZoom(1.0);
            return;
        }

        const stageRect = this.dom.stage.getBoundingClientRect();
        const base = this.baseCanvasSize();
        if (stageRect.width <= 0 || stageRect.height <= 0 || base.width <= 0 || base.height <= 0) {
            return;
        }

        const nextZoom = this.state.fitMode === 'width'
            ? stageRect.width / base.width
            : stageRect.height / base.height;
        this.applyZoom(nextZoom);
    },

    toggleFullscreen() {
        if (document.fullscreenElement) {
            document.exitFullscreen?.();
            return;
        }
        this.dom.stage.requestFullscreen?.();
    },

    updateSlider() {
        this.dom.leftLayer.style.setProperty('--reveal-percent', this.state.revealPercent + '%');
        this.dom.divider.style.setProperty('--reveal-percent', this.state.revealPercent + '%');
    },

    updateImages() {
        const frameData = this.state.data.frames[this.state.currentFrameIdx];
        if (!frameData) return;

        let leftSrc, rightSrc;
        let leftLabelTxt, rightLabelTxt;

        if (this.state.mode === 'slider' || this.state.mode === 'diff') {
            leftSrc = frameData.images[this.state.leftClipIdx].src;
            rightSrc = frameData.images[this.state.rightClipIdx].src;

            const leftClip = this.state.data.clips[this.state.leftClipIdx];
            const rightClip = this.state.data.clips[this.state.rightClipIdx];
            leftLabelTxt = `${leftClip.label} (Left)`;
            rightLabelTxt = `${rightClip.label} (Right)`;

            // For Diff mode, right layer is the "compare" one which gets difference blend
            // Left layer is base.

        } else {
            // Overlay or Blink - show activeClip
            // We use left layer as the main visible one for these modes
            leftSrc = frameData.images[this.state.activeClipIdx].src;
            // Right unused/hidden
            rightSrc = frameData.images[(this.state.activeClipIdx + 1) % this.state.data.clips.length].src; // Preload next?

            const activeClip = this.state.data.clips[this.state.activeClipIdx];
            leftLabelTxt = activeClip.label;
            rightLabelTxt = "";
        }

        if (this.dom.leftImg.getAttribute('src') !== leftSrc) {
            if (this.dom.sizerImg && this.dom.sizerImg.getAttribute('src') !== leftSrc) {
                this.dom.sizerImg.src = leftSrc;
            }
            this.dom.leftImg.src = leftSrc;
            // Alt text update
            const clipName = (this.state.mode === 'overlay' || this.state.mode === 'blink')
                ? this.state.data.clips[this.state.activeClipIdx].label
                : this.state.data.clips[this.state.leftClipIdx].label;
            this.dom.leftImg.alt = `${clipName} - Frame ${frameData.number}`;
        }
        if (this.dom.rightImg.getAttribute('src') !== rightSrc) {
            this.dom.rightImg.src = rightSrc;
            // Alt text update for right image (only relevant in split modes)
            const clipName = this.state.data.clips[this.state.rightClipIdx].label;
            this.dom.rightImg.alt = `${clipName} - Frame ${frameData.number}`;
        }

        this.dom.labelLeft.textContent = leftLabelTxt;
        this.dom.labelRight.textContent = rightLabelTxt;

        // Toggle visibility classes based on mode logic in CSS
        if (this.state.mode === 'overlay' || this.state.mode === 'blink') {
             this.dom.leftLayer.classList.add('active');
             this.dom.rightLayer.classList.remove('active');
        }
    },
    render() {
        // Update controls
        this.dom.frameSelect.value = this.state.currentFrameIdx;
        this.dom.btnPrev.disabled = this.state.currentFrameIdx === 0;
        this.dom.btnNext.disabled = this.state.currentFrameIdx === this.state.data.frames.length - 1;

        this.dom.leftSelect.value = this.state.leftClipIdx;
        this.dom.rightSelect.value = this.state.rightClipIdx;

        // Update images and labels
        this.updateImages();
        this.updateSlider();
        this.applyFitMode();

        // Update filmstrip active state
        Array.from(this.dom.filmstrip.children).forEach((el, idx) => {
            el.classList.toggle('active', idx === this.state.currentFrameIdx);
            el.setAttribute('aria-current', idx === this.state.currentFrameIdx);
        });
    },

    preloadImages() {
         // Basic preload of next few frames
         // Implementation omitted for MVP brevity, browser handles lazy loading
    }
};

document.addEventListener('DOMContentLoaded', () => ReportViewer.init());
