class ScreenUI {
    constructor(container) {
        this.container = container;
        this.lastRender = null;
        this.sequenceTimer = null;
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
        const listItems = (items || []).slice(0, 9);
        this.container.classList.remove('menu', 'screen-single');
        this.container.classList.add('screen-list');
        const html = [
            `<div class="screen-title">${safeTitle}</div>`,
            ...listItems.map((item) => `<div class="screen-item">${item}</div>`)
        ];
        this.container.innerHTML = html.join('');
        this.lastRender = { mode: 'list', title: safeTitle, items: listItems };
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
            this.showList(this.lastRender.title, this.lastRender.items);
        } else if (this.lastRender.mode === 'seq') {
            this.showSequence(this.lastRender.messages, this.lastRender.delayMs);
        } else {
            this.showMessage(this.lastRender.message);
        }
    }
}

window.ScreenUI = ScreenUI;
