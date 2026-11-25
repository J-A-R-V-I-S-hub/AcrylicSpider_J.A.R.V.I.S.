// sw.js — service worker minimale per rendere /jarvis installabile.
//
// NON mette niente in cache: il pannello legge dal robot in tempo reale
// (camera, assetto, comandi) e una copia vecchia sarebbe peggio di niente.
// Serve solo perché i browser richiedono un service worker con un handler
// di fetch per proporre "Aggiungi alla schermata Home".

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (evento) => {
    evento.waitUntil(self.clients.claim());
});

// Nessuna intercettazione: ogni richiesta va in rete come prima.
self.addEventListener('fetch', () => {});
