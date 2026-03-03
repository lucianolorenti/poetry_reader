# Poetry URL Extractor Agent

## Description
Este agente extrae información de poesía desde una URL proporcionada y genera un archivo Markdown con el formato estándar del proyecto.

## Goal
Generar archivos `.md` con formato consistente para poemas extraídos de URLs, listos para ser procesados por el sistema de video.

## Output Format
El archivo generado debe seguir este formato exacto:

```
Titulo: [Título del poema]
Autor: [Nombre del autor]

[Contenido del poema, manteniendo los saltos de línea y estrofas]
```

## Workflow

### 1. URL Input
El usuario proporcionará una URL que contenga:
- El texto de un poema
- Información del autor
- Título del poema

### 2. Extraction
Extraer de la URL:
- **Título**: Buscar el título principal del poema
- **Autor**: Identificar el nombre del autor/poeta
- **Texto**: Capturar todo el contenido poético, preservando:
  - Saltos de línea entre versos
  - Estrofas separadas por líneas en blanco
  - Puntuación original

### 3. File Generation
Generar un archivo con:
- **Extensión**: `.md` (Markdown)
- **Ubicación**: Directorio `poemas/` en la raíz del proyecto
- **Nombre**: Usar slug del título (ej: `esta_tarde_mi_bien.md`)

### 4. Validation
Verificar que el archivo generado:
- Tenga las líneas `Titulo:` y `Autor:` al inicio
- Contenga el texto completo del poema
- Termine sin espacios extra al final

## Example Input/Output

### Input URL
`https://ejemplo.com/poemas/soneto-xvii-pablo-neruda`

### Output File: `poemas/soneto_xvii.md`
```markdown
Titulo: Soneto XVII
Autor: Pablo Neruda

No te amo como si fueras rosa de sal, topacio
o flecha de claveles que propagan el fuego:
te amo como se aman ciertas cosas oscuras,
secretamente, entre la sombra y el alma.

Te amo como la planta que no florece y lleva
 Dentro de sí, escondida, la luz de aquellas flores,
y gracias a tu amor vive oscuro en mi cuerpo
el aroma concentrado que ascendió de la tierra.

Te amo sin saber cómo, ni cuándo, ni de dónde,
te amo directamente sin problemas ni orgullo:
así te amo porque no sé amar de otra manera,

sino así de este modo en que no soy ni eres,
tan cerca que tu mano sobre mi pecho es mía,
tan cerca que se cierran tus ojos con mi sueño.
```

## Commands Available

```bash
# El agente procesará automáticamente cuando se proporcione una URL
# y generará el archivo .md correspondiente

# Para verificar el archivo generado:
cat poemas/[nombre_archivo].md

# Para listar todos los poemas disponibles:
ls poemas/*.md
```

## Notes
- Si la URL no tiene información clara de autor, usar "Anónimo" o "Autor Desconocido"
- Si el título no está claro, usar el título de la página web o "Sin título"
- Mantener el formato original del poema (acentos, puntuación, mayúsculas)
- No agregar comentarios ni metadatos adicionales al archivo
