import test from "node:test"
import assert from "node:assert/strict"

import { formatSearchResultText } from "../src/lib/slip-report.ts"

test("formatSearchResultText includes thickness in copied report", () => {
  const text = formatSearchResultText(
    {
      status: "success",
      width: 2500,
      height: 1500,
      width_round: 2500,
      height_round: 1500,
      marking: "8-14-8 6-16-6-14-6",
      formulas: {
        "1k": ["8-14-8"],
        "2k": ["6-16-6-14-6"],
        "3k": [],
      },
      formula_details: {
        "1k": [{ formula: "8-14-8", total_thickness: 16 }],
        "2k": [{ formula: "6-16-6-14-6", total_thickness: 18 }],
        "3k": [],
      },
    },
    null,
  )

  assert.match(text, /8-14-8 \(16\)/)
  assert.match(text, /6-16-6-14-6 \(18\)/)
})

test("formatSearchResultText skips thickness suffix when it is missing", () => {
  const text = formatSearchResultText(
    {
      status: "success",
      width: 1200,
      height: 1000,
      width_round: 1200,
      height_round: 1000,
      marking: null,
      formulas: {
        "1k": ["4-16-4"],
        "2k": [],
        "3k": [],
      },
      formula_details: {
        "1k": [{ formula: "4-16-4", total_thickness: null }],
        "2k": [],
        "3k": [],
      },
    },
    null,
  )

  assert.match(text, /4-16-4/)
  assert.doesNotMatch(text, /4-16-4 \(/)
})
