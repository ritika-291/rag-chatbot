(function () {
    console.log("Docubuddy Custom JS Loaded!");

    let lastClickedThreadId = null;

    // Track which thread's menu button was clicked
    document.addEventListener('mousedown', (event) => {
        let current = event.target;
        while (current && current !== document.body) {
            if (current.tagName === 'A' && current.getAttribute('href') && current.getAttribute('href').includes('/thread/')) {
                const href = current.getAttribute('href');
                const match = href.match(/\/thread\/([^\/]+)/);
                if (match) {
                    lastClickedThreadId = match[1];
                    return;
                }
            }

            const parentListItem = current.closest('.MuiListItem-root') ||
                current.closest('div[role="listitem"]') ||
                current.closest('.cl-sidebar-thread-item') ||
                current.closest('[class*="thread"]');
            if (parentListItem) {
                const link = parentListItem.querySelector('a[href*="/thread/"]');
                if (link) {
                    const href = link.getAttribute('href');
                    const match = href.match(/\/thread\/([^\/]+)/);
                    if (match) {
                        lastClickedThreadId = match[1];
                        return;
                    }
                }
            }
            current = current.parentElement;
        }
    }, true);

    function getSessionId() {
        // 1. Try to get from URL pathname: /thread/103 or /thread/uuid-string
        const match = window.location.pathname.match(/\/thread\/([^\/]+)/);
        if (match) {
            return match[1];
        }

        // 2. Try to get from active sidebar item link
        const activeSidebarLink = document.querySelector('a.Mui-selected[href*="/thread/"]');
        if (activeSidebarLink) {
            const hrefMatch = activeSidebarLink.getAttribute('href').match(/\/thread\/([^\/]+)/);
            if (hrefMatch) {
                return hrefMatch[1];
            }
        }

        return null;
    }

    async function fetchTokenUsage(sessionId) {
        try {
            let url = '/api/token_usage';
            if (sessionId) {
                url += `?session_id=${sessionId}`;
            }
            const res = await fetch(url);
            if (res.ok) {
                return await res.json();
            }
        } catch (e) {
            console.error("Error fetching token usage:", e);
        }
        return null;
    }

    function drawCircle(container, data) {
        const allocated = data ? data.allocated : 0;
        const used = data ? data.used : 0;
        const remaining = data ? data.remaining : 0;

        if (allocated <= 0) {
            container.innerHTML = '';
            return;
        }

        const pct = Math.min(100, Math.max(0, (used / allocated) * 100));
        const radius = 9;
        const circumference = 2 * Math.PI * radius; // ~56.548
        const strokeDashoffset = circumference - (pct / 100) * circumference;

        // Choose color based on usage percentage
        let color = "#26A69A"; // Teal
        if (pct >= 90) {
            color = "#EF5350"; // Red
        } else if (pct >= 70) {
            color = "#FFA726"; // Orange
        }

        container.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" style="transform: rotate(-90deg); cursor: pointer;" title="Tokens: ${used} / ${allocated} used (${Math.round(pct)}%)">
                <circle cx="12" cy="12" r="${radius}" fill="none" stroke="#333" stroke-width="2"/>
                <circle cx="12" cy="12" r="${radius}" fill="none" stroke="${color}" stroke-width="2" 
                    stroke-dasharray="${circumference}" 
                    stroke-dashoffset="${strokeDashoffset}" 
                    stroke-linecap="round"/>
            </svg>
        `;
        container.title = `Token Usage: ${used} / ${allocated} tokens used (${Math.round(pct)}%)`;
    }

    async function updateTokenUsageCircle() {
        let container = document.getElementById('token-progress-circle');
        if (!container) {
            container = document.createElement('div');
            container.id = 'token-progress-circle';
            // Apply fixed styling to position it above the download button
            Object.assign(container.style, {
                position: 'fixed',
                bottom: '160px', // 60px above the download button
                right: '30px',
                zIndex: '9999',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: 'rgba(0, 0, 0, 0.5)',
                borderRadius: '50%',
                padding: '6px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                transition: 'opacity 0.2s',
            });
            document.body.appendChild(container);
        }

        const sessionId = getSessionId();
        const data = await fetchTokenUsage(sessionId);
        if (data) {
            drawCircle(container, data);
        }
    }

    // Dynamic UI Injection for Download Chat
    function injectHeaderDownloadButton() {
        if (document.getElementById('header-download-btn')) {
            return;
        }

        const downloadBtn = document.createElement('button');
        downloadBtn.id = 'header-download-btn';
        downloadBtn.title = "Download Chat as PDF";
        downloadBtn.innerHTML = `
            <svg viewBox="0 0 24 24" style="width: 20px; height: 20px; fill: currentColor; opacity: 0.9;">
                <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"></path>
            </svg>
        `;

        Object.assign(downloadBtn.style, {
            position: 'fixed',
            bottom: '100px',
            right: '30px',
            zIndex: '9999',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '12px',
            backgroundColor: '#F80061',
            color: 'white',
            border: 'none',
            borderRadius: '50%',
            cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            transition: 'transform 0.2s, background-color 0.2s, opacity 0.2s',
        });

        downloadBtn.onmouseover = () => {
            downloadBtn.style.backgroundColor = '#D00052';
            downloadBtn.style.transform = 'scale(1.05)';
        };
        downloadBtn.onmouseout = () => {
            downloadBtn.style.backgroundColor = '#F80061';
            downloadBtn.style.transform = 'scale(1)';
        };

        downloadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const threadId = getSessionId();
            if (!threadId) {
                alert("Please start a chat first before downloading.");
                return;
            }

            const a = document.createElement('a');
            a.href = `/api/download_chat/${threadId}`;
            a.download = `chat_${threadId}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        });

        document.body.appendChild(downloadBtn);
    }

    let welcomeMarkdown = "";
    let isFetchingMarkdown = false;

    async function fetchWelcomeMarkdown() {
        if (welcomeMarkdown || isFetchingMarkdown) return;
        isFetchingMarkdown = true;
        try {
            const res = await fetch('/api/welcome_markdown');
            if (res.ok) {
                const data = await res.json();
                welcomeMarkdown = data.markdown;
            }
        } catch (e) {
            console.error("Error fetching welcome markdown:", e);
        } finally {
            isFetchingMarkdown = false;
        }
    }

    function parseMarkdown(md) {
        if (!md) return "";
        // Clean markdown parsing for standard formats
        return md
            .replace(/^#\s+(.+)$/gm, '<h1 style="font-family: \'Outfit\', \'Inter\', sans-serif; font-size: 2.6rem; font-weight: 800; background: linear-gradient(135deg, #FF5C93 0%, #F80061 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0 0 12px 0; letter-spacing: -1px; filter: drop-shadow(0 2px 8px rgba(248,0,97,0.25)); text-align: center;">$1</h1>')
            .replace(/^##\s+(.+)$/gm, '<h2 style="font-family: \'Outfit\', \'Inter\', sans-serif; font-size: 1.8rem; font-weight: 700; color: #fff; margin: 24px 0 12px 0; text-align: center;">$1</h2>')
            .replace(/^###\s+(.+)$/gm, '<h3 style="font-family: \'Outfit\', \'Inter\', sans-serif; font-size: 1.4rem; font-weight: 600; color: #eee; margin: 18px 0 10px 0; text-align: center;">$1</h3>')
            .replace(/^\s*-\s+(.+)$/gm, '<li style="color: #ccc; margin: 6px 0; font-size: 1.1rem; line-height: 1.5; font-family: \'Inter\', sans-serif;">$1</li>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .split('\n\n')
            .map(p => {
                const trimmed = p.trim();
                if (!trimmed) return "";
                if (trimmed.startsWith('<h') || trimmed.startsWith('<li') || trimmed.startsWith('<ul') || trimmed.startsWith('<div')) {
                    return trimmed;
                }
                return `<p style="font-family: 'Inter', sans-serif; font-size: 1.2rem; color: rgba(255,255,255,0.65); line-height: 1.6; margin: 10px 0 20px 0; text-align: center; font-weight: 400;">${trimmed}</p>`;
            })
            .join('\n');
    }

    async function updateWelcomeScreen() {
        if (document.title !== "DocBuddy") {
            document.title = "DocBuddy";
        }

        const hasMessages = document.querySelector('.step-item') ||
            document.querySelector('[id^="step-"]') ||
            document.querySelector('.cl-message') ||
            document.querySelector('.chat-message') ||
            document.querySelector('[data-testid="message"]');

        const customTitle = document.getElementById('custom-welcome-title');

        if (hasMessages) {
            if (customTitle) {
                customTitle.style.display = 'none';
            }
            return;
        }

        const imgs = document.querySelectorAll('img, svg');
        let logoEl = null;

        for (const el of imgs) {
            if (el.closest('header') ||
                el.closest('.cl-sidebar') ||
                el.closest('form') ||
                el.closest('.MuiInputBase-root') ||
                el.id === 'token-progress-circle' ||
                el.closest('#token-progress-circle') ||
                el.closest('#header-download-btn')) {
                continue;
            }

            const rect = el.getBoundingClientRect();
            if (rect.width > 25 && rect.height > 25) {
                // The logo is typically in the upper part of the welcome screen
                if (rect.top < window.innerHeight * 0.6) {
                    logoEl = el;
                    break;
                }
            }
        }

        if (logoEl) {
            logoEl.style.display = 'none';

            // Fetch markdown if we haven't already
            if (!welcomeMarkdown) {
                await fetchWelcomeMarkdown();
            }

            if (!customTitle) {
                const newTitle = document.createElement('div');
                newTitle.id = 'custom-welcome-title';
                newTitle.style.animation = 'fadeIn 0.6s ease-out';
                newTitle.style.marginBottom = '2.5rem';
                newTitle.style.display = 'flex';
                newTitle.style.flexDirection = 'column';
                newTitle.style.alignItems = 'center';
                newTitle.style.justifyContent = 'center';

                newTitle.innerHTML = parseMarkdown(welcomeMarkdown || "# Hello! 👋 DocBuddy");
                logoEl.parentNode.insertBefore(newTitle, logoEl);
            } else {
                customTitle.style.display = 'block';
                // If markdown was fetched after insertion, update the HTML
                if (welcomeMarkdown && !customTitle.getAttribute('data-loaded')) {
                    customTitle.innerHTML = parseMarkdown(welcomeMarkdown);
                    customTitle.setAttribute('data-loaded', 'true');
                }
            }
        }
    }

    // Run regularly to keep the circle and the download button in DOM and updated
    setInterval(() => {
        updateTokenUsageCircle();
        injectHeaderDownloadButton();
    }, 2000);

    // Fast check for the welcome screen logo to replace it instantly
    setInterval(updateWelcomeScreen, 100);
})();
