import { describe, expect, it } from "vitest";
import { getFileNameFromDisposition } from "./file-transfer";

describe("getFileNameFromDisposition", () => {
  it("returns undefined when disposition is missing", () => {
    expect(getFileNameFromDisposition(undefined)).toBeUndefined();
  });

  it("parses a quoted filename", () => {
    expect(getFileNameFromDisposition('attachment; filename="report.pdf"')).toBe(
      "report.pdf"
    );
  });

  it("parses an unquoted filename", () => {
    expect(getFileNameFromDisposition("attachment; filename=report.pdf")).toBe(
      "report.pdf"
    );
  });

  it("decodes UTF-8 encoded filenames", () => {
    expect(
      getFileNameFromDisposition("attachment; filename*=UTF-8''r%C3%A9sum%C3%A9.pdf")
    ).toBe("résumé.pdf");
  });

  it("returns undefined when no filename token is present", () => {
    expect(getFileNameFromDisposition("attachment")).toBeUndefined();
  });
});
