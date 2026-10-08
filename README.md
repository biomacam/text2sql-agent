# Webinar Text2SQL

Este proyecto consiste en la creación de un aplicación para la consulta a bases de datos relacionales con un agente. Este agente está compuesto de tres procesos:
1. Creación de la query SQL según la consulta del usuario conocida la estructura de la base de datos.
2. Ejecución de query creada.
3. Devolución de la respuesta en lenguaje natural para un uso completamente conversacional con la base de datos.


## Estructura de carpetas

```plaintext
📦 webinar_text2sql
├── 📁 chatbot                                          # Código Text-to-SQL 
│   ├── 📄 __init__.py                                  # Convierte un directorio en un paquete
│   ├── 📄 chatclass.py                                 # Clase del agente text2sql 
│   └── 📄 prompts.py                                   # Prompts del sistema
│
├── 📁 images                                           # Carpeta con las imagenes usadas
│
├── 📁 notebooks                                        # Carpeta de notebooks de prueba
│   ├── 📁 src                                          # Carpeta de codigo del chat
│   │   └── 📄 chat.py                                  # Función del chatbot
│   ├── 📄 Consultor SQL OpenAI y Langchain.ipynb       # Jupyter notebook con el paso a paso
│   └── 📄 practicas.ipynb                              # Jupyter notebook con 10 preguntas de prueba
│
├── 📁 tools                                            # Herramientas 
│   ├── 📄 __init__.py                                  # Convierte un directorio en un paquete
│   └── 📄 tools.py                                     # Herramientas (logger)
│
├── 📄 .env.template                                    # Plantilla de archivo .env 
├── 📄 .gitignore                                       # Archivos y carpetas a ignorar en Git
├── 📄 .python-version                                  # Versión de python
├── 📄 front.py                                         # Archivo del frontend con chainlit
├── 📄 pyproject.toml                                   # Dependencias y configuración 
├── 📄 README.md                                        # Documentación principal del proyecto
├── 📄 requirements.txt                                 # Dependencias y configuración 
└── 📄 uv.lock                                          # Dependencias y configuración 
```

