const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    Browsers,
} = require("@whiskeysockets/baileys");
const { Boom } = require("@hapi/boom");
const qrcode = require("qrcode");
const express = require("express");
const app = express();
const port = 9000;

app.use(express.json());

let sock;
let qrCodeData = null;
let connectionStatus = "Disconnected";
let reconnectAttempt = 0;
let reconnectTimer = null;

const MAX_RECONNECT_DELAY_MS = 60_000;
const BASE_RECONNECT_DELAY_MS = 2_000;

function scheduleReconnect(reason) {
    if (reconnectTimer) return;
    const delay = Math.min(
        MAX_RECONNECT_DELAY_MS,
        BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttempt)
    );
    reconnectAttempt += 1;
    console.log(`Scheduling WhatsApp reconnect in ${delay}ms (attempt ${reconnectAttempt}, reason: ${reason})`);
    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectToWhatsApp();
    }, delay);
}

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState("auth_info_baileys");

    let version;
    try {
        const fetched = await fetchLatestBaileysVersion({ timeout: 15_000 });
        version = fetched.version;
        if (!fetched.isLatest && fetched.error) {
            console.warn("Using bundled Baileys version (fetch failed):", fetched.error?.message || fetched.error);
        }
    } catch (e) {
        console.warn("fetchLatestBaileysVersion threw, using socket defaults:", e?.message || e);
    }

    sock = makeWASocket({
        auth: state,
        printQRInTerminal: false,
        browser: Browsers.ubuntu("Chrome"),
        ...(version ? { version } : {}),
        syncFullHistory: false,
        connectTimeoutMs: 60000,
        keepAliveIntervalMs: 10000,
        retryRequestDelayMs: 5000,
    });

    sock.ev.on("connection.update", (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            qrCodeData = qr;
        }

        if (connection === "close") {
            const err = lastDisconnect?.error;
            const statusCode =
                err instanceof Boom ? err.output?.statusCode : undefined;
            const loggedOut = statusCode === DisconnectReason.loggedOut;
            const is405 =
                statusCode === 405 ||
                (err instanceof Boom &&
                    err?.data?.reason === "405");

            console.log(
                `Connection closed: ${err?.message || err}. StatusCode: ${statusCode}. LoggedOut: ${loggedOut}`
            );

            connectionStatus = "Disconnected";
            qrCodeData = null;

            if (loggedOut) {
                console.log("Logged out. Reconnect manually.");
                reconnectAttempt = 0;
                return;
            }

            if (is405) {
                console.warn(
                    "WhatsApp handshake rejected (405). This usually means the browser fingerprint or Baileys version is blocked. Applying extended delay."
                );
                // For 405, we might want to reset the session if it persists, 
                // but for now let's just use the exponential backoff which is already implemented.
            }

            scheduleReconnect(is405 ? "405" : statusCode || "unknown");
        } else if (connection === "open") {
            console.log("WhatsApp connection opened successfully.");
            connectionStatus = "Connected";
            qrCodeData = null;
            reconnectAttempt = 0;
        }
    });

    sock.ev.on("creds.update", saveCreds);
}

// API Endpoints for Python to communicate with
app.get("/qr", async (req, res) => {
    if (qrCodeData) {
        const qrImage = await qrcode.toDataURL(qrCodeData);
        res.json({ qr: qrImage, status: connectionStatus });
    } else {
        res.json({ qr: null, status: connectionStatus });
    }
});

app.post("/send", async (req, res) => {
    const { number, message } = req.body;
    if (connectionStatus !== "Connected") {
        return res.status(400).json({ error: "WhatsApp not connected" });
    }

    try {
        const jid = number.includes("@s.whatsapp.net") ? number : `${number.replace(/\D/g, "")}@s.whatsapp.net`;
        await sock.sendMessage(jid, { text: message });
        res.json({ success: true });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

app.get("/status", (req, res) => {
    res.json({ status: connectionStatus });
});

app.post("/logout", async (req, res) => {
    try {
        await sock.logout();
        connectionStatus = "Disconnected";
        res.json({ success: true });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

app.listen(port, () => {
    console.log(`WhatsApp Gateway listening at http://localhost:${port}`);
    connectToWhatsApp();
});
