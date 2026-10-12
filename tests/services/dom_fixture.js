'use strict';

// Only the DOM mechanics shared by the viewer, lens, and grid fixtures live here.
// Geometry, selectors, image completion, and pointer capture remain scenario-owned.
function domMechanics(documentFor = () => null) {
    const listeners = new Map();
    return {
        parentElement: null,
        children: [],
        addEventListener(type, callback, options = {}) {
            const entries = listeners.get(type) || [];
            if (!entries.some(entry => entry.callback === callback)) {
                entries.push({ callback, once: Boolean(options?.once) });
            }
            listeners.set(type, entries);
        },
        removeEventListener(type, callback) {
            const entries = listeners.get(type) || [];
            listeners.set(type, entries.filter(entry => entry.callback !== callback));
        },
        listenerCount(type) { return (listeners.get(type) || []).length; },
        listenerCallbacks(type) { return (listeners.get(type) || []).map(entry => entry.callback); },
        dispatch(type, values = {}) {
            const event = values;
            if (!Object.hasOwn(event, 'target')) event.target = this;
            event.currentTarget = this;
            event.preventDefault ??= () => {};
            event.stopPropagation ??= () => {};
            for (const entry of [...(listeners.get(type) || [])]) {
                if (!(listeners.get(type) || []).includes(entry)) continue;
                // Remove before calling: a recursive dispatch cannot call a once listener twice.
                if (entry.once) this.removeEventListener(type, entry.callback);
                entry.callback.call(this, event);
            }
            return event;
        },
        append(...children) {
            for (const child of children) {
                child.remove?.();
                child.parentElement = this;
                this.children.push(child);
            }
        },
        replaceChildren(...children) {
            const document = documentFor();
            if (document?.activeElement !== this && this.contains(document?.activeElement)) {
                document.activeElement = null;
            }
            this.children.forEach(child => { child.parentElement = null; });
            this.children = [];
            this.append(...children);
        },
        remove() {
            if (!this.parentElement) return;
            const document = documentFor();
            if (this.contains(document?.activeElement)) document.activeElement = null;
            this.parentElement.children = this.parentElement.children.filter(child => child !== this);
            this.parentElement = null;
        },
        contains(target) {
            return target === this || this.children.some(child => child.contains?.(target));
        },
        focus() {
            this.focused = true;
            const document = documentFor();
            if (document) document.activeElement = this;
            this.dispatch('focus');
        },
    };
}

module.exports = { domMechanics };
