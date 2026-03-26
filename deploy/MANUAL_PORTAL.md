# Greybark Research — Manual del Portal de Clientes

## Acceso al Portal

**URL:** `http://87.99.133.124`

### Iniciar Sesion

1. Abrir el enlace del portal en el navegador
2. Ingresar el **ID de cliente** (ejemplo: `mbi`, `vantrust`, `bvc`)
3. Ingresar la **contrasena** asignada
4. Hacer click en **"Ingresar"**

La sesion dura **8 horas**. Despues de ese tiempo, sera necesario ingresar nuevamente.

---

## Navegacion Principal

Una vez autenticado, la barra de navegacion superior muestra las siguientes secciones:

| Seccion           | Ruta             | Descripcion                              |
|-------------------|------------------|------------------------------------------|
| **Dashboard**     | `/`              | Panel principal con estadisticas         |
| **Pipeline**      | `/pipeline`      | Ejecutar el AI Council mensual           |
| **Daily**         | `/daily`         | Generar reportes diarios AM/PM           |
| **Reportes**      | `/reports`       | Galeria de todos los reportes            |
| **Historico**     | `/historico`     | Archivo de reportes agrupados por fecha  |
| **Config**        | `/settings`      | Configuracion de branding y prompts IA   |
| **Estado**        | `/system-status` | Verificacion de APIs y estado del sistema|

Para cerrar sesion, hacer click en **"Salir"** (esquina superior derecha).

---

## 1. Dashboard (Panel Principal)

El dashboard es la pagina de inicio despues del login. Muestra:

### Estadisticas de Uso

Cuatro tarjetas con el conteo acumulado de:
- Reportes Daily AM generados
- Reportes Daily PM generados
- Sesiones de AI Council ejecutadas
- Podcasts generados

### Accesos Rapidos

Iconos que llevan directamente a cada seccion del portal. Solo aparecen las opciones contratadas por el cliente.

### Generar Reporte Rapido

Si el cliente tiene contratado el AI Council, puede lanzar una ejecucion rapida directamente desde el dashboard:

1. Escribir directivas opcionales en el campo de texto (ejemplo: "Enfoque en renta fija local, horizonte 6 meses")
2. Hacer click en **"Generar reporte"**
3. Se redirige automaticamente a la pagina de estado para seguir el progreso

Para mayor control sobre la ejecucion (seleccionar reportes especificos, subir articulos, etc.), usar el link **"Pipeline completo"**.

### Reportes Recientes

Tabla con los ultimos 5 reportes generados. Cada reporte tiene botones para **Ver** (abre en el portal) y **Descargar** (descarga el archivo HTML).

### Ejecuciones Recientes

Tabla con los ultimos jobs ejecutados, mostrando producto, estado y fecha.

---

## 2. Pipeline (AI Council Mensual)

Esta es la pagina principal para configurar y ejecutar el pipeline completo del AI Council. Se divide en dos columnas.

### Columna Izquierda

#### Archivos de Research

Aqui se suben documentos (PDFs, TXT, MD) que seran leidos por los agentes del AI Council como contexto adicional.

**Para subir archivos:**
1. Arrastrar archivos sobre la zona de carga, o hacer click para seleccionarlos
2. Formatos aceptados: PDF, TXT, MD (maximo 50 MB por archivo)
3. Hacer click en **"Subir archivos"**

Los archivos subidos aparecen en la lista inferior. Para eliminar un archivo, hacer click en el boton **X** junto a su nombre.

#### Directivas del Comite

Campo de texto libre donde se escriben instrucciones que seran leidas por **todos** los agentes del AI Council.

Ejemplos de directivas:
- "Foco en impacto de aranceles en Chile"
- "Creo que BCCh mantiene TPM"
- "Hay valor en Europa?"
- "Me preocupa la valorizacion de tech en USA, evaluar sostenibilidad de earnings"
- "Ponderar riesgo geopolitico Iran-USA"

Hacer click en **"Guardar directivas"** para persistir los cambios.

> **Importante:** Las directivas son **independientes por cliente**. Lo que escriba MBI no afecta a Vantrust ni a BVC. Cada cliente tiene su propio archivo de directivas.

### Columna Derecha

#### Configuracion del Pipeline

**Reportes a generar:** Seleccionar que reportes producir:
- **Macro** — Reporte macroeconomico global
- **Renta Variable** — Analisis de mercados accionarios
- **Renta Fija** — Analisis de tasas y credito
- **Asset Allocation** — Asignacion de activos y modelo de cartera

Por defecto se generan Macro, RV y RF. Asset Allocation es opcional.

**Opciones adicionales:**
- **Dry Run** — Solo recopila datos sin ejecutar el council (util para verificar disponibilidad de datos)
- **Saltar recopilacion** — Usa datos previamente recopilados (ahorra tiempo si los datos ya estan frescos)

#### Ejecutar

