# Guía de uso — Budget Tracker

## 1. Descargar e instalar

1. Abre la app **Terminal** (Cmd+Espacio, escribe "Terminal", Enter).
2. Pega este comando completo y presiona Enter:

```
[ -d ~/Documents/budget-tracker ] || (mkdir -p ~/Documents && curl -fsSL https://github.com/vortizleon/budget-tracker/archive/refs/heads/main.tar.gz | tar -xz -C ~/Documents && mv ~/Documents/budget-tracker-main ~/Documents/budget-tracker); bash ~/Documents/budget-tracker/Instalar.command
```

Eso descarga la app a `Documents/budget-tracker` y corre el instalador.
Se usa Terminal (y no el ZIP del navegador) porque Mac bloquea los archivos
descargados desde el navegador; así no aparece ningún aviso de seguridad.

---

## 2. Qué esperar del instalador

- Trabaja solo. Instala `uv` (que baja Python) y los componentes de la app.
  **No pide contraseña, no necesita Homebrew ni las herramientas de Xcode, y
  no requiere actualizar macOS.** Todo es LOCAL en tu computadora.
- Al terminar, **se abre la app en tu navegador**. Si todavía no tienes tu
  archivo de Google (`.json`), no pasa nada: se consigue en la sección 3 y se
  sube desde la propia app (**Settings → Google credentials**).
- Es seguro volver a correr `Instalar.command` las veces que haga falta.

---

## 3. Consigue tu archivo de Google

Para leer tu Gmail la app necesita un archivo `.json` de Google. Hay dos
formas de conseguirlo. **Si conoces a quien te compartió la app, usa la
Opción A (2 minutos).**

### Opción A (recomendada): que quien te compartió la app te invite

1. Mándale por mensaje el correo de **Gmail donde recibes los avisos de tu
   banco**. Esa persona te agrega como "usuario de prueba" en su proyecto de
   Google.
2. Te va a mandar un archivo que se llama algo como
   `client_secret_123456.json`. Es **privado**: no lo compartas ni lo subas
   a ningún lado. Solo identifica a la app: **no da acceso a tu correo ni al
   de quien te lo mandó**. El acceso solo existe cuando tú inicias sesión y
   das permiso (sección 5), y queda guardado únicamente en tu computadora.
   Solo funciona con los correos que ya agregaron a la lista.
3. Abre la app (doble clic en **"Budget Tracker"** en tu Escritorio, o en
   `Abrir.command`), ve a **Settings → Google credentials** y **arrastra el
   archivo ahí** (o haz clic para elegirlo). No hace falta renombrarlo.
   *(Alternativa: guárdalo en la carpeta `Documents/budget-tracker` y haz
   doble clic en `Instalar.command`; la app lo detecta sola.)*
4. Pasa a la sección 4.
5. Cuando conectes Gmail (sección 5) Google va a mostrar una pantalla que
   dice **"Google no verificó esta app"** y **"solo continúa si conoces al
   desarrollador que te invitó"**. Es lo esperado: haz clic en **Avanzado**
   → **Ir a Budget Tracker (no seguro)** → **Permitir**.

Con esta opción **te saltas la Opción B**.

<details>
<summary><b>Opción B: crea tu propio proyecto de Google</b> (solo si nadie te puede invitar; toca para abrir)</summary>

Úsala si nadie te puede invitar. Toma unos 5 minutos y es gratis.

Aquí tú creas tu propio "proyecto" en Google Cloud: así nadie más está
involucrado en el acceso a tu correo.

Usa la cuenta de Gmail de donde quieres leer los correos del banco. Cada
enlace de abajo te lleva directo a la pantalla que necesitas (puede pedirte
iniciar sesión primero).

1. Crea el proyecto: entra a
   **https://console.cloud.google.com/projectcreate**
   - **Nombre del proyecto:** `Budget Tracker` (o el que quieras).
   - **Recurso superior / Ubicación:** déjalo en **Sin organización**.
   - Clic en **Crear**.

   Te lleva al panel de Google Cloud ("Vista general de Cloud"). **Ignora
   todo lo que aparece ahí**: el banner de "Comienza tu prueba gratuita" y
   el botón **Comenzar gratis** (no necesitas facturación ni tarjeta; Gmail
   API es gratis) y el aviso de "Cloud Hub". Solo confirma que arriba, junto
   al logo de Google Cloud, aparezca el nombre de tu proyecto. Si tienes
   más de un proyecto, revisa que sea ese y no otro.
