"""Static CAG few-shot estimation examples injected into the system prompt."""

from __future__ import annotations

from typing import TypedDict

_CAG_RULE = "=" * 72


class EstimationExample(TypedDict):
    """One prior estimation used as a CAG few-shot reference."""

    meeting_summary: str
    estimation: str


ESTIMATION_EXAMPLES: list[EstimationExample] = [
    {
        "meeting_summary": (
            "Cliente de e-commerce quiere un catálogo de productos con filtros "
            "por categoría y precio, carrito de compra, checkout con Stripe y "
            "panel admin básico para gestionar stock. Diseño no existe aún. "
            "Plazo deseado: 8 semanas. Equipo disponible: 1 frontend, 1 backend."
        ),
        "estimation": """
## Estimación: Catálogo e-commerce con checkout Stripe

### Alcance
MVP con catálogo filtrable, carrito, pago con Stripe y admin de stock.

### Desglose de tareas
| Tarea | Horas | Rol |
|---|---:|---|
| Diseño UI (wireframes + maquetas) | 24 | Designer |
| Setup proyecto (Next.js + API + CI) | 8 | Fullstack |
| Catálogo + filtros | 32 | Frontend |
| Carrito y estado de sesión | 16 | Frontend |
| Integración Stripe Checkout | 20 | Backend |
| Panel admin de stock (CRUD) | 24 | Fullstack |
| Auth admin | 8 | Backend |
| Tests + QA + despliegue | 16 | Fullstack |

### Equipo sugerido
- 1 Frontend (React/Next.js)
- 1 Backend (API + Stripe)
- 1 Designer (part-time, primeras 2 semanas)

### Totales
- **Horas:** ~148 h
- **Duración:** 7–8 semanas (2 personas a tiempo completo)
- **Coste orientativo:** 148 h × tarifa media equipo

### Riesgos
- Diseño desde cero puede retrasar el arranque
- Reglas fiscales/Stripe por país no definidas
""".strip(),
    },
    {
        "meeting_summary": (
            "Startup necesita una app móvil interna para que el equipo de campo "
            "registre visitas a clientes: formulario offline, sincronización al "
            "recuperar red, listado de visitas del día y exportación CSV. Solo "
            "iOS por ahora. Plazo: 6 semanas."
        ),
        "estimation": """
## Estimación: App móvil de registro de visitas (iOS)

### Alcance
App iOS con formularios offline-first, sync, listado diario y export CSV.

### Desglose de tareas
| Tarea | Horas | Rol |
|---|---:|---|
| Arquitectura offline + sync | 20 | Mobile |
| UI formularios de visita | 28 | Mobile |
| Cola local y reintentos | 16 | Mobile |
| API sync + autenticación | 24 | Backend |
| Listado del día + filtros | 12 | Mobile |
| Exportación CSV | 8 | Backend |
| Pruebas en campo + hardening | 16 | Mobile |

### Equipo sugerido
- 1 Mobile (Swift / React Native)
- 1 Backend (API sync)

### Totales
- **Horas:** ~124 h
- **Duración:** 5–6 semanas
- **Coste orientativo:** 124 h × tarifa media equipo

### Riesgos
- Conflictos de sync si dos dispositivos editan la misma visita
- Alcance Android explícitamente fuera de esta estimación
""".strip(),
    },
    {
        "meeting_summary": (
            "Empresa de formación quiere un portal de alumnos con login, listado "
            "de cursos, reproducción de vídeo (Vimeo), progreso por lección y "
            "certificado PDF al completar. Contenidos ya están en Vimeo. Plazo "
            "ideal: 5 semanas."
        ),
        "estimation": """
## Estimación: Portal de alumnos con certificados

### Alcance
Portal web con auth, cursos, player Vimeo, progreso y certificado PDF.

### Desglose de tareas
| Tarea | Horas | Rol |
|---|---:|---|
| Auth (email/password + roles) | 12 | Backend |
| Modelo cursos / lecciones | 10 | Backend |
| UI listado y detalle de curso | 18 | Frontend |
| Embed Vimeo + tracking progreso | 16 | Fullstack |
| Generación certificado PDF | 12 | Backend |
| Dashboard progreso alumno | 10 | Frontend |
| QA + despliegue | 10 | Fullstack |

### Equipo sugerido
- 1 Frontend
- 1 Backend

### Totales
- **Horas:** ~88 h
- **Duración:** 4–5 semanas
- **Coste orientativo:** 88 h × tarifa media equipo

### Riesgos
- Límites de la API de Vimeo (privacidad / domains)
- Plantilla legal del certificado no definida
""".strip(),
    },
    {
        "meeting_summary": (
            "Agencia de marketing pide una landing page con formulario de "
            "contacto, integración con HubSpot CRM, sección de blog con editor "
            "WYSIWYG y SEO básico. El diseño ya está en Figma. Plazo: 4 semanas. "
            "Un solo desarrollador fullstack disponible."
        ),
        "estimation": """
## Estimación: Landing + blog + HubSpot

### Alcance
Landing a partir de Figma, formulario → HubSpot, blog con WYSIWYG y SEO on-page.

### Desglose de tareas
| Tarea | Horas | Rol |
|---|---:|---|
| Maquetación landing desde Figma | 16 | Frontend |
| Formulario + validación + HubSpot | 12 | Fullstack |
| CMS/blog + editor WYSIWYG | 20 | Fullstack |
| SEO técnico (meta, sitemap, OG) | 6 | Frontend |
| Responsive + accesibilidad básica | 8 | Frontend |
| QA + despliegue (hosting + DNS) | 6 | Fullstack |

### Equipo sugerido
- 1 Fullstack

### Totales
- **Horas:** ~68 h
- **Duración:** 3–4 semanas (1 persona)
- **Coste orientativo:** 68 h × tarifa media

### Riesgos
- Cambios de diseño en Figma a mitad de sprint
- Límites/plan de HubSpot no confirmados
""".strip(),
    },
    {
        "meeting_summary": (
            "SaaS B2B quiere un dashboard de métricas: login con SSO (Google "
            "Workspace), gráficas de uso (DAU, retención, ingresos), filtros por "
            "rango de fechas y export a Excel. Datos llegan por API interna ya "
            "existente. Plazo: 6 semanas. Prioridad: desktop, no móvil."
        ),
        "estimation": """
## Estimación: Dashboard SaaS con SSO y export

### Alcance
Dashboard desktop con SSO Google, gráficas, filtros temporales y export Excel.

### Desglose de tareas
| Tarea | Horas | Rol |
|---|---:|---|
| SSO Google Workspace (OAuth) | 16 | Backend |
| Shell del dashboard + routing | 12 | Frontend |
| Integración API métricas | 16 | Fullstack |
| Gráficas (DAU, retención, ingresos) | 24 | Frontend |
| Filtros de fechas + estado URL | 10 | Frontend |
| Export Excel | 10 | Backend |
| Tests + QA + despliegue | 12 | Fullstack |

### Equipo sugerido
- 1 Frontend
- 1 Backend

### Totales
- **Horas:** ~100 h
- **Duración:** 5–6 semanas
- **Coste orientativo:** 100 h × tarifa media equipo

### Riesgos
- Latencia/paginación de la API interna no documentada
- Definición exacta de “retención” pendiente con producto
""".strip(),
    },
    {
        "meeting_summary": (
            "Clínica dental quiere un sistema de citas online: calendario "
            "público, reserva por paciente, recordatorios por email/SMS, panel "
            "para recepción y sincronización básica con Google Calendar. "
            "Multi-idioma ES/EN. Plazo deseado: 10 semanas."
        ),
        "estimation": """
## Estimación: Sistema de citas online (clínica)

### Alcance
Reservas públicas, panel recepción, recordatorios email/SMS, sync Google Calendar, i18n ES/EN.

### Desglose de tareas
| Tarea | Horas | Rol |
|---|---:|---|
| Modelo citas / disponibilidad / doctores | 20 | Backend |
| Calendario público + flujo de reserva | 28 | Frontend |
| Panel recepción (CRUD citas) | 24 | Fullstack |
| Auth pacientes y staff | 14 | Backend |
| Recordatorios email | 10 | Backend |
| Recordatorios SMS (Twilio u similar) | 12 | Backend |
| Sync Google Calendar | 16 | Backend |
| i18n ES/EN | 10 | Frontend |
| QA + despliegue + RGPD básico | 16 | Fullstack |

### Equipo sugerido
- 1 Frontend
- 1 Backend
- Apoyo part-time compliance/UX (opcional)

### Totales
- **Horas:** ~150 h
- **Duración:** 8–10 semanas
- **Coste orientativo:** 150 h × tarifa media equipo

### Riesgos
- Consentimiento y datos de salud (RGPD) no detallados
- Coste variable de SMS según volumen
""".strip(),
    },
    {
        "meeting_summary": (
            "Equipo interno pide un bot de Slack que, ante un mensaje con un "
            "enlace de ticket de Jira, resuma el ticket y sugiera el siguiente "
            "paso. Solo lectura de Jira, sin escribir. Deploy en su VPC. Plazo: "
            "3 semanas. Un backend senior disponible a media jornada."
        ),
        "estimation": """
## Estimación: Bot Slack → resumen de tickets Jira

### Alcance
Slash command / mención en Slack; lee Jira; resume y sugiere siguiente paso; deploy VPC.

### Desglose de tareas
| Tarea | Horas | Rol |
|---|---:|---|
| App Slack (events + OAuth) | 12 | Backend |
| Cliente Jira read-only | 8 | Backend |
| Prompt + llamada LLM (resumen) | 10 | Backend |
| Formato respuesta Slack (blocks) | 6 | Backend |
| Config secrets / deploy VPC | 10 | Backend |
| Hardening + logs + QA | 8 | Backend |

### Equipo sugerido
- 1 Backend senior (media jornada)

### Totales
- **Horas:** ~54 h
- **Duración:** 3 semanas (media jornada ≈ 20 h/semana)
- **Coste orientativo:** 54 h × tarifa senior

### Riesgos
- Permisos Jira/Slack del workspace corporativo
- Política interna sobre datos enviados al LLM
""".strip(),
    },
]


