# Guía de uso — Budget Tracker

## 1. Descargar la app

1. Haz click aca para descargar el ZIP: https://github.com/vortizleon/budget-tracker/archive/refs/heads/main.zip
3. Busca el archivo `budget-tracker-main.zip` en tu carpeta de **Descargas**
   y haz doble clic para descomprimirlo.
4. Mueve la carpeta `budget-tracker-main` a donde prefieras tenerla de forma
   permanente (por ejemplo, tu carpeta de **Documentos**). Puedes renombrarla
   si quieres, por ejemplo a `budget-tracker`.

---

## 2. Ejecutar el instalador

1. Abre esa carpeta y busca el archivo **`Instalar.command`**.
2. Haz doble clic en él.
3. Si tu Mac muestra un aviso de que no puede abrirlo porque es de un
   "desarrollador no identificado" (es porque no soy ningun big corp): haz **clic derecho** sobre
   `Instalar.command` → **Abrir** → y confirma **Abrir** en la ventana que
   aparece. Esto solo hay que hacerlo la primera vez.
4. Se abre una ventana de Terminal y el instalador empieza a trabajar solo:
   instala lo que haga falta (puede pedirte tu contraseña de Mac — es
   normal, no se ve mientras escribes) y prepara la app.
5. En algún momento el instalador se va a detener y decirte que falta el
   archivo `credentials.json`. Es normal — eso es lo que haces en el
   siguiente paso. Deja esa ventana abierta o ciérrala, no pasa nada; cuando
   termines el paso 3 vuelves a hacer doble clic en `Instalar.command` y
   sigue donde quedó.

---

## 3. Configura tu proyecto de Google

Esta es la única parte que **cada persona tiene que hacer por su cuenta**.
Gmail no permite que una sola app lea el correo de varias personas distintas
sin que cada quien autorice su propio acceso — por eso cada quien necesita
su propio "proyecto" en Google Cloud. Toma unos 5 minutos y es gratis.

Usa la cuenta de Gmail de donde quieres leer los correos del banco. Cada
enlace de abajo te lleva directo a la pantalla que necesitas (puede pedirte
iniciar sesión primero).

1. Crea el proyecto: entra a
   **https://console.cloud.google.com/projectcreate**
   Ponle un nombre, por ejemplo `Budget Tracker`, y clic en **Crear**.
   Espera unos segundos y asegúrate de que ese proyecto quede seleccionado
   en el menú de arriba (si tienes más de un proyecto de Google, revisa que
   diga "Budget Tracker" y no otro).
2. Habilita Gmail API: con el proyecto ya seleccionado, entra a
   **https://console.cloud.google.com/apis/library/gmail.googleapis.com**
   y haz clic en **Habilitar**.
3. Configura la pantalla de consentimiento: entra a
   **https://console.cloud.google.com/apis/credentials/consent**
   - Tipo de usuario: **Externo** → Crear.
   - Nombre de la app: `Budget Tracker`. Correo de asistencia: el tuyo.
   - Más abajo, en datos de contacto del desarrollador, pon tu correo otra
     vez.
   - Clic en **Guardar y continuar** en cada pantalla que siga (en
     "Permisos"/Scopes no hace falta agregar nada) hasta terminar.
4. Agrégate como usuario de prueba: en esa misma pantalla de consentimiento
   (mismo enlace del paso 3), busca la sección **"Usuarios de prueba"**
   (Test users) → **Add users** → agrega tu propio correo de Gmail →
   Guardar.
   (Si te saltas este paso, Google te va a bloquear el acceso más adelante
   con un error de "acceso no verificado".)
5. Crea las credenciales: entra a
   **https://console.cloud.google.com/apis/credentials** → **Crear
   credenciales** (Create credentials) → **"ID de cliente de OAuth"** (OAuth
   client ID).
   - Tipo de aplicación: **Aplicación de escritorio** (Desktop app).
   - Ponle el nombre que quieras → **Crear**.
6. Te va a aparecer una ventana con tus datos — haz clic en **Descargar
   JSON**.
7. Ve a tu carpeta de **Descargas** y busca ese archivo (algo como
   `client_secret_123456.json`):
   - Renómbralo a exactamente: **`credentials.json`**
   - Muévelo a la carpeta de la app, justo al lado de `Instalar.command`.
8. Vuelve al paso 2 de esta guía: haz doble clic en **`Instalar.command`**
   otra vez.

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
cuenta de Gmail que usaste en el paso 3, y dar permiso de **solo lectura**
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
- Ver tus gastos del mes, por categoría y por comercio (pestaña Dashboard/Analytics).
- Asignar o corregir la categoría de cada transacción (pestaña Transactions).
- Ver tus tarjetas, cuentas y suscripciones.

**¿Prefieres la Terminal?** Todo lo de arriba también tiene su propio
comando — `finance-app sync`, `finance-app report`, `finance-app
refresh-oauth`, etc. Usa lo que te resulte más cómodo; ambos caminos hacen
exactamente lo mismo. Ver el `README.md` del proyecto para la lista
completa de comandos.

---

## Preguntas frecuentes

**"Mac dice que no puede abrir Instalar.command porque es de un desarrollador
no identificado"**
Clic derecho sobre el archivo → Abrir → confirmar Abrir. Solo pasa la
primera vez.

**"Google dice que la app no está verificada / no es segura"**
Es normal y esperado — hiciste tu propio proyecto solo para ti en el paso 3,
y solo tú (como "usuario de prueba") puedes usarlo. Clic en Avanzado →
continuar.

**"Access blocked: this app's request is invalid"**
Te faltó agregarte como "usuario de prueba" en el paso 4 de la sección
"Configura tu proyecto de Google". Entra a
https://console.cloud.google.com/apis/credentials/consent y agrégate en
"Usuarios de prueba".

**Dejó de sincronizar / dice que el token expiró**
En Settings, clic en **Reconnect Gmail** y luego en **Sync Now** para volver
a autorizar el acceso. (O, por Terminal: `finance-app refresh-oauth`.)

**Las transacciones de un banco dejaron de aparecer bien**
A veces los bancos cambian el formato de sus correos. Avísale a quien te
compartió la app para que revise y actualice el programa.

**¿Es seguro? ¿Alguien más ve mis datos?**
Todo queda únicamente en tu computadora: el archivo `credentials.json`, el
permiso de Gmail y la base de datos con tus transacciones. La app no sube
nada a internet ni a ningún servidor — solo lee tu propio correo y guarda
todo localmente.
