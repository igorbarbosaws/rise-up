let map;

function initMap() {
    const brasilCenter = [-14.235, -51.925];
    const initialZoom = 4;

    map = L.map('map').setView(brasilCenter, initialZoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18
    }).addTo(map);

    console.log("Mapa inicializado com sucesso!");
}

/**
 * @param {number} lat
 * @param {number} lng
 * @param {string} info
 */

function addAgencyMarker(lat, lng, info) {
    if (!map) return;

    const marker = L.marker([lat, lng]).addTo(map);
    

    marker.bindPopup(`
        <div class="map-popup">
            <strong>Banco do Brasil</strong><br>
            ${info}
        </div>
    `);
}

initMap();