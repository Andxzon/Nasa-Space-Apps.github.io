import json
import os
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv
import openai

# --- Configuración de API y Entorno ---
load_dotenv()
openai.api_key = os.getenv("API_KEY")

# --- Funciones de Soporte ---

def safe_get(obj: Dict[str, Any], key: str, default: str = "dato no disponible") -> str:
    """
    Obtiene un valor de un diccionario de forma segura.
    """
    value = obj.get(key)
    if value is None or value == "":
        return default
    return str(value)

def load_json(path_or_str: str) -> List[Dict[str, Any]]:
    """
    Carga datos JSON desde una ruta de archivo o un string.
    El JSON puede ser una lista de objetos o un objeto con una clave 'articles'
    que contenga la lista.
    """
    data = None
    if os.path.exists(path_or_str):
        try:
            with open(path_or_str, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            raise ValueError("Error: El archivo no contiene un JSON válido.")
        except FileNotFoundError:
            raise FileNotFoundError(f"Error: No se encontró el archivo en la ruta: {path_or_str}")
    else:
        try:
            data = json.loads(path_or_str)
        except json.JSONDecodeError:
            raise ValueError("Error: El string proporcionado no es un JSON válido.")

    # Si el JSON es un objeto con la clave 'articles', usamos esa lista
    if isinstance(data, dict) and 'articles' in data:
        if isinstance(data['articles'], list):
            return data['articles']
        else:
            raise TypeError("Error: La clave 'articles' debe contener una lista (array) de objetos.")
    
    if not isinstance(data, list):
        raise TypeError("Error: El JSON debe ser una lista (array) de objetos o un objeto con la clave 'articles'.")
    
    return data

# --- Funciones de IA y Lógica Principal ---

def generate_summaries_in_batch(items: List[Dict[str, Any]]) -> List[str]:
    """
    Genera resúmenes para un lote de ítems usando el LLM de OpenAI en una sola llamada.
    """
    if not items:
        return []

    # Construir el prompt para el lote
    item_prompts = []
    for i, item in enumerate(items):
        item_str = json.dumps(item, indent=2, ensure_ascii=False)
        item_prompts.append(f"\n--- Ítem {i+1} (ID: {item.get('id', 'N/A')}) ---\n{item_str}")
    
    full_prompt = "\n".join(item_prompts)

    system_prompt = (
        "A continuación se presentan varios ítems en formato JSON. "
        "Para cada ítem, genera un resumen objetivo en español de 1 a 2 oraciones. "
        "No inventes información ni añadas detalles que no estén presentes. "
        "Devuelve la respuesta como un único objeto JSON que contenga una clave 'resumenes' que sea un array de strings. "
        "Cada string en el array debe ser el resumen de un ítem, en el mismo orden en que fueron presentados. "
        "Asegúrate de que la salida sea solo el objeto JSON, sin texto adicional."
    )

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.2,
            max_tokens=len(items) * 150  # Estimar tokens necesarios
        )
        
        response_data = json.loads(response.choices[0].message.content)
        summaries = response_data.get("resumenes", [])

        if len(summaries) == len(items):
            return summaries
        else:
            print(f"\n[Advertencia] La IA devolvió {len(summaries)} resúmenes, pero se esperaban {len(items)}. Se usarán resúmenes vacíos.")
            return ["Resumen no disponible"] * len(items)

    except Exception as e:
        print(f"\n[Advertencia] No se pudo generar resumen con IA para el lote: {e}")
        return ["Resumen no pudo ser generado por la IA."] * len(items)