Hacer click en **"Ejecutar Pipeline"** para iniciar. Se redirige a la pagina de estado.

> El boton se desactiva automaticamente despues de hacer click para evitar ejecuciones duplicadas.

---

## 3. Daily (Reporte Diario)

Genera reportes de mercado diarios con opcion de podcast y envio por email.

### Configuracion

**Periodo:**
- **AM (Matutino)** — Reporte de apertura de mercados
- **PM (Vespertino)** — Reporte de cierre

Solo aparecen los periodos contratados.

**Opciones:**
- **Generar podcast** — Crea un archivo de audio MP3 con el resumen del reporte (activado por defecto si esta contratado)
- **Enviar por email** — Envia el reporte a los destinatarios configurados
- **Saltar recopilacion** — Reutiliza datos existentes
- **Dry Run** — Simulacion sin llamar APIs

Hacer click en **"Generar Reporte"** para iniciar.

### Reportes Diarios Recientes

Tabla con los ultimos reportes diarios generados, con opciones para ver y descargar.

---

## 4. Estado de Ejecucion

Cuando se lanza un pipeline (mensual o diario), se muestra esta pagina con seguimiento en tiempo real.

### Elementos de la Pagina

**Barra de progreso:** Avanza de 0% a 100% conforme avanzan las fases.

**Fases del pipeline mensual:**
1. Recopilacion de datos
2. Preflight check
3. Intelligence Briefing
4. AI Council (sesion principal)
5. Generacion de reportes
6. Resumen

**Fases del pipeline diario:**
1. Recopilacion de datos
2. Generacion de reporte
3. Formato HTML
4. Podcast
5. Email

Cada fase muestra un icono de estado:
- ⬜ Pendiente
- 🔄 En progreso
- ✅ Completada
- ❌ Error

**Log completo:** Secccion expandible que muestra la salida del proceso en tiempo real.

### Al Completar

- **Exito:** Aparecen botones para "Ver reportes" e ir al dashboard
- **Error:** Aparece el mensaje de error con opcion de "Reintentar"

> La pagina se actualiza automaticamente cada 2 segundos. No es necesario recargar manualmente.

---

## 5. Reportes

Galeria de todos los reportes HTML generados, ordenados por fecha de creacion (mas reciente primero).

Cada tarjeta muestra:
- Nombre del archivo
- Fecha y hora de generacion
- Tamano del archivo
- Carpeta de origen

**Acciones por reporte:**
- **Ver** — Abre el reporte embebido dentro del portal
- **Descargar** — Descarga el archivo HTML al computador

### Visor de Reportes

Al hacer click en "Ver", el reporte se muestra dentro de un marco (iframe) con una barra de herramientas:

- **← Reportes** — Volver a la galeria
- **Abrir en nueva ventana** — Abre el HTML puro en una pestana nueva
- **Descargar** — Descarga el archivo

---

## 6. Historico

Archivo completo de reportes agrupados por fecha.

### Contenido

- **Estadisticas de uso** — Mismas tarjetas del dashboard
- **Reportes por fecha** — Agrupados en secciones colapsables por dia
- **Council Sessions** — Tabla con sesiones del AI Council ejecutadas (estado, duracion, archivo)
- **Jobs Recientes** — Historial de ejecuciones

Cada reporte muestra un icono segun su tipo:
- 🌍 Macro
- 📈 Renta Variable
- 📉 Renta Fija
- 📊 Asset Allocation
- 🔍 Intelligence Briefing
- 📊 Daily

---

## 7. Configuracion

Permite personalizar la apariencia de los reportes y el comportamiento de los agentes IA.

### Branding (Columna Izquierda)

#### Logo
- **Subir logo:** Click en "Subir", seleccionar archivo PNG, JPG o SVG (maximo 2 MB)
- **Eliminar logo:** Click en "Eliminar logo" debajo de la vista previa

#### Colores
- **Color primario** — Color principal de headers y titulos (selector de color)
- **Color acento** — Color de destacados, lineas y fechas (selector de color)

#### Tipografia
- Seleccionar familia de fuente del menu desplegable (Georgia, Segoe UI, Arial, Times New Roman, Helvetica, Verdana, Roboto, Open Sans)

#### Texto de Footer
- Texto que aparece al pie de los reportes (ejemplo: "Powered by MBI Research")

#### Avanzado
- **HTML header de emails** — Codigo HTML personalizado para el encabezado de emails enviados

Hacer click en **"Guardar branding"** para aplicar los cambios.

### AI Prompts (Columna Izquierda, segunda seccion)

Estos campos modifican el comportamiento de los agentes del AI Council:

