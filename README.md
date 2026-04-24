# 🏃 Garmin Coach Bot

Bot de Telegram que actúa como entrenador personal de alto rendimiento,
usando tus datos de **Garmin Connect** y **Groq** como cerebro IA.

---

## 🗂 Estructura del proyecto

```
garmin-coach/
├── main.py            # Punto de entrada, scheduler
├── bot.py             # Bot de Telegram (comandos y conversación)
├── coach.py           # Motor IA con Claude API
├── garmin_sync.py     # Descarga datos de Garmin Connect
├── db.py              # Gestión TinyDB
├── pyproject.toml     # Dependencias y config (Poetry)
├── poetry.lock        # Lockfile generado por Poetry
├── Dockerfile
├── docker-compose.yml
├── .env.example       # Plantilla de variables de entorno
└── data/              # 📁 Generado automáticamente
    ├── garmin_coach.json    # Base de datos TinyDB
    └── logs/bot.log
```

---

## ⚙️ Configuración inicial

### 1. Clonar y preparar el entorno

```bash
git clone <tu-repo>
cd garmin-coach
cp .env.example .env
```

### 2. Instalar dependencias con Poetry

```bash
# Instalar Poetry si no lo tienes
curl -sSL https://install.python-poetry.org | python3 -

# Instalar dependencias del proyecto
poetry install

# Activar el entorno virtual
poetry shell
```

Para añadir o quitar dependencias:

```bash
poetry add <paquete>          # añadir dependencia
poetry add --group dev <paquete>  # añadir dependencia de desarrollo
poetry remove <paquete>       # eliminar dependencia
poetry update                 # actualizar todas las dependencias
```

### 2. Rellenar el fichero `.env`

```env
GARMIN_EMAIL=tu_email@ejemplo.com
GARMIN_PASSWORD=tu_password_garmin

TELEGRAM_BOT_TOKEN=      # De @BotFather en Telegram
TELEGRAM_ALLOWED_USER_ID= # Tu ID de Telegram (usa @userinfobot para saberlo)

GROQ_API_KEY=gsk-AKU...

SYNC_TIME_MORNING=07:00   # Hora del briefing de mañana
SYNC_TIME_EVENING=21:00   # Hora del briefing de noche

DAYS_HISTORY=30           # Cuántos días atrás sincronizar
```

### 3. Obtener tu Telegram User ID

1. Abre Telegram y busca **@userinfobot**
2. Escríbele `/start`
3. Te dará tu ID numérico — cópialo en `TELEGRAM_ALLOWED_USER_ID`

### 4. Crear el bot en Telegram

1. Abre **@BotFather** en Telegram
2. Escribe `/newbot` y sigue las instrucciones
3. Copia el token en `TELEGRAM_BOT_TOKEN`

---

## 🐳 Arrancar con Docker

> El `Dockerfile` usa Poetry internamente — no necesitas nada más que Docker.

```bash
# Construir y arrancar en background
docker-compose up -d --build

# Ver logs en tiempo real
docker-compose logs -f

# Parar
docker-compose down
```

> 💡 Si has actualizado dependencias localmente, haz `docker-compose build --no-cache` para que Docker recoja el `poetry.lock` actualizado.

---

## 💬 Comandos del bot

| Comando | Descripción |
|---------|-------------|
| `/start` | Muestra ayuda y comandos disponibles |
| `/sync` | Sincroniza datos de Garmin ahora mismo |
| `/status` | Muestra cuántos datos hay guardados |
| `/briefing` | Genera un análisis personalizado ahora |
| `/reset` | Reinicia la conversación con el coach |
| `/memoria <texto>` | Guarda una nota (lesiones, sensaciones...) |

### Conversación libre

Puedes escribir cualquier cosa:
- *"¿Cómo llevo la carga de entrenamiento esta semana?"*
- *"¿Debería entrenar hoy o descansar?"*
- *"Diseñame un plan para mejorar mi VO2max"*
- *"Ayer dormí mal, ¿cómo afecta a mi entrenamiento?"*

---

## 🔄 Sincronización automática

El bot sincroniza automáticamente a las horas que configures en `.env`:
- **Mañana**: Sync + briefing de recuperación y recomendación del día
- **Noche**: Sync + valoración del entrenamiento y plan para mañana

---

## 🧠 Memoria del coach

El coach recuerda:
- Notas guardadas con `/memoria`
- El historial de conversación de la sesión actual
- Todos los datos históricos de Garmin en la base de datos

Los datos de Garmin se usan **siempre desde la BD local** a no ser que hagas `/sync`.

---

## 🛠 Solución de problemas

### Error de autenticación en Garmin
Garmin Connect a veces requiere resolver un CAPTCHA la primera vez.
En ese caso, prueba a hacer login desde el navegador primero.

### El bot no responde
```bash
docker-compose logs garmin-coach | tail -50
```

### Borrar y recrear la base de datos
```bash
rm data/garmin_coach.json
docker-compose restart
```
