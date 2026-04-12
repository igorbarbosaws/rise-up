const API_CONFIG = {
    localPath: 'data/agencias.json',
    bcbEndpoint: 'https://olinda.bcb.gov.br/olinda/servico/Informes_Agencias/versao/v1/odata/Agencias'
};

/**
 * @param {string} filter
 */
async function getAgencias(filter = '') {
    try {
        const response = await fetch(API_CONFIG.localPath);
        
        if (!response.ok) {
            throw new Error('Não foi possível carregar os dados das agências.');
        }

        const data = await response.json();

        if (filter) {
            return data.filter(ag => 
                ag.municipio.toLowerCase().includes(filter.toLowerCase()) || 
                ag.uf.toLowerCase() === filter.toLowerCase()
            );
        }

        return data;
    } catch (error) {
        console.error("Erro na API:", error);
        return [];
    }
}

function formatAddress(agencia) {
    return `${agencia.logradouro}, ${agencia.numero} - ${agencia.bairro}, ${agencia.municipio} - ${agencia.uf}`;
}