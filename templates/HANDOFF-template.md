# Handoff: [plan-id]

- `status`: [pending | in_progress | blocked | completed]
- `phase`: [número]
- `task`: [N.M]
- `owner`: [agente o sesión]
- `branch`: [rama]
- `last_verified_commit`: [SHA]
- `updated_at`: [ISO-8601 UTC]
- `mode`: [single-agent | mixed | multi-agent]
- `models`: [selección de modelos por rol y estimación de tokens]

## Next action

[Una acción concreta que otro agente pueda ejecutar sin contexto adicional.]

## Blockers

- [bloqueo o `None`]

## Evidence

- Command: `[comando real]`
- Result: `[salida resumida real]`
- Coverage: `[porcentaje y alcance, o no aplica]`
- Security: `[estado y evidencia]`
- Regression: `[estado y evidencia]`
- Model budget: `[tokens reales/estimados por rol y modelo]`

## Completed

- [trabajo terminado]

## Failed approaches

- [intento fallido y por qué no repetirlo, o `None`]

## Decisions

- [decisión y motivo]
