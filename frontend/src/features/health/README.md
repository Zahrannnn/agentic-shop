# Health Feature

Public backend health view for configured REST services.

- The UI can be public, but avoid secrets in labels or URLs.
- Route handler work belongs under `src/app/api`.
- Feature API code calls the route handler through TanStack Query.
