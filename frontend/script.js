// Session ID Management for Multi-Turn Memory
let currentSessionId = localStorage.getItem("support_session_id");
if (!currentSessionId) {
    currentSessionId = "sess-" + Math.random().toString(36).substring(2, 8);
    localStorage.setItem("support_session_id", currentSessionId);
}

document.getElementById("currentSessionDisplay").textContent = currentSessionId;
document.getElementById("initTime").textContent = formatTime(new Date());

function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(unsafe) {
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatBotMessage(text) {
    let formatted = escapeHtml(text);
    formatted = formatted.replace(/\n\n/g, "<br><br>").replace(/\n/g, "<br>");
    return formatted;
}

// Tab Switching (Chat vs Dashboard)
function switchTab(tab) {
    const chatBtn = document.getElementById("tabChatBtn");
    const dashBtn = document.getElementById("tabDashboardBtn");
    const chatView = document.getElementById("chatView");
    const dashView = document.getElementById("dashboardView");

    if (tab === "chat") {
        chatBtn.classList.add("active");
        dashBtn.classList.remove("active");
        chatView.classList.add("active");
        dashView.classList.remove("active");
    } else {
        dashBtn.classList.add("active");
        chatBtn.classList.remove("active");
        dashView.classList.add("active");
        chatView.classList.remove("active");
        loadDashboardData();
    }
}

// Reset / Start New Conversation
function startNewConversation() {
    currentSessionId = "sess-" + Math.random().toString(36).substring(2, 8);
    localStorage.setItem("support_session_id", currentSessionId);
    document.getElementById("currentSessionDisplay").textContent = currentSessionId;

    const chatMessages = document.getElementById("chatMessages");
    chatMessages.innerHTML = `
        <div class="message-row bot">
            <div class="msg-avatar">🤖</div>
            <div class="msg-bubble">
                <div class="msg-header">
                    <span class="sender-name">NovaTech Resolution Agent</span>
                    <span class="msg-time">${formatTime(new Date())}</span>
                </div>
                <div class="msg-body">
                    Started a new conversational memory thread. How can I help you today?
                </div>
                <div class="msg-footer">
                    <span class="tag-pill welcome">NEW SESSION</span>
                </div>
            </div>
        </div>
    `;
}

// Append Message to Chat
function appendMessage(sender, text, intent = null, traces = [], escalated = false) {
    const chatMessages = document.getElementById("chatMessages");
    const isBot = sender === "bot";
    const timeStr = formatTime(new Date());

    const wrapper = document.createElement("div");
    wrapper.className = `message-row ${isBot ? "bot" : "user"}`;

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = isBot ? "🤖" : "👤";

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    const header = document.createElement("div");
    header.className = "msg-header";
    header.innerHTML = `
        <span class="sender-name">${isBot ? "NovaTech Resolution Agent" : "You"}</span>
        <span class="msg-time">${timeStr}</span>
    `;

    const body = document.createElement("div");
    body.className = "msg-body";
    if (isBot) {
        body.innerHTML = formatBotMessage(text);
    } else {
        body.textContent = text;
    }

    const footer = document.createElement("div");
    footer.className = "msg-footer";

    if (isBot) {
        let tagHtml = "";
        if (escalated) {
            tagHtml += `<span class="tag-pill escalated">🚨 HUMAN ESCALATED</span>`;
        } else if (intent) {
            tagHtml += `<span class="tag-pill">${intent.replace(/_/g, " ")}</span>`;
        }

        let traceBtn = "";
        if (traces && traces.length > 0) {
            const traceId = "trace-" + Math.random().toString(36).substring(2, 7);
            traceBtn = `<button class="trace-toggle-btn" onclick="toggleTrace('${traceId}')">🔍 View AI Reasoning (${traces.length} steps)</button>`;
            
            const traceBox = document.createElement("div");
            traceBox.id = traceId;
            traceBox.className = "trace-details-box";
            traceBox.style.display = "none";
            traceBox.innerHTML = traces.map((t, idx) => `
                <div><strong>[Step ${idx+1}]</strong> ${escapeHtml(t.step || 'ACTION')}: ${escapeHtml(JSON.stringify(t.tool || t.result || t.output || t))}</div>
            `).join("");

            footer.innerHTML = `<div>${tagHtml}</div>${traceBtn}`;
            bubble.appendChild(header);
            bubble.appendChild(body);
            bubble.appendChild(footer);
            bubble.appendChild(traceBox);
        } else {
            footer.innerHTML = `<div>${tagHtml}</div>`;
            bubble.appendChild(header);
            bubble.appendChild(body);
            bubble.appendChild(footer);
        }
    } else {
        bubble.appendChild(header);
        bubble.appendChild(body);
    }

    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);

    chatMessages.appendChild(wrapper);
    scrollToBottom();
}

function toggleTrace(id) {
    const el = document.getElementById(id);
    if (el) {
        el.style.display = el.style.display === "none" ? "block" : "none";
    }
}