2. Habilita Gmail API: con el proyecto seleccionado, entra a
   **https://console.cloud.google.com/apis/library/gmail.googleapis.com**
   y haz clic en el botón azul **Habilitar** (Enable). Espera unos segundos:
   cuando termine, la página "Detalles del servicio o la API" muestra
   **Estado: Habilitada**. **No** hagas clic todavía en el botón
   "Crear credenciales" que aparece arriba; primero va el paso 3.
3. Configura Google Auth Platform (antes llamada "pantalla de consentimiento
   de OAuth"): entra a **https://console.cloud.google.com/auth/overview** y
   haz clic en **Comenzar** (Get started). Es un asistente de 4 pantallas:
   - **Información de la app:** en "Nombre de la aplicación" escribe
     `Budget Tracker`. En "Correo electrónico de asistencia al usuario" es
     una lista desplegable: ábrela y elige tu correo (si lo dejas vacío
     marca error en rojo). Clic en **Siguiente**.

     ![Paso 1 del asistente: Información de la app](docs/img/google-auth-1-info-app.webp)
   - **Público:** elige **Usuarios externos** (no "Interno"; "Interno" solo
     sirve para cuentas de empresa/organización de Google). Dice que tu app
     "se iniciará en modo de prueba": es lo que queremos. Clic en
     **Siguiente**.

     ![Paso 2 del asistente: Público](docs/img/google-auth-2-publico.webp)
   - **Información de contacto:** escribe o elige tu correo (es donde Google
     te avisaría de cambios en el proyecto) → **Siguiente**.
   - **Finalizar:** marca la casilla de aceptar la política de datos de
     usuario de los servicios de las API de Google y guarda con
     **Continuar** / **Crear**.

   Cuando termine, ves la pantalla "Descripción general de OAuth" con un
   aviso azul abajo que dice **"Se creó la configuración de OAuth"**. Que
   diga "Aún no configuraste ningún cliente de OAuth" es normal, eso va en el
   paso 5.

   ![Configuración de OAuth creada](docs/img/google-auth-3-listo.webp)
4. Agrégate como usuario de prueba: en el menú de la izquierda, entra a
   **Público** (o ve a **https://console.cloud.google.com/auth/audience**).
   Arriba, **Estado de publicación** debe decir **Prueba** (Testing) y
   **Tipo de usuario** debe decir **Usuarios externos**: déjalos así (no
   hagas clic en "Publicar app" ni en "Marcar como interno"). Baja hasta
   **Usuarios de prueba** → **Add users** → escribe tu correo de Gmail →
   **Guardar**.
   - Puede salir un aviso **"No se agregaron cuentas no aptas"** aunque el
     correo sea válido. Clic en **Cerrar** y mira la lista de **Usuarios de
     prueba**: si tu correo aparece ahí, está bien y puedes seguir.
   - Si el correo **no** aparece en la lista, vuelve a intentarlo escribiéndolo
     todo en minúsculas.

   Si tu correo no está en esa lista, Google te bloquea más adelante con un
   error de "acceso no verificado".
5. Crea las credenciales: en el menú de la izquierda, entra a **Clientes**
   (Clients) (o ve a **https://console.cloud.google.com/auth/clients**) →
   **Crear cliente** (Create client).
   - Tipo de aplicación: **Aplicación de escritorio** (Desktop app).
   - Ponle el nombre que quieras → **Crear**.
   - No hace falta tocar "Acceso a los datos" (Data Access) ni agregar
     permisos: la app los pide sola al conectar Gmail.
6. Te va a aparecer una ventana con los datos de tu cliente — haz clic en
   **Descargar JSON**. (Si la cerraste: en **Clientes**, clic en el nombre
   del cliente que creaste → **Descargar JSON**.) Ese archivo es privado:
   no lo compartas ni lo subas a ningún lado.
7. Ve a tu carpeta de **Descargas** y busca ese archivo (algo como
   `client_secret_123456.json`). En la app, ve a **Settings → Google
   credentials** y **arrástralo ahí** (o haz clic para elegirlo). **No hace
   falta renombrarlo.**
8. Pasa a la sección 4.

> **Nota:** Google cambia estas pantallas de vez en cuando. Si algo no se ve
> igual, busca el equivalente por el nombre del botón. Los pasos siempre son:
> habilitar Gmail API → configurar la pantalla de consentimiento (Usuarios
> externos) → agregarte como usuario de prueba → crear un cliente de
> escritorio → descargar el JSON.

</details>

---

## 4. Agregar tus tarjetas (desde el navegador, sin Terminal)

El instalador crea solo, sin preguntarte nada, las categorías por defecto y
agrega los correos de BAC y Promerica desde donde la app ya sabe leer
transacciones — no tienes que saber de antemano cuáles son esas direcciones.
Después abre automáticamente el panel de la app en tu navegador
(`localhost:8000`).

Ahí te faltan dos cosas, ambas con clics normales, nada de Terminal:

**A. Agrega tus tarjetas.** Ve a la pestaña **Cards** (menú de la
izquierda) → **+ Add Card**, una vez por cada tarjeta que quieras rastrear:
- Nombre → el que quieras, ej. `BAC Visa`
- Últimos 4 dígitos de la tarjeta
- Tipo → Credit o Debit
- Banco → BAC o Promerica
- Si maneja colones y/o dólares, marca las casillas correspondientes
- Fecha de pago / límite de crédito son opcionales, déjalos en blanco si
  no los sabes de memoria

**B. (Opcional) ¿Bancos distintos a BAC o Promerica?** Ve a la pestaña
**Settings** → sección **Email Sources** → **+ Add Email Source**. Ahí
mismo te explica que lo que pides es la dirección *desde donde el banco te
manda* los avisos — no tu propio correo.

---

## 5. Primera sincronización

En la pestaña **Settings**, en la sección **Sync Status**, haz clic en el
botón **Sync Now**.

La primera vez se va a abrir tu navegador pidiéndote iniciar sesión con la
cuenta de Gmail que registraste en la sección 3, y dar permiso de **solo lectura**
sobre tu correo (la app nunca puede enviar correos ni borrar nada).

Vas a ver una pantalla de Google que dice algo como **"Google no verificó
esta app"**. Es normal — es tu propio proyecto, hecho solo para ti, y Google
muestra esa advertencia para cualquier app que no pasó su proceso de
verificación comercial. Haz clic en **Avanzado** → **Ir a Budget Tracker
(no seguro)** → **Permitir**.

Después de eso va a aparecer un mensaje en la esquina de la pantalla
diciendo cuántas transacciones nuevas encontró. ¡Ya está lista para usarse!

---

## 6. Uso del día a día

**Idioma:** la app está en español e inglés. El botón **EN | ES** (arriba a la izquierda, junto al ícono de modo oscuro) cambia el idioma y recuerda la elección.

**Abrir la app:** haz doble clic en **"Budget Tracker"** en tu Escritorio
(o en `Abrir.command` dentro de la carpeta de la app). No necesitas la
Terminal. Si reiniciaste la Mac, solo vuelve a abrirla así. La app corre
solo en tu computadora; nadie más en tu red puede entrar.

Todo lo normal se hace desde el navegador, en la pestaña **Settings**:

| Botón | Qué hace |
|---|---|
| **Sync Now** | Trae las transacciones nuevas de Gmail — hazlo 1 vez por semana |
| **Sync Range** (dentro de "Missing a gap?") | Trae transacciones de un rango de fechas específico, por si te saltaste un período |
| **Re-apply Rules** | Vuelve a clasificar transacciones "Uncategorized" después de agregar/editar una regla en Categories |
| **Reconnect Gmail** | Si dejó de sincronizar por un error de permisos, haz clic aquí y luego en "Sync Now" |

Una rutina razonable: **Sync Now** una vez por semana, y revisar la pestaña
**Analytics** los primeros días de cada mes para ver cómo te fue.

Dentro del panel del navegador también puedes:
- Agregar una transacción a mano (pestaña Transacciones → **+ Agregar transacción**): útil para compras en efectivo o de bancos que no envían correo. Si no se elige categoría, se asigna sola con las reglas de categorización o la categoría predeterminada de la tarjeta.
- Ver tus gastos del mes, por categoría y por comercio (pestaña Dashboard/Analytics).
- Asignar o corregir la categoría de cada transacción (pestaña Transactions).
- Ver tus tarjetas, cuentas y suscripciones.

**¿Prefieres la Terminal?** (Opcional; abre una Terminal *nueva* después de
instalar.) Todo lo de arriba también tiene su propio
comando — `finance-app sync`, `finance-app report`, `finance-app
refresh-oauth`, etc. Usa lo que te resulte más cómodo; ambos caminos hacen
exactamente lo mismo. Ver el `README.md` del proyecto para la lista
completa de comandos.

---

## Preguntas frecuentes

**"Mac dice que no puede abrir Instalar.command porque es de un desarrollador
no identificado"**
Clic derecho sobre el archivo → Abrir → confirmar Abrir. Solo pasa la
primera vez, y solo si bajaste el ZIP desde el navegador en vez de usar el comando de la
sección 1. Después de correr el instalador, `Abrir.command` y el acceso
directo del Escritorio ya no dan este aviso.

**El instalador falló al descargar `uv` o Python**
Revisa tu conexión a internet y vuelve a hacer doble clic en
`Instalar.command`; es seguro repetirlo, salta lo que ya está hecho. Si estás
en una red de trabajo o escuela, prueba con otra (a veces bloquean
`astral.sh` o `github.com`).

**No veo el acceso directo "Budget Tracker" en el Escritorio**
Mac a veces pide permiso para que Terminal escriba en el Escritorio. Si lo
negaste, usa `Abrir.command` dentro de la carpeta de la app (puedes arrastrarlo
al Dock). Para recuperar el permiso: Ajustes del Sistema → Privacidad y
seguridad → Archivos y carpetas → Terminal → Escritorio.

**El navegador no abre / "no se puede conectar a localhost:8000"**
Haz doble clic en `Abrir.command` otra vez. Si sigue sin funcionar, revisa
el archivo `.server.log` dentro de la carpeta de la app (ahí queda el
error) y mándaselo a quien te compartió la app. También puede ser que otro
programa esté usando el puerto 8000.

**Quiero actualizar a una versión nueva**
Haz doble clic en **`Actualizar.command`** (en la carpeta de la app). Baja la
última versión y la copia encima, **sin tocar tus datos** (tarjetas,
transacciones, `credentials.json`, `token.json`). Antes de actualizar guarda
una copia de tu base de datos en la carpeta `backups/`. Si la app estaba
abierta, la reinicia sola. También puedes correr `finance-app update` en la
Terminal.

**"Google dice que la app no está verificada / no es segura"**
Es normal y esperado: la app está en "modo de prueba" y solo pueden usarla
los correos agregados como "usuarios de prueba" (por quien te invitó, o por
ti en la Opción B). Clic en Avanzado → Ir a Budget Tracker → Permitir.

**"Access blocked" / "no tienes acceso" con la Opción A**
Tu correo no está en la lista de usuarios de prueba de quien te invitó, o
entraste con otra cuenta de Gmail. Confirma con esa persona que agregó
exactamente el correo con el que estás iniciando sesión.

**"Access blocked: this app's request is invalid"**
Tu correo no está en la lista de "usuarios de prueba". Con la Opción A, pídele
a quien te invitó que te agregue. Con la Opción B, entra a
https://console.cloud.google.com/auth/audience y agrégate en
"Usuarios de prueba" (paso 4).

**Dejó de sincronizar / dice que el token expiró** (puede pasar cada ~7 días)
Mientras el proyecto de Google esté en modo **Testing** (así debe quedar),
Google hace que el permiso caduque a los 7 días. No es un error
de la app. En Settings, clic en **Reconnect Gmail** y luego en **Sync Now**
para volver a autorizar el acceso. (O, por Terminal: `finance-app refresh-oauth`.)

**Las transacciones de un banco dejaron de aparecer bien**
A veces los bancos cambian el formato de sus correos. Avísale a quien te
compartió la app para que revise y actualice el programa.

**¿Es seguro? ¿Alguien más ve mis datos?**
Todo queda únicamente en tu computadora: el archivo `credentials.json`, el
permiso de Gmail y la base de datos con tus transacciones. La app no sube
nada a internet ni a ningún servidor — solo lee tu propio correo y guarda
todo localmente.
