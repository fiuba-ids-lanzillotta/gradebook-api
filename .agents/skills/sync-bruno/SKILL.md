---
name: sync-bruno
description: Keep the Bruno API collection in sync with the API's endpoints and request/response formats
allowed-tools:
  - read
  - edit
  - write
  - grep
  - glob
permissions:
  allow:
    - Read(**)
  ask:
    - Write(**)
---

Keep the Bruno collection in sync with the current API. Use this after adding/changing/removing
endpoints or changing request/response shapes.

## Reference the source of truth

1. Read `docs/swagger.yaml` and the routes in `gradebook_api/routes/` to get the current endpoints,
   methods, auth requirements, bodies and status codes.

## Update the collection

The Bruno collection lives in a separate repo:
`../../bruno-workspace/gradebook-api-collection`. For each change:

- **New endpoint** → add a `.bru` request in the matching folder (Auth / Items / ...), with method,
  URL (`{{protocol}}://{{host}}{{base_url}}/...`), headers, and an example body.
- **Admin endpoints** → set `auth: inherit` so the request uses the collection's Bearer token
  (`{{token}}`), populated by the **Auth > Login** request.
- **Changed body/format** → update the request body and any example to match the validated DTO
  (e.g. `items`: `nombre` required/unique, `descripcion` optional, `activo` boolean).
- **Removed endpoint** → delete the corresponding `.bru`.
- Keep environment variables (`protocol`, `host`, `base_url`, `token`, `api_key`) consistent across
  requests. The `X-API-Key` header lives at the collection level (`collection.bru`).

## Verify

- Every endpoint in `swagger.yaml` has a matching request in the collection, and there are no
  requests pointing to endpoints that no longer exist.
- Report which requests were added, changed, or removed.