def _wrap_example(index: int, total: int, example: EstimationExample) -> str:
    """Wrap one example with explicit CAG begin/end markers.

    :arg index: 1-based example index.
    :arg total: Total number of examples in the CAG block.
    :arg example: Meeting summary and estimation pair.
    :return: Marked block ready for system-prompt injection.
    :raises: Does not raise under normal operation.
    """
    begin = (
        f"{_CAG_RULE}\n"
        f"CAG FEW-SHOT EXAMPLE {index}/{total}\n"
        f"Use this block only as a style/format reference for estimations.\n"
        f"{_CAG_RULE}"
    )
    end = (
        f"{_CAG_RULE}\n"
        f"END CAG FEW-SHOT EXAMPLE {index}/{total}\n"
        f"{_CAG_RULE}"
    )
    body = (
        f"## Meeting summary\n\n{example['meeting_summary'].strip()}\n\n"
        f"## Estimation\n\n{example['estimation'].strip()}"
    )
    return f"{begin}\n\n{body}\n\n{end}"


def load_cag_examples_markdown() -> str:
    """Join ``ESTIMATION_EXAMPLES`` into a delimited CAG context string.

    :return: Single Markdown string with labeled few-shot blocks for the
        system prompt.
    :raises ValueError: If fewer than two examples are defined.
    """
    examples = ESTIMATION_EXAMPLES
    if len(examples) < 2:
        raise ValueError(
            "ESTIMATION_EXAMPLES must contain at least two CAG few-shot examples"
        )

    total = len(examples)
    header = (
        f"{_CAG_RULE}\n"
        f"CAG STATIC CONTEXT - {total} few-shot estimation examples\n"
        f"Each block is delimited by BEGIN/END markers. Do not mix scopes.\n"
        f"{_CAG_RULE}\n"
    )
    blocks = [
        _wrap_example(i, total, example)
        for i, example in enumerate(examples, start=1)
    ]
    footer = (
        f"\n{_CAG_RULE}\n"
        f"END CAG STATIC CONTEXT\n"
        f"{_CAG_RULE}"
    )
    return header + "\n\n".join(blocks) + footer


__all__ = [
    "ESTIMATION_EXAMPLES",
    "EstimationExample",
    "load_cag_examples_markdown",
]