function scrollToBottom() {
    const chatMessages = document.getElementById("chatMessages");
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator(show) {
    const el = document.getElementById("typingIndicator");
    el.style.display = show ? "block" : "none";
    if (show) scrollToBottom();
}

// Send Message
async function sendMessage(text) {
    const trimmed = text.trim();
    if (!trimmed) return;

    appendMessage("user", trimmed);

    const input = document.getElementById("userInput");
    const sendBtn = document.getElementById("sendBtn");
    input.disabled = true;
    sendBtn.disabled = true;

    showTypingIndicator(true);

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: trimmed,
                session_id: currentSessionId,
                customer_id: 1
            })
        });

        const data = await response.json();

        if (response.ok) {
            appendMessage("bot", data.response, data.intent, data.traces, data.escalated);
        } else {
            appendMessage("bot", `Error: ${data.detail || "Unable to reach assistant."}`, "ERROR");
        }
    } catch (err) {
        appendMessage("bot", `Connection error: ${err.message}`, "ERROR");
    } finally {
        showTypingIndicator(false);
        input.disabled = false;
        sendBtn.disabled = false;
        input.value = "";
        input.focus();
    }
}

function handleFormSubmit(event) {
    event.preventDefault();
    const input = document.getElementById("userInput");
    sendMessage(input.value);
}

function sendQuickMessage(text) {
    const input = document.getElementById("userInput");
    input.value = text;
    sendMessage(text);
}

// ==================== DASHBOARD DATA LOADING ====================

async function loadDashboardData() {
    try {
        // 1. Load Overview Stats
        const statsRes = await fetch("/api/dashboard/overview");
        if (statsRes.ok) {
            const stats = await statsRes.json();
            document.getElementById("statTotalOrders").textContent = stats.total_orders;
            document.getElementById("statProcessingOrders").textContent = `Processing: ${stats.order_status_counts["Processing"] || 0}`;
            document.getElementById("statDeliveredOrders").textContent = stats.order_status_counts["Delivered"] || 0;
            document.getElementById("statTotalTickets").textContent = stats.total_tickets;
            document.getElementById("statEscalatedTickets").textContent = stats.escalated_count;
        }

        // 2. Load Orders Table
        const ordersRes = await fetch("/api/dashboard/orders");
        if (ordersRes.ok) {
            const orders = await ordersRes.json();
            document.getElementById("ordersCountBadge").textContent = orders.length;
            const tbody = document.getElementById("ordersTableBody");
            tbody.innerHTML = orders.map(o => `
                <tr>
                    <td><strong>#${o.id}</strong></td>
                    <td>${escapeHtml(o.product_name)}</td>
                    <td>$${o.price.toFixed(2)}</td>
                    <td><span class="status-pill ${o.status.toLowerCase()}">${o.status}</span></td>
                    <td>${escapeHtml(o.customer_name)}</td>
                </tr>
            `).join("");
        }

        // 3. Load Tickets Table
        const ticketsRes = await fetch("/api/dashboard/tickets");
        if (ticketsRes.ok) {
            const tickets = await ticketsRes.json();
            document.getElementById("ticketsCountBadge").textContent = tickets.length;
            const tbody = document.getElementById("ticketsTableBody");
            tbody.innerHTML = tickets.map(t => {
                const priorityClass = t.priority ? t.priority.toLowerCase() : "normal";
                return `
                    <tr>
                        <td><strong>#${t.id}</strong></td>
                        <td><span class="priority-pill ${priorityClass}">${t.priority || 'Normal'}</span></td>
                        <td>${t.status}</td>
                        <td>${escapeHtml(t.assigned_agent || 'Support Team')}</td>
                        <td>${escapeHtml(t.issue.substring(0, 45))}${t.issue.length > 45 ? '...' : ''}</td>
                    </tr>
                `;
            }).join("");
        }

        // 4. Load Trace Stream
        const traceRes = await fetch("/api/dashboard/traces");
        if (traceRes.ok) {
            const traces = await traceRes.json();
            const stream = document.getElementById("traceStream");
            if (traces.length === 0) {
                stream.innerHTML = `<div class="trace-placeholder">No agent activity logged yet. Chat with the agent to observe reasoning in real time!</div>`;
            } else {
                stream.innerHTML = traces.map(tr => `
                    <div class="trace-item">
                        <span class="trace-time">[${tr.timestamp}]</span>
                        <span class="trace-action">${escapeHtml(tr.action)}:</span>
                        <span class="trace-details">${escapeHtml(typeof tr.details === 'object' ? JSON.stringify(tr.details) : tr.details)}</span>
                    </div>
                `).join("");
            }
        }
    } catch (e) {
        console.error("Failed to load dashboard data:", e);
    }
}

async function resetDatabaseDemo() {
    if (!confirm("Are you sure you want to reset the SQLite database to its initial demo state?")) return;
    try {
        const res = await fetch("/api/dashboard/reset", { method: "POST" });
        if (res.ok) {
            alert("Database successfully reset to demo state!");
            loadDashboardData();
        }
    } catch (e) {
        alert("Failed to reset database: " + e.message);
    }
}
