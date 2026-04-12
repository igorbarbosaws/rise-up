document.addEventListener("DOMContentLoaded", function() {

    const menuToggle = document.querySelector('.menu-toggle');
    const sidebar = document.querySelector('#sidebar');
    const content = document.querySelector('#content');

    if (menuToggle && sidebar && content) {
        menuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('active');
            content.classList.toggle('active');

            if (typeof map !== 'undefined') {
                setTimeout(() => { map.invalidateSize(); }, 300);
            }
        });
    }

    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const agenciasGrid = document.getElementById('agencias-grid');

    if (searchBtn && searchInput) {
        
        async function buscarAgencias() {
            const termoBusca = searchInput.value.trim();
            if (!agenciasGrid) return;

            agenciasGrid.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Carregando agências...</div>';

            try {
                const agencias = await getAgencias(termoBusca);
                renderizarInterface(agencias);
            } catch (error) {
                agenciasGrid.innerHTML = '<p class="error">Erro ao conectar com a base de dados.</p>';
                console.error("Erro na busca:", error);
            }
        }

        function renderizarInterface(agencias) {
            if (!agenciasGrid) return;
            agenciasGrid.innerHTML = '';

            if (agencias.length === 0) {
                agenciasGrid.innerHTML = '<p class="error">Nenhuma agência encontrada para esta busca.</p>';
                return;
            }

            agencias.forEach(agencia => {
                const infoPopup = `
                    <strong>${agencia.nome}</strong><br>
                    ${agencia.endereco || 'Endereço não informado'}
                `;

                if (typeof addAgencyMarker === 'function') {
                    addAgencyMarker(agencia.lat, agencia.lng, infoPopup);
                }

                const card = document.createElement('div');
                card.className = 'info-card agencia-card';
                card.innerHTML = `
                    <h3>${agencia.nome}</h3>
                    <p><strong>Prefixo:</strong> ${agencia.prefixo}</p>
                    <p><i class="fas fa-map-marker-alt"></i> ${agencia.endereco || 'Consultar base'}</p>
                    <button class="btn-action" onclick="focarNoMapa(${agencia.lat}, ${agencia.lng})">
                        Ver no Mapa
                    </button>
                `;
                agenciasGrid.appendChild(card);
            });
        }

        searchBtn.addEventListener('click', buscarAgencias);
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') buscarAgencias();
        });
    }
});


function focarNoMapa(lat, lng) {
    if (typeof map !== 'undefined') {
        map.setView([lat, lng], 15);
    }
}