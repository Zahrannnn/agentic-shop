// Mirror of the backend catalog ids in `backend/app/catalog/data/headphones.json`.
// Regenerate this literal by hand whenever the backend catalog changes; the
// contract test (`validations/plan-schema.test.ts`) fs-reads the backend JSON
// and asserts both sources match exactly, so drift fails the frontend suite.

export const CATALOG_IDS: ReadonlySet<string> = new Set([
  "aurora-hush-pro",
  "cloudline-air",
  "skyline-hush",
  "volt-enduro-70",
  "pinegrove-bass-40",
  "pinegrove-day-50",
  "harbor-lite-anc",
  "kite-audio-street",
  "nimbus-go-anc",
  "tidalroom-studio-100",
  "coralfield-flex",
  "quartzbeat-sport",
  "emberwave-mid",
  "maple-ridge-comfort-150",
  "vesper-mini-anc",
  "driftwood-canyon",
  "cobalt-harbor-anc",
  "lumen-acoustics-air-3",
  "stratosound-one",
  "novastar-bass-x",
  "onward-travel-max",
  "velvetone-jazz-1",
  "bravenorth-arc",
  "heliostudio-pro-400",
  "summit-labs-aether",
  "obsidian-audio-flag-8",
  "cascadia-reference",
  "meridian-sound-lux",
  "pockettone-basis-29",
  "wavelet-core-buds",
  "aquabass-sport-2",
  "nimblepod-daily",
  "zenburst-hush",
  "pebble-hush-anc",
  "airglide-open-ear",
  "sonavista-pro-buds",
  "solstice-elite-anc",
  "lumenflow-studio-buds",
]);

// Name used by specs/002-frontend-ui-renderer/data-model.md for the same set.
export const CATALOG_PRODUCT_IDS: ReadonlySet<string> = CATALOG_IDS;

// Whitelist a `comparison_table` may reference for its columns: catalog spec
// attributes plus review-score dimensions.
export const KNOWN_ATTRIBUTES: readonly string[] = [
  "price_usd",
  "battery_hours",
  "weight_g",
  "anc_type",
  "driver_mm",
  "comfort",
  "anc",
  "sound",
  "battery",
  "value",
  "multipoint",
  "folding",
];
