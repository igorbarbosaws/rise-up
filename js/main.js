const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const agenciasGrid = document.getElementById('agencias-grid');

async function buscarAgencias() {
    const termoBusca = searchInput.value.trim();

    agenciasGrid.innerHTML = '<p>A carregar agências...</p>';

    const agencias = await getAgencias(termoBusca);

    renderizarInterface(agencias);
}

function renderizarInterface(agencias) {
    agenciasGrid.innerHTML = '';

    if (agencias.length === 0) {
        agenciasGrid.innerHTML = '<p class="error">Nenhuma agência encontrada para esta busca.</p>';
        return;
    }

    agencias.forEach(agencia => {
        const infoPopup = `
            <strong>${agencia.nome}</strong><br>
            ${formatAddress(agencia)}
        `;
        addAgencyMarker(agencia.lat, parseInt(agencia.lng), infoPopup);

        const card = document.createElement('div');
        card.className = 'agencia-card';
        card.innerHTML = `
            <h3>${agencia.nome}</h3>
            <p><strong>Prefixo:</strong> ${agencia.prefixo}</p>
            <p>${formatAddress(agencia)}</p>
            <button onclick="focarNoMapa(${agencia.lat}, ${agencia.lng})">Ver no Mapa</button>
        `;
        agenciasGrid.appendChild(card);
    });
}

function focarNoMapa(lat, lng) {
    map.setView([lat, lng], 15);
}

searchBtn.addEventListener('click', buscarAgencias);

searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') buscarAgencias();
});