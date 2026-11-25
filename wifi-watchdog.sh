#!/bin/bash
# wifi-watchdog.sh — tiene il Raspberry Pi agganciato alla rete WiFi configurata.
#
# PERCHÉ ESISTE
# All'avvio NetworkManager ha pochi secondi per connettersi. Se il modem è
# lento, wifi_hotspot_manager.sh apre la rete di emergenza e il Pi resta lì:
# raggiungibile solo via cavo o hotspot. Questo script, una volta al minuto,
# prova a riportarlo sulla rete vera.
#
# Il nome della rete NON è scritto qui: viene letto da NetworkManager, cioè
# dalla prima connessione wifi che non sia l'hotspot di emergenza. Così lo
# stesso script funziona su qualsiasi installazione.
#
# Installato da setup.py come /usr/local/bin/wifi-watchdog.sh e richiamato da
# wifi-watchdog.timer.

HOTSPOT="Adeept_Robot"
IFACE="wlan0"
LOG="/var/log/wifi-watchdog.log"

# nome della connessione wifi "vera" (la prima che non è l'hotspot)
WIFI=$(nmcli -t -f NAME,TYPE connection show 2>/dev/null \
       | awk -F: -v h="$HOTSPOT" '$2=="802-11-wireless" && $1!=h {print $1; exit}')

[ -z "$WIFI" ] && exit 0

stato() {
    nmcli -t -f DEVICE,CONNECTION device status 2>/dev/null \
        | awk -F: -v d="$IFACE" '$1==d{print $2}'
}

corrente=$(stato)

# già sulla rete buona
[ "$corrente" = "$WIFI" ] && exit 0

# interfaccia assente o giù: non insistere
[ -z "$corrente" ] && exit 0

echo "$(date '+%F %T') wlan0=$corrente → provo $WIFI" >> "$LOG"

# l'hotspot occupa l'interfaccia: va spento per poter fare il client
if [ "$corrente" = "$HOTSPOT" ]; then
    nmcli connection down "$HOTSPOT" >/dev/null 2>&1
    sleep 1
fi

nmcli connection up "$WIFI" ifname "$IFACE" >/dev/null 2>&1
sleep 6

nuovo=$(stato)
echo "$(date '+%F %T') → wlan0=$nuovo" >> "$LOG"

# se non è andata, rimetti l'hotspot: meglio un collegamento di emergenza
# che nessun collegamento
if [ "$nuovo" != "$WIFI" ] && [ "$nuovo" != "$HOTSPOT" ]; then
    nmcli connection up "$HOTSPOT" ifname "$IFACE" >/dev/null 2>&1
    echo "$(date '+%F %T') → ripristinato $HOTSPOT" >> "$LOG"
fi

exit 0
