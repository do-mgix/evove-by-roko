class ScreenUI {
    constructor(container) {
        this.container = container;
        this.lastRender = null;
        this.sequenceTimer = null;
        this.listPageIndex = 0;
        this.listPageSize = 5;
    }

    _normalizeMessage(msg) {
        if (Array.isArray(msg)) {
            return msg.join(' ');
        }
        return String(msg ?? '');
    }

    _flattenMessages(messages) {
        const lines = [];
        messages.forEach((msg) => {
            const text = this._normalizeMessage(msg);
            if (!text) return;
            text.split('\n').forEach((line) => {
                const trimmed = line.trim();
                if (trimmed.length > 0) {
                    lines.push(trimmed);
                }
            });
        });
        return lines;
    }

    _isListMessage(lines) {
        if (!lines.length) return false;
        const first = lines[0];
        return first.startsWith('--- ') && first.endsWith(' ---');
    }

    _isActionSequence(lines) {
        if (!lines.length) return false;
        return lines.some((line) => /score plus|increase by/i.test(line));
    }

    _stopSequence() {
        if (this.sequenceTimer) {
            clearInterval(this.sequenceTimer);
            this.sequenceTimer = null;
        }
    }

    clearScreen() {
        this._stopSequence();
        this.container.classList.remove('menu', 'screen-list', 'screen-seq');
        this.container.classList.add('screen-single');
        this.container.innerHTML = '';
        this.lastRender = null;
    }

    showMessage(message) {
        this._stopSequence();
        const text = this._normalizeMessage(message).trim();
        if (!text) return;
        this.container.classList.remove('menu', 'screen-list');
        this.container.classList.add('screen-single');
        this.container.innerHTML = `<div class="screen-message">${text}</div>`;
        this.lastRender = { mode: 'single', message: text };
    }

    showList(title, items) {
        this._stopSequence();
        const safeTitle = title || 'SYSTEM';
        const listItems = Array.isArray(items) ? items : (items ? [String(items)] : []);
        this.listPageIndex = 0;
        this.container.classList.remove('menu', 'screen-single');
        this.container.classList.add('screen-list');
        this._renderListPage(safeTitle, listItems, this.listPageIndex);
        this.lastRender = { mode: 'list', title: safeTitle, items: listItems };
    }

    _renderListPage(title, items, pageIndex) {
        const totalItems = items.length;
        const totalPages = Math.max(1, Math.ceil(totalItems / this.listPageSize));
        const safeIndex = Math.min(Math.max(0, pageIndex), totalPages - 1);
        const start = safeIndex * this.listPageSize;
        const pageItems = items.slice(start, start + this.listPageSize);
        const html = [
            `<div class="screen-title">${title} (${safeIndex + 1}/${totalPages})</div>`,
            ...pageItems.map((item) => `<div class="screen-item">${item}</div>`)
        ];
        this.container.innerHTML = html.join('');
        this.listPageIndex = safeIndex;
    }

    nextListPage() {
        if (!this.lastRender || this.lastRender.mode !== 'list') return false;
        const items = this.lastRender.items || [];
        const totalPages = Math.max(1, Math.ceil(items.length / this.listPageSize));
        if (totalPages <= 1) return false;
        const nextIndex = (this.listPageIndex + 1) % totalPages;
        this._renderListPage(this.lastRender.title, items, nextIndex);
        return true;
    }

    showSequence(messages, delayMs = 3000) {
        this._stopSequence();
        const lines = this._flattenMessages(messages);
        if (!lines.length) return;
        this.container.classList.remove('menu', 'screen-list');
        this.container.classList.add('screen-seq');
        let idx = 0;
        const render = () => {
            const line = lines[idx] || '';
            this.container.innerHTML = `<div class="screen-message">${line}</div>`;
        };
        render();
        this.sequenceTimer = setInterval(() => {
            idx = (idx + 1) % lines.length;
            render();
        }, delayMs);
        this.lastRender = { mode: 'seq', messages: lines, delayMs, index: idx };
    }

    exitListOrSequence() {
        if (!this.lastRender) return false;
        if (this.lastRender.mode === 'list' || this.lastRender.mode === 'seq') {
            this.clearScreen();
            return true;
        }
        return false;
    }

    showFromMessages(messages) {
        const lines = this._flattenMessages(messages || []);
        if (!lines.length) return;
        if (this._isListMessage(lines)) {
            const rawTitle = lines[0].replace(/^---\s*/, '').replace(/\s*---$/, '');
            const items = lines.slice(1);
            this.showList(rawTitle, items);
            return;
        }
        if (this._isActionSequence(lines)) {
            this.showSequence(lines, 3000);
            return;
        }
        if (lines.length > 1) {
            this.showList('SYSTEM', lines);
            return;
        }
        this.showMessage(lines[0]);
    }

    renderLast() {
        if (!this.lastRender) return;
        if (this.lastRender.mode === 'list') {
            this._renderListPage(this.lastRender.title, this.lastRender.items || [], this.listPageIndex);
        } else if (this.lastRender.mode === 'seq') {
            this.showSequence(this.lastRender.messages, this.lastRender.delayMs);
        } else {
            this.showMessage(this.lastRender.message);
        }
    }
}

window.ScreenUI = ScreenUI;
