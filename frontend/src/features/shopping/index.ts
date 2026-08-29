// Public API of the shopping feature. Consumers (routes, other features)
// import from this barrel only.
export {
  CATALOG_IDS,
  CATALOG_PRODUCT_IDS,
  KNOWN_ATTRIBUTES,
} from "./utils/catalog-refs";
export {
  PLAN_COMPONENT_TYPES,
  parseUiPlan,
  planActionSchema,
  planComponentSchema,
  uiPlanSchema,
  validateProductRefs,
} from "./validations/plan-schema";
export type {
  CartLine,
  CartViewProps,
  ComparisonTableProps,
  ParseUiPlanResult,
  PlanAction,
  PlanComponent,
  PlanComponentType,
  PreferencePickerProps,
  ProductDetailsProps,
  ProductGridProps,
  TextBlockProps,
  UIAction,
  UiPlan,
} from "./validations/plan-schema";
export {
  markSessionLive,
  resetSessionExpired,
  selectSessionId,
  sessionSlice,
  startNewSession,
  type SessionState,
} from "./store/session-slice";
export {
  STAGE_ORDER,
  deltaAppended,
  phaseSetIdle,
  planInvalid,
  planReceived,
  selectCurrentTurn,
  selectIsBusy,
  selectPhase,
  selectTurns,
  stageProgress,
  stageSeen,
  transcriptCleared,
  transcriptSlice,
  turnEnded,
  turnFailed,
  turnProse,
  turnStarted,
  type SentAction,
  type Stage,
  type TerminalOutcome,
  type TranscriptPhase,
  type TranscriptState,
  type Turn,
} from "./store/transcript-slice";
export { ShopPage } from "./components/shop-page";
