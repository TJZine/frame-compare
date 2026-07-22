const GridView = (() => {
    const DESKTOP_PAGE_SIZE = 4;
    const MOBILE_QUERY = '(max-width: 767px)';

    function pageSize(isMobile) {
        return isMobile ? 1 : DESKTOP_PAGE_SIZE;
    }

    function normalizedStart(start, clipCount, isMobile) {
        if (clipCount <= 0) return 0;
        const bounded = Math.max(0, Math.min(clipCount - 1, Number.isInteger(start) ? start : 0));
        const size = pageSize(isMobile);
        return Math.floor(bounded / size) * size;
    }

    function visibleIndexes(start, clipCount, isMobile) {
        const first = normalizedStart(start, clipCount, isMobile);
        const end = Math.min(clipCount, first + pageSize(isMobile));
        return Array.from({ length: Math.max(0, end - first) }, (_, offset) => first + offset);
    }

    function positionText(start, clipCount, isMobile) {
        if (clipCount <= 0) return '';
        const indexes = visibleIndexes(start, clipCount, isMobile);
        if (isMobile) return `Clip ${indexes[0] + 1} of ${clipCount}`;
        return `Clips ${indexes[0] + 1}\u2013${indexes[indexes.length - 1] + 1} of ${clipCount}`;
    }

    function layoutName(clipCount, viewportWidth, visibleCount = clipCount) {
        if (viewportWidth < 768) return 'mobile';
        if (clipCount === 2) return 'two';
        if (clipCount === 3 && viewportWidth >= 1200) return 'three-wide';
        if (clipCount === 3) return 'three-wrap';
        if (visibleCount >= 4 || clipCount > 4) return 'four';
        return 'single';
    }

    function create(viewer) {
        const dom = {
            grid: document.getElementById('rv-grid'),
            cells: document.querySelector('[data-grid-cells]'),
            frameError: document.querySelector('[data-grid-frame-error]'),
            controls: document.querySelector('[data-control-scope="grid"]'),
            previous: document.getElementById('btn-grid-prev'),
            next: document.getElementById('btn-grid-next'),
            position: document.querySelector('[data-grid-position]'),
        };
        const state = {
            initialized: false,
            active: false,
            start: 0,
            mobile: false,
            mediaQuery: null,
            resizeObserver: null,
            failed: new Set(),
            renderGeneration: 0,
        };

        function clipCount() {
            return viewer.state.data?.clips?.length || 0;
        }

        function currentFrame() {
            return viewer.currentFrame();
        }

        function isMobile() {
            const width = dom.grid?.getBoundingClientRect?.().width || 0;
            return Boolean(state.mediaQuery?.matches || (width > 0 && width < 768));
        }

        function indexes() {
            return visibleIndexes(state.start, clipCount(), state.mobile);
        }

        function announce(message) {
            viewer.announce?.(message);
        }

        function updateControls(options = {}) {
            if (!dom.controls) return;
            const count = clipCount();
            const first = indexes()[0] ?? 0;
            const size = pageSize(state.mobile);
            const needsPaging = state.mobile ? count > 1 : count > DESKTOP_PAGE_SIZE;
            dom.controls.hidden = !state.active || !needsPaging;
            dom.previous.disabled = first <= 0;
            dom.next.disabled = first + size >= count;
            const text = positionText(state.start, count, state.mobile);
            dom.position.textContent = text;
            dom.position.setAttribute('aria-label', text);
            if (options.announce && text) announce(`${text} visible.`);
        }

        function updateLayout() {
            if (!dom.grid) return;
            const width = dom.grid.getBoundingClientRect?.().width
                || Number(window.innerWidth)
                || viewer.dom.stage?.clientWidth
                || 0;
            dom.grid.dataset.layout = layoutName(clipCount(), width, indexes().length);
            dom.grid.dataset.visibleCount = String(indexes().length);
        }

        function sourceFor(index) {
            return currentFrame()?.images?.[index]?.src || '';
        }

        function safeLabel(index) {
            return viewer.state.data?.clips?.[index]?.label || `Clip ${index + 1}`;
        }

        function clipRoles(index) {
            const roles = [];
            if (index === viewer.referenceClipIndex()) roles.push('Reference');
            if (index === viewer.state.activeClipIdx) roles.push('Active');
            return roles;
        }

        function updateCellRoles() {
            if (!dom.cells) return;
            dom.cells.querySelectorAll('.rv-grid-cell').forEach(cell => {
                const index = Number(cell.dataset.clipIndex);
                const label = safeLabel(index);
                const roles = clipRoles(index);
                cell.dataset.reference = roles.includes('Reference') ? 'true' : 'false';
                cell.dataset.active = roles.includes('Active') ? 'true' : 'false';
                cell.setAttribute(
                    'aria-label',
                    [`Clip ${index + 1}, ${label}`, ...roles].join(', '),
                );
                const role = cell.querySelector('[data-grid-role]');
                if (role) {
                    role.textContent = roles.join(' · ');
                    role.hidden = roles.length === 0;
                }
            });
        }

        function setCellStatus(cell, status) {
            cell.dataset.status = status;
            const loading = cell.querySelector('[data-grid-loading]');
            if (loading) loading.hidden = status !== 'loading';
            const error = cell.querySelector('[data-grid-error]');
            if (error) error.hidden = status !== 'error';
        }

        function sizeImage(image) {
            const media = image.closest?.('.rv-grid-media');
            const width = Number(image.naturalWidth);
            const height = Number(image.naturalHeight);
            if (!media || width <= 0 || height <= 0) return;
            const mediaRect = media.getBoundingClientRect?.();
            if (!mediaRect || mediaRect.width <= 0 || mediaRect.height <= 0) return;
            const scale = Math.min(mediaRect.width / width, mediaRect.height / height);
            image.style.width = `${width * scale}px`;
            image.style.height = `${height * scale}px`;
        }

        function entryMetrics(entry) {
            const media = entry?.image?.closest?.('.rv-grid-media');
            const mediaRect = media?.getBoundingClientRect?.();
            const sourceWidth = Number(entry?.image?.naturalWidth) || Number(entry?.width);
            const sourceHeight = Number(entry?.image?.naturalHeight) || Number(entry?.height);
            if (
                !mediaRect
                || mediaRect.width <= 0
                || mediaRect.height <= 0
                || sourceWidth <= 0
                || sourceHeight <= 0
            ) return null;
            const scale = Math.min(mediaRect.width / sourceWidth, mediaRect.height / sourceHeight);
            return {
                entry,
                mediaRect,
                width: sourceWidth * scale,
                height: sourceHeight * scale,
            };
        }

        function metricsForPoint(clientX, clientY) {
            const metrics = entries().map(entryMetrics).filter(Boolean);
            return metrics.find(item => (
                clientX >= item.mediaRect.left
                && clientX <= item.mediaRect.left + item.mediaRect.width
                && clientY >= item.mediaRect.top
                && clientY <= item.mediaRect.top + item.mediaRect.height
            )) || metrics[0] || null;
        }

        function sizeImages() {
            entries().forEach(entry => sizeImage(entry.image));
            viewer.clampPan?.();
            viewer.lens?.refresh?.();
        }

        function updateFrameError() {
            if (!dom.frameError) return;
            const visible = indexes();
            const allFailed = visible.length > 0 && visible.every(index => state.failed.has(index));
            dom.frameError.hidden = !allFailed;
            dom.frameError.textContent = allFailed
                ? 'Images for this frame are unavailable. Navigation and retry remain available.'
                : '';
        }

        function isCurrentGeneration(generation) {
            return state.active && generation === state.renderGeneration;
        }

        function handleLoad(cell, image, index, generation) {
            if (!isCurrentGeneration(generation)) return;
            state.failed.delete(index);
            setCellStatus(cell, 'ready');
            image.hidden = false;
            sizeImage(image);
            updateFrameError();
            viewer.lens?.sync?.();
        }

        function handleError(cell, image, index, src, generation) {
            if (!isCurrentGeneration(generation)) return;
            state.failed.add(index);
            setCellStatus(cell, 'error');
            image.hidden = true;
            const error = cell.querySelector('[data-grid-error]');
            if (error) error.hidden = false;
            updateFrameError();
            const label = safeLabel(index);
            announce(`${label} image unavailable.`);
            if (!src.startsWith('data:')) return;
            cell.querySelector('[data-grid-retry]')?.remove();
        }

        function retry(cell, image, index, src, generation) {
            if (!isCurrentGeneration(generation)) return;
            state.failed.delete(index);
            const error = cell.querySelector('[data-grid-error]');
            if (error) error.hidden = true;
            image.hidden = false;
            setCellStatus(cell, 'loading');
            image.removeAttribute('src');
            cell.focus({ preventScroll: true });
            window.requestAnimationFrame(() => {
                if (!isCurrentGeneration(generation)) return;
                image.src = src;
            });
        }

        function buildCell(index, generation) {
            const label = safeLabel(index);
            const src = sourceFor(index);
            const cell = document.createElement('figure');
            cell.className = 'rv-grid-cell';
            cell.dataset.clipIndex = String(index);
            cell.dataset.status = 'loading';
            cell.tabIndex = 0;
            cell.title = label;

            const media = document.createElement('div');
            media.className = 'rv-grid-media';
            const image = document.createElement('img');
            image.className = 'rv-grid-image';
            image.alt = `${label} - Frame ${currentFrame()?.number ?? viewer.state.currentFrameIdx + 1}`;
            image.decoding = 'async';
            image.dataset.clipIndex = String(index);
            image.addEventListener('load', () => handleLoad(cell, image, index, generation));
            image.addEventListener('error', () => handleError(cell, image, index, src, generation));

            const loading = document.createElement('span');
            loading.className = 'rv-grid-loading';
            loading.dataset.gridLoading = '';
            loading.textContent = 'Loading image\u2026';

            const error = document.createElement('div');
            error.className = 'rv-grid-error';
            error.dataset.gridError = '';
            error.hidden = true;
            const errorText = document.createElement('span');
            errorText.textContent = `${label} image unavailable`;
            error.append(errorText);
            if (src && !src.startsWith('data:')) {
                const retryButton = document.createElement('button');
                retryButton.type = 'button';
                retryButton.dataset.gridRetry = '';
                retryButton.textContent = 'Retry';
                retryButton.setAttribute('aria-label', `Retry ${label} image`);
                retryButton.addEventListener('pointerdown', event => event.stopPropagation());
                retryButton.addEventListener('click', event => {
                    event.stopPropagation();
                    retry(cell, image, index, src, generation);
                });
                error.append(retryButton);
            }

            media.append(image, loading, error);
            const caption = document.createElement('figcaption');
            caption.className = 'rv-grid-label';
            caption.title = label;
            const captionLabel = document.createElement('span');
            captionLabel.className = 'rv-grid-label-text';
            captionLabel.textContent = label;
            const role = document.createElement('span');
            role.className = 'rv-grid-role';
            role.dataset.gridRole = '';
            caption.append(captionLabel, role);
            cell.append(media, caption);
            cell.addEventListener('focus', () => {
                viewer.state.activeClipIdx = index;
                updateCellRoles();
                viewer.updateInspectorData?.();
                viewer.lens?.sync?.();
            });

            if (src) image.src = src;
            else handleError(cell, image, index, src, generation);
            return cell;
        }

        function render(options = {}) {
            if (!state.active || !dom.cells) return;
            const focusedClipIdx = clipIndexFromTarget(document.activeElement);
            state.start = normalizedStart(state.start, clipCount(), state.mobile);
            state.failed.clear();
            state.renderGeneration += 1;
            const generation = state.renderGeneration;
            dom.cells.replaceChildren(...indexes().map(index => buildCell(index, generation)));
            updateCellRoles();
            updateLayout();
            updateControls(options);
            updateFrameError();
            syncViewport();
            viewer.updateCurrentFrameMetadata(currentFrame());
            viewer.lens?.sync?.();
            if (Number.isInteger(focusedClipIdx) && indexes().includes(focusedClipIdx)) {
                Array.from(dom.cells.querySelectorAll('.rv-grid-cell'))
                    .find(cell => Number(cell.dataset.clipIndex) === focusedClipIdx)
                    ?.focus({ preventScroll: true });
            }
        }

        function clear() {
            state.renderGeneration += 1;
            state.failed.clear();
            dom.cells?.replaceChildren();
            if (dom.frameError) dom.frameError.hidden = true;
        }

        function setActive(active) {
            state.active = Boolean(active);
            if (dom.grid) dom.grid.hidden = !state.active;
            if (!state.active) {
                clear();
                updateControls();
                return;
            }
            initialize();
            updateControls();
        }

        function move(direction) {
            if (!state.active) return;
            const size = pageSize(state.mobile);
            const next = normalizedStart(state.start + direction * size, clipCount(), state.mobile);
            if (next === state.start) return;
            state.start = next;
            render({ announce: true });
        }

        function handleReflow() {
            if (!state.initialized) return;
            const nextMobile = isMobile();
            if (nextMobile === state.mobile) {
                if (state.active) {
                    updateLayout();
                    window.requestAnimationFrame(sizeImages);
                }
                return;
            }
            const focusedClipIdx = clipIndexFromTarget(document.activeElement);
            const firstVisible = Number.isInteger(focusedClipIdx)
                ? focusedClipIdx
                : indexes()[0] ?? 0;
            state.mobile = nextMobile;
            state.start = normalizedStart(firstVisible, clipCount(), state.mobile);
            if (state.active) render({ announce: true });
        }

        function initialize() {
            if (state.initialized) return;
            state.initialized = true;
            state.mediaQuery = window.matchMedia?.(MOBILE_QUERY) || { matches: false };
            state.mobile = isMobile();
            state.mediaQuery.addEventListener?.('change', handleReflow);
            window.addEventListener('resize', handleReflow);
            if (typeof ResizeObserver === 'function') {
                state.resizeObserver = new ResizeObserver(handleReflow);
                state.resizeObserver.observe(dom.grid);
            }
        }

        function bind() {
            dom.previous?.addEventListener('click', () => move(-1));
            dom.next?.addEventListener('click', () => move(1));
        }

        function entries() {
            if (!state.active || !dom.cells) return [];
            return Array.from(dom.cells.querySelectorAll('.rv-grid-image')).map(image => {
                const clipIdx = Number(image.dataset.clipIndex);
                const clip = viewer.state.data?.clips?.[clipIdx];
                return {
                    clipIdx,
                    image,
                    unavailable: state.failed.has(clipIdx),
                    width: Number(clip?.resolution?.[0]),
                    height: Number(clip?.resolution?.[1]),
                };
            });
        }

        function clipIndexFromTarget(target) {
            if (!state.active) return null;
            const cell = target?.closest?.('[data-clip-index]');
            if (!cell || !dom.cells?.contains(cell)) return null;
            const index = Number(cell.dataset.clipIndex);
            return Number.isInteger(index) ? index : null;
        }

        function syncViewport() {
            if (!dom.grid) return;
            dom.grid.style.setProperty('--grid-zoom-level', viewer.state.zoom);
            entries().forEach(entry => {
                const metrics = entryMetrics(entry);
                if (!metrics) return;
                entry.image.style.setProperty(
                    '--grid-pan-x',
                    `${viewer.state.panX * metrics.width}px`,
                );
                entry.image.style.setProperty(
                    '--grid-pan-y',
                    `${viewer.state.panY * metrics.height}px`,
                );
            });
            dom.grid.classList.toggle('rv-grid--pixelated', viewer.state.zoom > 1);
        }

        function panBounds() {
            const metrics = entries().map(entryMetrics).filter(Boolean);
            if (metrics.length === 0) return { x: 0, y: 0 };
            return metrics.reduce((bounds, item) => ({
                x: Math.min(
                    bounds.x,
                    Math.max(0, (item.width * viewer.state.zoom - item.mediaRect.width) / (2 * item.width)),
                ),
                y: Math.min(
                    bounds.y,
                    Math.max(0, (item.height * viewer.state.zoom - item.mediaRect.height) / (2 * item.height)),
                ),
            }), { x: Number.POSITIVE_INFINITY, y: Number.POSITIVE_INFINITY });
        }

        function panBasisForPoint(clientX, clientY) {
            const metrics = metricsForPoint(clientX, clientY);
            return metrics ? { width: metrics.width, height: metrics.height } : null;
        }

        function zoomAnchorForPoint(clientX, clientY) {
            const metrics = metricsForPoint(clientX, clientY);
            if (!metrics) return null;
            const centerX = metrics.mediaRect.left + metrics.mediaRect.width / 2;
            const centerY = metrics.mediaRect.top + metrics.mediaRect.height / 2;
            return {
                centerX,
                centerY,
                width: metrics.width,
                height: metrics.height,
                contentX: (
                    clientX - centerX - viewer.state.panX * metrics.width
                ) / (metrics.width * viewer.state.zoom),
                contentY: (
                    clientY - centerY - viewer.state.panY * metrics.height
                ) / (metrics.height * viewer.state.zoom),
            };
        }

        function panForZoomAnchor(anchor, clientX, clientY, zoom) {
            if (!anchor || anchor.width <= 0 || anchor.height <= 0) return null;
            return {
                x: (clientX - anchor.centerX) / anchor.width - anchor.contentX * zoom,
                y: (clientY - anchor.centerY) / anchor.height - anchor.contentY * zoom,
            };
        }

        return {
            bind,
            clear,
            clipIndexFromTarget,
            entries,
            indexes,
            isActive: () => state.active,
            panBounds,
            panBasisForPoint,
            panForZoomAnchor,
            render,
            setActive,
            state,
            syncViewport,
            zoomAnchorForPoint,
        };
    }

    return {
        DESKTOP_PAGE_SIZE,
        create,
        layoutName,
        normalizedStart,
        pageSize,
        positionText,
        visibleIndexes,
    };
})();
