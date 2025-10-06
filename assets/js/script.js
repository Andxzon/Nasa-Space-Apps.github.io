document.addEventListener('DOMContentLoaded', () => {
    const searchForm = document.getElementById('search-form');
    const searchInput = document.getElementById('search-input');
    const searchStatus = document.getElementById('search-status');
    const resultsContainer = document.getElementById('results-container');

    searchForm.addEventListener('submit', async (event) => {
        event.preventDefault(); 

        const query = searchInput.value.trim();

        if (query) {
            searchStatus.textContent = 'Buscando resultados...';
            resultsContainer.innerHTML = ''; 

            try {
                const response = await fetch(`http://localhost:5000/search?query=${encodeURIComponent(query)}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const results = await response.json();

                searchStatus.textContent = `Mostrando resultados para: "${query}"`;

                if (results.length > 0) {
                    const resultsList = document.createElement('ul');
                    results.forEach(result => {
                        const listItem = document.createElement('li');

                        const textContent = document.createElement('div');
                        textContent.classList.add('text-content');

                        const link = document.createElement('a');
                        link.href = result.link;
                        link.textContent = result.title;
                        link.target = '_blank'; 
                        
                        const summary = document.createElement('p');
                        summary.textContent = result.summary;

                        textContent.appendChild(link);
                        textContent.appendChild(summary);

                        const image = document.createElement('img');
                        image.src = 'assets/images/exam2.png';
                        image.classList.add('result-image');

                        listItem.appendChild(textContent);
                        listItem.appendChild(image);
                        resultsList.appendChild(listItem);
                    });
                    resultsContainer.appendChild(resultsList);
                } else {
                    resultsContainer.textContent = 'No se encontraron resultados.';
                }

            } catch (error) {
                console.error('Error fetching search results:', error);
                searchStatus.textContent = 'Error al realizar la búsqueda.';
                resultsContainer.textContent = 'Ocurrió un error al obtener los resultados. Por favor, intente de nuevo más tarde.';
            } finally {
                setTimeout(() => {
                    searchStatus.textContent = '';
                }, 3000);
            }

        } else {
            searchStatus.textContent = 'Por favor, ingrese una consulta.';
            setTimeout(() => {
                searchStatus.textContent = '';
            }, 2000);
        }
    });
});