| Campo                    | Efecto                                              | Ejemplo                                    |
|--------------------------|-----------------------------------------------------|--------------------------------------------|
| **Tono**                 | Estilo de comunicacion de los reportes              | "Formal y conservador"                     |
| **Audiencia**            | A quien van dirigidos los reportes                  | "Directorio y gerencia"                    |
| **Foco tematico**        | Area de enfasis principal                           | "Renta fija Chile"                         |
| **Instrucciones custom** | Indicaciones adicionales para todos los agentes     | "Siempre incluir comparacion con LatAm"    |
| **Intro podcast**        | Texto de apertura del podcast                       | "Buenos dias, bienvenidos al reporte..."   |
| **Outro podcast**        | Texto de cierre del podcast                         | "Esto fue el reporte de MBI Research..."   |
| **Disclaimer**           | Texto legal al final de los reportes                | "Este reporte es solo para uso interno..." |

Hacer click en **"Guardar prompts"** para aplicar.

### Vista Previa (Columna Derecha)

Panel en vivo que muestra como se veran los reportes con la configuracion actual. Los cambios de color, fuente y footer se reflejan inmediatamente al moverlos.

---

## 8. Estado del Sistema

Pagina de diagnostico que verifica la salud del sistema.

### Fuentes de Datos y Dependencias

Lista de verificacion con estado de:

| Check                | Que verifica                          |
|----------------------|---------------------------------------|
| Anthropic API Key    | Clave para Claude (Council + Research)|
| FRED API Key         | Datos macroeconomicos USA             |
| BCCh API             | Datos macroeconomicos Chile           |
| AlphaVantage API     | Earnings, factores, sentimiento       |
| Platform DB          | Conexion a base de datos SQLite       |
| Python: anthropic    | Libreria Anthropic instalada          |
| Python: yfinance     | Libreria Yahoo Finance instalada      |
| Python: pdfplumber   | Libreria PDF instalada                |
| Python: pandas       | Libreria Pandas instalada             |
| Python: matplotlib   | Libreria Matplotlib instalada         |

Cada check muestra ✅ (ok) o ❌ (error) con detalle.

### Espacio en Disco

Uso de disco de las carpetas clave:
- `output/council/` — Archivos de sesiones del AI Council
- `output/reports/` — Reportes HTML generados
- `input/research/` — Archivos de investigacion subidos

---

## Preguntas Frecuentes

**¿Cuanto tarda el pipeline mensual?**

| Modo | Tiempo aproximado |
|------|-------------------|
| Completo (recopilacion + council + 4 reportes) | 35-50 minutos |
| Sin recopilacion (skip collect + 4 reportes) | 15-35 minutos |
| Dry run (solo recopilacion) | 10-15 minutos |

**¿Que reportes se generan?**

| Reporte | Contenido | Charts | Paginas aprox. |
|---------|-----------|--------|----------------|
| **Macro** | USA, Europa, China, Chile/LatAm, commodities, tasas | 29 | 25-30 |
| **Renta Variable** | Valuaciones, sectores, factores, earnings, flujos | 12 | 15-20 |
| **Renta Fija** | Duration, credito IG/HY, EM debt, Chile soberano | 8 | 12-15 |
| **Asset Allocation** | 5 portafolios modelo, escenarios, views regionales | 0 (tablas) | 10-12 |
| **Intelligence Briefing** | Datos verificados, charts macro, contexto pre-council | 44 | 15-20 |

**¿Puedo ejecutar multiples pipelines a la vez?**
Si, cada ejecucion genera un job independiente con su propio ID. Sin embargo, ejecutar multiples pipelines simultaneos consume mas creditos de API.

**¿Que pasa si el pipeline falla?**
La pagina de estado mostrara el error y la fase donde fallo. Los reportes que SI se generaron correctamente se copian automaticamente a la carpeta del cliente — no se pierden. Puede reintentar desde la pagina de pipeline.

**¿Los cambios de branding afectan reportes ya generados?**
No. Los cambios de branding solo afectan reportes generados despues de guardar la configuracion. Los reportes existentes mantienen el branding con el que fueron creados.

**¿Las directivas de un cliente afectan a otro?**
No. Cada cliente tiene sus propias directivas independientes. Lo que escriba MBI no afecta a Vantrust ni a BVC.

**¿Como cambio mi contrasena?**
Contacte al administrador del sistema para actualizar la contrasena.

**¿Como descargo el podcast?**
Los podcasts aparecen junto a los reportes diarios. Busque archivos `.mp3` en la seccion de reportes o en el historico del dia correspondiente.

---

## Flujo Recomendado

### Primera vez (demo)
```
1. Ingresar al portal
2. Ir a Config → subir logo, ajustar colores y nombre de empresa
3. Ir a Pipeline → escribir directivas especificas
4. Seleccionar los 4 reportes (Macro + RV + RF + AA)
5. Ejecutar Pipeline → esperar ~40 minutos
6. Ver reportes en la seccion Reportes
```

### Ejecuciones posteriores
```
1. Ir a Pipeline → ajustar directivas si es necesario
2. Marcar "Saltar recopilacion" si los datos son del mismo dia
3. Ejecutar → ~20 minutos
```
