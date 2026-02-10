class ScreenUI {
    constructor(container) {
        this.container = container;
        this.lastRender = null;
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

    showMessage(message) {
        const text = this._normalizeMessage(message).trim();
        if (!text) return;
        this.container.classList.remove('menu', 'screen-list');
        this.container.classList.add('screen-single');
        this.container.innerHTML = `<div class="screen-message">${text}</div>`;
        this.lastRender = { mode: 'single', message: text };
    }

    showList(title, items) {
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

    showFromMessages(messages) {
        const lines = this._flattenMessages(messages || []);
        if (!lines.length) return;
        if (this._isListMessage(lines)) {
            const rawTitle = lines[0].replace(/^---\s*/, '').replace(/\s*---$/, '');
            const items = lines.slice(1);
            this.showList(rawTitle, items);
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
        } else {
            this.showMessage(this.lastRender.message);
        }
    }
}

window.ScreenUI = ScreenUI;
