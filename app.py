from flask import Flask, request, jsonify
from flask_cors import CORS
from main import load_json, search_items, summarize_items

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    try:
        datos = load_json('index.json')
        items_encontrados, nota = search_items(datos, query, None)

        if nota:
            print(f"Aviso: {nota}")

        if not items_encontrados:
            return jsonify([])

        criterios_usados = {"criterio_busqueda": query, "campo_filtro": None, "max_items": 5}
        texto, json_salida = summarize_items(items_encontrados, 5, criterios_usados)

        # The script.js is expecting a list of objects with title, summary and link
        # The summarize_items function returns a different format, so we need to adapt it.
        results = []
        if 'items_resumidos' in json_salida:
            for item in json_salida['items_resumidos']:
                results.append({
                    'title': item.get('titulo'),
                    'summary': item.get('resumen_breve'),
                    'link': item.get('fuente')
                })

        return jsonify(results)

    except Exception as e:
        print(f"Error during search: {e}")
        return jsonify({'error': 'An error occurred during the search.'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
