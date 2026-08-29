#!/usr/bin/env node

import { mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";

const featureDirs = [
  "api",
  "components",
  "constants",
  "hooks",
  "utils",
  "validations",
];

function toKebabCase(value) {
  return value
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
}

async function askFeatureName() {
  const rl = readline.createInterface({ input, output });
  const answer = await rl.question("Feature name: ");
  rl.close();
  return answer;
}

async function createFeature(rawName) {
  const featureName = toKebabCase(rawName);

  if (!featureName) {
    throw new Error("Feature name is required.");
  }

  const featureRoot = path.join(process.cwd(), "src", "features", featureName);

  if (existsSync(featureRoot)) {
    throw new Error(`Feature already exists: src/features/${featureName}`);
  }

  await mkdir(featureRoot, { recursive: true });
  await Promise.all(
    featureDirs.map(async (dir) => {
      const dirPath = path.join(featureRoot, dir);
      await mkdir(dirPath, { recursive: true });
      await writeFile(path.join(dirPath, ".gitkeep"), "\n", "utf8");
    })
  );

  await writeFile(
    path.join(featureRoot, "README.md"),
    `# ${featureName} Feature\n\nOwns this feature's UI, hooks, API boundaries, constants, validations, utilities, and types.\n\n- Export the public surface from \`index.ts\`.\n- Keep components presentational.\n- Keep feature-local types in \`types.ts\`.\n- Replace \`.gitkeep\` files as folders gain real files.\n`,
    "utf8"
  );
  await writeFile(path.join(featureRoot, "types.ts"), "\n", "utf8");
  await writeFile(path.join(featureRoot, "index.ts"), "\n", "utf8");

  console.log(`Created src/features/${featureName}`);
  console.log("Next steps:");
  console.log("- Add public exports to index.ts");
  console.log("- Put presentational UI in components/");
  console.log("- Run npm run build before handing off");
}

async function main() {
  const [, , command, providedName] = process.argv;

  if (command !== "feature") {
    console.log("Usage: npm run corelia -- feature <name>");
    console.log("Run without <name> for an interactive prompt.");
    process.exit(command ? 1 : 0);
  }

  const featureName = providedName ?? (await askFeatureName());
  await createFeature(featureName);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
