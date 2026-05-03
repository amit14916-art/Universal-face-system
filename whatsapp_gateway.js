const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require("@whiskeysockets/baileys");
const { Boom } = require("@hapi/boom");
const qrcode = require("qrcode");
const express = require("express");
const app = express();
const port = 9000;

app.use(express.json());

let sock;
let qrCodeData = null;
let connectionStatus = "Disconnected";

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState("auth_info_baileys");
    
    sock = makeWASocket({
        auth: state,
        printQRInTerminal: false,
        browser: ["Sentinel AI", "Chrome", "1.1.0"],
        syncFullHistory: false,
        connectTimeoutMs: 60000,
        keepAliveIntervalMs: 10000,
        retryRequestDelayMs: 5000
    });

    sock.ev.on("connection.update", (update) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            qrCodeData = qr;
        }

        if (connection === "close") {
            const shouldReconnect = (lastDisconnect.error instanceof Boom)?.output?.statusCode !== DisconnectReason.loggedOut;
            console.log("connection closed due to ", lastDisconnect.error, ", reconnecting ", shouldReconnect);
            connectionStatus = "Disconnected";
            qrCodeData = null;
            if (shouldReconnect) connectToWhatsApp();
        } else if (connection === "open") {
            console.log("opened connection");
            connectionStatus = "Connected";
            qrCodeData = null;
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
