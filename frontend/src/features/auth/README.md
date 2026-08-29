# Auth Feature

Provider-agnostic authentication boundary for the starter. Replace the fake session adapter with the project auth provider while keeping the public exports stable.

- Put session contracts in `types.ts`.
- Keep route UI in `components/`.
- Keep provider-specific calls in `api/`.
- Export only the intended public surface from `index.ts`.