## Estructura de la base de datos
Usaremos la base de datos [sakila](https://dev.mysql.com/doc/sakila/en/sakila-installation.html), una base de datos de ejemplo que podemos descargar desde [aquí](https://github.com/YonatanRA/webinar_text2sql/raw/refs/heads/main/sakila_db/sakila.sql). Sus características son las siguientes:

+ Dominio del negocio: Videoclub (alquiler de películas).

+ Tamaño: Mediana complejidad, ideal para practicar consultas SQL reales.

+ Relaciones: Incluye múltiples relaciones entre tablas, ideal para practicar joins, subqueries, views y stored procedures.

+ Diagrama entidad-relación:
![erd](https://raw.githubusercontent.com/YonatanRA/webinar_text2sql/refs/heads/main/images/erd.png)



## Dependencias

1. **Instalación `uv`**:

   El método de instalación recomendado de `uv` es:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   De manera alternativa, podemos instalar `uv` via `pip`:

   ```bash
   pip install uv
   ```

   Para más detalles, revisar los [métodos de instalación](https://docs.astral.sh/uv/getting-started/installation/#installation-methods).



2. **Activación del entorno virtual**

    Activar el entorno virtual usado el siguiente comando:

    ```bash
    source .venv/bin/activate
    ```

    También puede usarse conda y crear un entorno virtual con:
     ```bash
    conda create -n sql python=3.11
    ```

3. **Sincronizar dependencias con uv**:

    ```bash
    uv sync
    ```

    Este comando instala las dependencias definidas en el archivo `pyproject.toml` con las mismas versiones especificadas en el archivo `uv.lock`.

4. **Sincronizar dependencias con pip**:

    ```bash
    pip install -r requirements.txt
    ```

    Este comando instala las dependencias en el entorno virtual definidas en el archivo `requirements.txt`. 

## Variables de entorno

Este proyecto necesita una base de datos SQL Server y acceso al agente FAB. Configura `URI`, `FAB_USER_ID`, `FAB_API_KEY` y `FAB_AGENT_URL` en `.env`; `.env.template` contiene ejemplos sin credenciales reales. Se recomienda usar un usuario de base de datos con permisos restringidos.

`URI = 'mssql+pyodbc://@localhost/A3ExportNominaClass?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes'`

`FAB_AGENT_URL = 'https://.../agent/sql-agent/execute'`

Para conectar con SQL Server es necesario tener instalado el [ODBC Driver 17 o 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) (driver del sistema, no es una dependencia de pip). Puede comprobarse con `Get-OdbcDriver` en PowerShell. Si se usa autenticación Windows, se mantiene `trusted_connection=yes` sin usuario/contraseña en la URI; para login SQL, usar `mssql+pyodbc://usuario:password@servidor/basedatos?driver=...`.




## Proceso de instalación y uso

1. Obtener URI de la base de datos de SQL y colocarla en el archivo `.env` (ejemplo en el archivo `.env.template`).


2. Instalar dependencias. Se puede usar el archivo `uv.lock` con el siguiente comando:
    ```bash
    uv sync
    ```
    También puede usarse el archivo `requirements.txt` usando el siguiente comando:
    ```bash
    pip install -r requirements.txt
    ```


3. Levantar el front de chainlit con el siguiente comando:
    ```bash
    chainlit run front.py -w --port 8001
    ```

## Arquitectura

No sigue ni Clean Architecture ni Arquitectura Hexagonal (puertos y adaptadores). Es una **arquitectura en capas simple (monolito de script)**, muy típica de un proyecto demo/webinar, con separación funcional ligera pero sin las fronteras formales que exigen esos patrones.

### Estructura real

```mermaid
graph TD
    A["front.py (presentación)<br/>Chainlit"] --> B["chatbot/chatclass.py<br/>Text2SQL (orquestación + lógica)"]
    B --> C["chatbot/prompts.py<br/>plantillas de prompt"]
    B --> D["LangChain / SQLDatabase<br/>(acceso a datos)"]
    B --> E["Agente FAB<br/>(generación SQL y respuesta)"]
    B --> F["tools/tools.py<br/>Logger"]
    D --> G[("SQL Server /<br/>A3ExportNominaClass")]
```

### Por qué no es Clean/Hexagonal

- **No hay inversión de dependencias real**: `Text2SQL` en `chatbot/chatclass.py` importa y usa directamente `create_engine`, `SQLDatabase` y `requests` para llamar al agente FAB — no hay interfaces/puertos abstractos que aíslen el dominio de SQLAlchemy, LangChain o el proveedor LLM.
- **No hay capa de dominio independiente**: no existen entidades/value objects ni casos de uso desacoplados de frameworks; todo vive en una única clase que mezcla reglas de negocio (reintentos, construcción de query, memoria conversacional) con detalles de infraestructura (engine, URI, LLM).
- **Configuración leída donde se usa**: `os.getenv('URI')` se lee directamente en el módulo `chatbot/chatclass.py`, no hay una capa de configuración/inyección de dependencias.
- **UI acoplada al caso de uso concreto**: `front.py` instancia `Text2SQL()` directamente y llama a `.main()`, sin ningún adaptador intermedio.

### Qué sí tiene (capas ligeras, no estrictas)

| Carpeta/archivo | Responsabilidad | Equivalente aproximado |
|---|---|---|
| `front.py` | Entrada/salida de usuario (Chainlit) | Capa de presentación |
| `chatbot/chatclass.py` | Orquestación del flujo (generar SQL → ejecutar → responder) | Capa de aplicación/servicio (mezclada con infraestructura) |
| `chatbot/prompts.py` | Plantillas de texto para el LLM | Configuración/recursos |
| `tools/tools.py` | Logger genérico | Utilidad transversal |

Es una separación por tipo de archivo/responsabilidad técnica, no por capas de arquitectura con reglas de dependencia (dominio no depende de infraestructura, etc.).