def search_items(data: List[Dict[str, Any]], criterio: str, campo_filtro: Optional[str]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Busca y filtra ítems en la lista de datos (artículos).
    """
    criterio_lower = criterio.lower()
    items_encontrados = []
    nota_filtro = None

    # Campos adaptados a la estructura de index.json
    campos_busqueda_amplia = ["title", "keywords", "topics"]
    
    if campo_filtro and data and campo_filtro not in data[0]:
        nota_filtro = f"campo_filtro '{campo_filtro}' no válido; se usó búsqueda amplia."
        campo_filtro = None

    for item in data:
        if campo_filtro:
            valor_campo = item.get(campo_filtro)
            if isinstance(valor_campo, list):
                # Manejar listas como 'keywords' o 'topics'
                if any(criterio_lower in str(sub_item).lower() for sub_item in valor_campo):
                    items_encontrados.append(item)
            elif valor_campo and criterio_lower in str(valor_campo).lower():
                items_encontrados.append(item)
        else:
            # Búsqueda amplia
            if criterio_lower in item.get("title", "").lower():
                items_encontrados.append(item)
                continue

            # Buscar en la lista de 'keywords' (que son dicts)
            if any(criterio_lower in kw.get("term", "").lower() for kw in item.get("keywords", [])):
                items_encontrados.append(item)
                continue

            # Buscar en la lista de 'topics' (que son strings)
            if any(criterio_lower in topic.lower() for topic in item.get("topics", [])):
                items_encontrados.append(item)
                continue
    
    # Eliminar duplicados si un ítem coincidió en múltiples campos
    items_sin_duplicados = []
    seen_ids = set()
    for item in items_encontrados:
        # Usar el 'id' del ítem para una deduplicación eficiente y segura
        item_id = item.get('id')
        if item_id is not None:
            if item_id not in seen_ids:
                items_sin_duplicados.append(item)
                seen_ids.add(item_id)
        else:
            # Fallback si no hay 'id': convertir el dict a un string para verificar duplicados
            # (menos eficiente pero seguro con tipos de datos no hashables como listas)
            item_str_representation = json.dumps(item, sort_keys=True)
            if item_str_representation not in seen_ids:
                items_sin_duplicados.append(item)
                seen_ids.add(item_str_representation)
    
    return items_sin_duplicados, nota_filtro

def summarize_items(items: List[Dict[str, Any]], max_items: int, criterios: Dict[str, Any], batch_size: int = 3) -> Tuple[str, Dict[str, Any]]:
    """
    Genera un resumen legible y un JSON estructurado, usando IA en lotes para el resumen breve.
    """
    items_a_resumir = items[:max_items]
    
    texto_legible = f"Resumen de {len(items_a_resumir)} resultados\n"
    texto_legible += "-" * 30 + "\n"
    
    if not items_a_resumir:
        texto_legible = "No se encontraron coincidencias."
        # Devuelve un diccionario vacío si no hay items
        return texto_legible, {}

    resumenes_para_json = []
    print(f"\nGenerando resúmenes con IA para {len(items_a_resumir)} ítems en lotes de {batch_size}... (esto puede tardar)")

    all_summaries = []
    for i in range(0, len(items_a_resumir), batch_size):
        lote = items_a_resumir[i:i + batch_size]
        print(f"Procesando lote {i//batch_size + 1}/{(len(items_a_resumir) + batch_size - 1)//batch_size}...")
        
        # --- Llamada a la IA para generar resúmenes en lote ---
        summaries_lote = generate_summaries_in_batch(lote)
        all_summaries.extend(summaries_lote)
        # -----------------------------------------------------

    for i, item in enumerate(items_a_resumir):
        item_id = safe_get(item, 'id')
        titulo = safe_get(item, 'title')
        fuente = safe_get(item, 'url')
        resumen_breve = all_summaries[i] if i < len(all_summaries) else "Resumen no generado."

        texto_legible += f"- ID: {item_id}\n"
        texto_legible += f"  Título: {titulo}\n"
        texto_legible += f"  Resumen (IA): {resumen_breve}\n"
        texto_legible += f"  Fuente: {fuente}\n\n"
        
        resumenes_para_json.append({
            "id": item_id,
            "titulo": titulo,
            "resumen_breve": resumen_breve,
            "fuente": fuente
        })

    tldr = "No se encontraron temas comunes."
    if items_a_resumir:
        all_topics = [topic for item in items_a_resumir for topic in item.get('topics', [])]
        if all_topics:
            topic_counts = {topic: all_topics.count(topic) for topic in set(all_topics)}
            most_common_topic = max(topic_counts, key=topic_counts.get)
            tldr = f"El tema más común en los resultados es '{most_common_topic}'."

    texto_legible += f"TL;DR: {tldr}"

    json_estructurado = {
        "criterios_utilizados": {
            "criterio_busqueda": criterios.get("criterio_busqueda"),
            "campo_filtro": criterios.get("campo_filtro") or "búsqueda amplia",
            "max_items_resueltos": len(items_a_resumir)
        },
        "total_encontrados": len(items),
        "items_resumidos": resumenes_para_json,
        "tldr": tldr
    }
    
    return texto_legible, json_estructurado

# --- Bloque Principal de Ejecución ---

def main():
    """
    Función principal que orquesta la ejecución del agente.
    """
    if not openai.api_key:
        print("Error: La variable de entorno API_KEY no está configurada.")
        print("Asegúrate de tener un archivo .env con API_KEY=tu-clave-de-openai")
        return

    print("--- Agente de Búsqueda y Resumen con IA ---")
    
    DEFAULT_JSON_PATH = 'index.json'

    try:
        datos = None
        # Intenta cargar el JSON por defecto del orquestador
        if os.path.exists(DEFAULT_JSON_PATH):
            print(f"Usando el archivo '{DEFAULT_JSON_PATH}' encontrado.")
            try:
                datos = load_json(DEFAULT_JSON_PATH)
            except (ValueError, TypeError) as e:
                print(f"Advertencia: No se pudo cargar '{DEFAULT_JSON_PATH}'. {e}")
        
        # Si no se cargaron datos, pide la ruta al usuario
        if datos is None:
            ruta_json = input("Introduce la ruta al archivo JSON de artículos: ")
            if not ruta_json:
                print("No se especificó un archivo JSON. Saliendo.")
                return
            datos = load_json(ruta_json)

        criterio = input("Criterio de búsqueda (ej: microgravity, bone, space medicine): ")
        if not criterio:
            print("El criterio de búsqueda no puede estar vacío.")
            return

        campo = input("Campo de filtro (opcional, ej: title, topics, keywords. Enter para omitir): ") or None
        max_items_str = input("Máximo de ítems a mostrar (opcional, por defecto 5): ")
        max_items = int(max_items_str) if max_items_str.isdigit() else 5

        items_encontrados, nota = search_items(datos, criterio, campo)
        
        if nota:
            print(f"\nAviso: {nota}\n")

        if not items_encontrados:
            print("\nNo se encontraron coincidencias. Aquí tienes algunas sugerencias:")
            print("1. Usa una palabra clave diferente o más general (en inglés).")
            print("2. Revisa la ortografía.")
            print("3. Omite el 'campo_filtro' para una búsqueda más amplia.")
            return

        criterios_usados = {"criterio_busqueda": criterio, "campo_filtro": campo, "max_items": max_items}
        texto, json_salida = summarize_items(items_encontrados, max_items, criterios_usados)

        print("\n" + "="*20 + " SALIDA LEGIBLE " + "="*20)
        print(texto)
        
        print("\n" + "="*20 + " SALIDA JSON " + "="*20)
        print(json.dumps(json_salida, indent=2, ensure_ascii=False))

    except (FileNotFoundError, ValueError, TypeError) as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nOcurrió un error inesperado: {e}")

if __name__ == "__main__":
    main()