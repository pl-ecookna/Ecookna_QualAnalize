export type FormulaGroupKey = "1k" | "2k" | "3k"

export type FormulaDetail = {
  formula: string
  total_thickness: number | null
}

export type SlipLookupResponse = {
  status: "success" | "not_found"
  message?: string
  width: number
  height: number
  width_round: number
  height_round: number
  marking: string | null
  formulas: Record<FormulaGroupKey, string[]>
  formula_details: Record<FormulaGroupKey, FormulaDetail[]>
}

export const formulaGroups: Array<{ key: FormulaGroupKey; title: string }> = [
  { key: "1k", title: "1-камерные" },
  { key: "2k", title: "2-камерные" },
  { key: "3k", title: "3-камерные" },
]

export const visibleFormulaGroups = formulaGroups.filter(({ key }) => key !== "3k")

export function splitMarkingLines(marking: string | null) {
  if (!marking) {
    return []
  }

  return marking
    .split(/\s+/)
    .map((part) => part.trim())
    .filter(Boolean)
}

export function formatFormulaWithThickness(formulaDetail: FormulaDetail) {
  return formulaDetail.total_thickness == null
    ? formulaDetail.formula
    : `${formulaDetail.formula} (${formulaDetail.total_thickness})`
}

export function formatSearchResultText(result: SlipLookupResponse | null, error: string | null) {
  if (error) {
    return `ПОДБОР ФОРМУЛЫ\nОшибка: ${error}`
  }

  if (!result) {
    return ""
  }

  const lines = [
    "ПОДБОР ФОРМУЛЫ",
    `Размер: ${result.width}x${result.height}`,
    `Округление: ${result.width_round}x${result.height_round}`,
  ]

  const markingLines = splitMarkingLines(result.marking)
  if (markingLines.length > 0) {
    lines.push("Формулы из таблицы слипания:")
    markingLines.forEach((line) => lines.push(line))
  }

  if (result.status === "not_found") {
    lines.push("Результат: правило в таблице слипания не найдено")
    return lines.join("\n")
  }

  lines.push("Результат: формулы найдены")

  visibleFormulaGroups.forEach(({ key, title }) => {
    const values = result.formula_details[key] || []
    if (values.length > 0) {
      lines.push(`${title}:`)
      values.forEach((formulaDetail) => lines.push(formatFormulaWithThickness(formulaDetail)))
    }
  })

  return lines.join("\n")
}
