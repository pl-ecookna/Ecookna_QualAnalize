import { useRef, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  Copy,
  FileSearch,
  FileUp,
  Info,
  LoaderCircle,
  OctagonAlert,
  TriangleAlert,
  ScanSearch,
  Search,
} from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import ecooknaGroupLogo from "@/assets/ecookna-group.png"
import heroQaIllustration from "@/assets/kaleva-hero.png"

type SlipLookupResponse = {
  status: "success" | "not_found"
  message?: string
  width: number
  height: number
  width_round: number
  height_round: number
  marking: string | null
  formulas: Record<"1k" | "2k" | "3k", string[]>
}

type PdfReportItem = {
  pos_num: string
  size: string
  formula: string
  is_outside: boolean
  errors: string[]
  raskl?: string | null
}

type PdfCheckResponse = {
  status: "success" | "warning" | "issues_found"
  message?: string
  file_name: string
  total_items: number
  issues_count: number
  report_data: PdfReportItem[]
}

const formulaGroups: Array<{ key: "1k" | "2k" | "3k"; title: string }> = [
  { key: "1k", title: "1-камерные" },
  { key: "2k", title: "2-камерные" },
  { key: "3k", title: "3-камерные" },
]

const visibleFormulaGroups = formulaGroups.filter(({ key }) => key !== "3k")

function splitMarkingLines(marking: string | null) {
  if (!marking) {
    return []
  }

  return marking
    .split(/\s+/)
    .map((part) => part.trim())
    .filter(Boolean)
}

function formatSearchResultText(result: SlipLookupResponse | null, error: string | null) {
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
    const values = result.formulas[key] || []
    if (values.length > 0) {
      lines.push(`${title}:`)
      values.forEach((formula) => lines.push(formula))
    }
  })

  return lines.join("\n")
}

function formatPdfResultText(result: PdfCheckResponse | null, error: string | null) {
  if (error) {
    return `ПРОВЕРКА PDF\nОшибка: ${error}`
  }

  if (!result) {
    return ""
  }

  const lines = [
    "ПРОВЕРКА PDF",
    `Файл: ${result.file_name}`,
    `Всего позиций: ${result.total_items}`,
    `Проблемных позиций: ${result.issues_count}`,
  ]

  if (result.status === "success") {
    lines.push("Результат: отклонений по таблице слипания не обнаружено")
    return lines.join("\n")
  }

  if (result.status === "warning" && result.message) {
    lines.push(`Результат: ${result.message}`)
    return lines.join("\n")
  }

  result.report_data.forEach((item) => {
    lines.push("")
    lines.push(`Позиция №${item.pos_num} | ${item.size}`)
    lines.push(`Формула: ${item.formula}`)
    lines.push(`Открывание: ${item.is_outside ? "Наружу (формула перевернута)" : "Внутрь"}`)
    lines.push(`Раскладка: ${item.raskl || "Нет"}`)
    item.errors.forEach((issue) => lines.push(`- ${issue}`))
  })

  return lines.join("\n")
}

function SearchResultView({
  result,
  error,
}: {
  result: SlipLookupResponse | null
  error: string | null
}) {
  if (error) {
    return (
      <Alert variant="destructive" className="rounded-2xl border-destructive/25 bg-destructive/5">
        <OctagonAlert className="size-4" />
        <AlertTitle>Ошибка подбора</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!result) {
    return null
  }

  const markingLines = splitMarkingLines(result.marking)
  const visibleGroups = visibleFormulaGroups.filter(({ key }) => (result.formulas[key] || []).length > 0)

  const statusTone =
    result.status === "success"
      ? "border-emerald-200 bg-emerald-50 text-emerald-950"
      : "border-amber-200 bg-amber-50 text-amber-950"

  const statusIcon =
    result.status === "success" ? (
      <CheckCircle2 className="size-4" />
    ) : (
      <TriangleAlert className="size-4" />
    )

  const statusTitle = result.status === "success" ? "Формулы найдены" : "Правило не найдено"

  return (
    <div className="space-y-3">
      <Alert className={`rounded-2xl ${statusTone}`}>
        {statusIcon}
        <AlertTitle>{statusTitle}</AlertTitle>
        <AlertDescription>
          {result.status === "success"
            ? "Подбор выполнен по таблице слипания."
            : "Для указанных размеров подходящее правило не найдено."}
        </AlertDescription>
      </Alert>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-border/70 bg-white/90 p-3">
          <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Размер</div>
          <div className="mt-1.5 text-lg font-semibold">{result.width}×{result.height}</div>
        </div>
        <div className="rounded-2xl border border-border/70 bg-white/90 p-3">
          <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Округление</div>
          <div className="mt-1.5 text-lg font-semibold">{result.width_round}×{result.height_round}</div>
        </div>
      </div>

      {markingLines.length > 0 ? (
        <div className="rounded-2xl border border-border/70 bg-white/90 p-3">
          <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Формулы из таблицы слипания</div>
          <div className="mt-1.5 space-y-1.5">
            {markingLines.map((line) => (
              <div key={line} className="text-base font-medium">
                {line}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {result.status === "success" && visibleGroups.length > 0 ? (
        <div className="space-y-2.5">
          {visibleGroups.map(({ key, title }) => (
              <div key={key} className="rounded-2xl border border-border/70 bg-white/90 p-3">
                <div className="mb-2.5 flex items-center gap-2">
                  <Info className="size-4 text-primary" />
                  <h3 className="text-sm font-semibold">{title}</h3>
                </div>
                <ul className="space-y-1.5">
                  {result.formulas[key].map((formula) => (
                    <li
                      key={formula}
                      className="flex items-start gap-3 rounded-xl border border-border/50 bg-secondary/20 px-3 py-2"
                    >
                      <span className="mt-1 size-2 rounded-full bg-primary" />
                      <span className="font-mono text-sm">{formula}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
        </div>
      ) : null}
    </div>
  )
}

function PdfResultView({
  result,
  error,
}: {
  result: PdfCheckResponse | null
  error: string | null
}) {
  if (error) {
    return (
      <Alert variant="destructive" className="rounded-2xl border-destructive/25 bg-destructive/5">
        <OctagonAlert className="size-4" />
        <AlertTitle>Ошибка проверки PDF</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!result) {
    return null
  }

  const isSuccess = result.status === "success"
  const isWarning = result.status === "warning"

  return (
    <div className="space-y-3">
      <Alert
        className={cn(
          "rounded-2xl",
          isSuccess
            ? "border-emerald-200 bg-emerald-50 text-emerald-950"
            : isWarning
              ? "border-amber-200 bg-amber-50 text-amber-950"
              : "border-destructive/25 bg-destructive/5 text-foreground",
        )}
      >
        {isSuccess ? (
          <CheckCircle2 className="size-4" />
        ) : isWarning ? (
          <TriangleAlert className="size-4" />
        ) : (
          <OctagonAlert className="size-4" />
        )}
        <AlertTitle>
          {isSuccess ? "Проверка завершена без замечаний" : isWarning ? "Нужна корректная выгрузка" : "Найдены замечания"}
        </AlertTitle>
        <AlertDescription>
          {isWarning && result.message
            ? result.message
            : isSuccess
              ? "Отклонений по таблице слипания не обнаружено."
              : `Проблемных позиций: ${result.issues_count} из ${result.total_items}.`}
        </AlertDescription>
      </Alert>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-border/70 bg-white/90 p-3">
          <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Файл</div>
          <div className="mt-1.5 text-base font-semibold break-all">{result.file_name}</div>
        </div>
        <div className="rounded-2xl border border-border/70 bg-white/90 p-3">
          <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Позиции / проблемы</div>
          <div className="mt-1.5 text-base font-semibold">
            {result.total_items} / {result.issues_count}
          </div>
        </div>
      </div>

      {result.report_data.length > 0 ? (
        <div className="space-y-2.5">
          {result.report_data.map((item) => (
            <div key={`${item.pos_num}-${item.size}`} className="rounded-2xl border border-border/70 bg-white/90 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-base font-semibold">Позиция №{item.pos_num}</div>
                  <div className="text-sm text-muted-foreground">{item.size}</div>
                </div>
                <TriangleAlert className="size-4 text-destructive" />
              </div>
              <div className="mt-2.5 space-y-1 text-sm">
                <div><span className="font-medium">Формула:</span> {item.formula}</div>
                <div><span className="font-medium">Открывание:</span> {item.is_outside ? "Наружу (формула перевернута)" : "Внутрь"}</div>
                <div><span className="font-medium">Раскладка:</span> {item.raskl || "Нет"}</div>
              </div>
              <ul className="mt-2.5 space-y-1.5">
                {item.errors.map((issue) => (
                  <li key={issue} className="flex items-start gap-3 rounded-xl bg-destructive/5 px-3 py-1.5 text-sm">
                    <span className="mt-1 size-2 rounded-full bg-destructive" />
                    <span>{issue}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default function App() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [widthValue, setWidthValue] = useState("")
  const [heightValue, setHeightValue] = useState("")
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searchResult, setSearchResult] = useState<SlipLookupResponse | null>(null)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)
  const [pdfResult, setPdfResult] = useState<PdfCheckResponse | null>(null)
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle")
  const [activeResult, setActiveResult] = useState<"search" | "pdf" | null>(null)
  const [resultDialogOpen, setResultDialogOpen] = useState(false)

  const normalizeIntegerInput = (value: string) => value.replace(/\D/g, "")

  const searchResultText = formatSearchResultText(searchResult, searchError)
  const pdfResultText = formatPdfResultText(pdfResult, pdfError)
  const resultText =
    activeResult === "search"
      ? searchResultText
      : activeResult === "pdf"
        ? pdfResultText
        : ""

  const submitSearch = async () => {
    const width = widthValue.trim()
    const height = heightValue.trim()
    if (!width || !height) {
      setActiveResult("search")
      setPdfError(null)
      setPdfResult(null)
      setSearchError("Укажите ширину и высоту стеклопакета")
      setSearchResult(null)
      setResultDialogOpen(true)
      return
    }

    setActiveResult("search")
    setSearchLoading(true)
    setSearchError(null)
    setSearchResult(null)
    setPdfError(null)
    setPdfResult(null)
    setCopyState("idle")

    try {
      const response = await fetch("/api/slip-formulas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ size: `${width}*${height}` }),
      })
      const data = (await response.json()) as SlipLookupResponse | { detail?: string }
      if (!response.ok) {
        throw new Error("detail" in data ? data.detail || "Ошибка поиска" : "Ошибка поиска")
      }
      setSearchResult(data as SlipLookupResponse)
      setResultDialogOpen(true)
    } catch (error) {
      setSearchResult(null)
      setSearchError(error instanceof Error ? error.message : "Ошибка поиска")
      setResultDialogOpen(true)
    } finally {
      setSearchLoading(false)
    }
  }

  const selectFile = (file: File | null) => {
    if (!file) {
      return
    }
    if (file.type !== "application/pdf") {
      setPdfError("Пожалуйста, выберите PDF файл.")
      setSelectedFile(null)
      setActiveResult("pdf")
      setResultDialogOpen(true)
      return
    }
    setPdfError(null)
    setPdfResult(null)
    setSelectedFile(file)
  }

  const submitPdf = async () => {
    if (!selectedFile) {
      return
    }

    setActiveResult("pdf")
    setPdfLoading(true)
    setPdfError(null)
    setPdfResult(null)
    setSearchError(null)
    setSearchResult(null)
    setCopyState("idle")

    try {
      const formData = new FormData()
      formData.append("file", selectedFile)

      const response = await fetch("/api/check", {
        method: "POST",
        body: formData,
      })
      const data = (await response.json()) as PdfCheckResponse | { detail?: string }
      if (!response.ok) {
        throw new Error("detail" in data ? data.detail || "Ошибка сервера" : "Ошибка сервера")
      }
      setPdfResult(data as PdfCheckResponse)
      setResultDialogOpen(true)
    } catch (error) {
      setPdfError(error instanceof Error ? error.message : "Ошибка сервера")
      setResultDialogOpen(true)
    } finally {
      setPdfLoading(false)
    }
  }

  const copyCombinedResult = async () => {
    if (!resultText) {
      return
    }

    try {
      await navigator.clipboard.writeText(resultText)
      setCopyState("copied")
      window.setTimeout(() => setCopyState("idle"), 2000)
    } catch {
      setCopyState("error")
      window.setTimeout(() => setCopyState("idle"), 2000)
    }
  }

  return (
    <main className="min-h-screen px-4 py-4 text-foreground sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <header className="overflow-hidden rounded-[28px] border border-border/60 bg-card/90 shadow-sm backdrop-blur">
          <div className="grid gap-6 px-5 py-5 lg:grid-cols-[260px_minmax(0,1fr)_250px] lg:items-center lg:gap-8 lg:px-7">
            <div className="overflow-hidden rounded-[24px] border border-border/70 bg-white/80 shadow-sm">
              <img
                src={heroQaIllustration}
                alt="Иллюстрация проверки заказа"
                className="h-[178px] w-full bg-white object-contain object-center p-2 lg:h-[200px]"
              />
            </div>

            <div className="flex min-w-0 items-center justify-center">
              <h1 className="whitespace-nowrap text-center text-[1.8rem] font-semibold tracking-tight sm:text-[2.1rem] lg:text-[2.5rem]">
                Подбор формул и проверка заказов
              </h1>
            </div>

            <div className="flex items-start justify-center pt-1 lg:justify-end">
              <img
                src={ecooknaGroupLogo}
                alt="ECOOKNA GROUP"
                className="h-auto w-[210px] max-w-full object-contain"
              />
            </div>
          </div>
        </header>

        <section className="grid gap-4 xl:grid-cols-2 xl:items-stretch">
          <Card className="overflow-hidden border-border/70 bg-card/95 shadow-sm xl:h-full">
            <CardHeader className="min-h-[6.5rem] gap-2 border-b border-border/70 bg-[linear-gradient(135deg,rgba(39,174,96,0.12),rgba(255,255,255,0.9))]">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <CardTitle className="text-2xl">Подбор формулы</CardTitle>
                  <CardDescription className="max-w-2xl text-sm leading-6">
                    Укажите размеры для проверки
                  </CardDescription>
                </div>
                <div className="hidden rounded-3xl border border-white/80 bg-white/70 p-3 text-primary shadow-sm sm:block">
                  <Search className="size-6" />
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex h-full flex-col justify-between gap-4 pt-5">
              <div className="grid gap-4">
                <div className="grid gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Ширина, мм</label>
                    <Input
                      value={widthValue}
                      onChange={(event) => setWidthValue(normalizeIntegerInput(event.target.value))}
                      inputMode="numeric"
                      pattern="[0-9]*"
                      placeholder="Например, 1520"
                      className="h-11 rounded-xl border-border/80 bg-white text-base shadow-none"
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault()
                          void submitSearch()
                        }
                      }}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Высота, мм</label>
                    <Input
                      value={heightValue}
                      onChange={(event) => setHeightValue(normalizeIntegerInput(event.target.value))}
                      inputMode="numeric"
                      pattern="[0-9]*"
                      placeholder="Например, 2730"
                      className="h-11 rounded-xl border-border/80 bg-white text-base shadow-none"
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault()
                          void submitSearch()
                        }
                      }}
                    />
                  </div>
                </div>
              </div>
              <Button
                onClick={() => void submitSearch()}
                disabled={searchLoading}
                className="h-11 w-full rounded-xl px-5 text-sm font-semibold"
              >
                {searchLoading ? (
                  <>
                    <LoaderCircle className="size-4 animate-spin" />
                    Подбираем
                  </>
                ) : (
                  <>
                    <FileSearch className="size-4" />
                    Подобрать формулы
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          <Card className="overflow-hidden border-border/70 bg-card/95 shadow-sm xl:h-full">
            <CardHeader className="min-h-[6.5rem] gap-2 border-b border-border/70 bg-[linear-gradient(135deg,rgba(39,174,96,0.12),rgba(255,255,255,0.9))]">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <CardTitle className="text-2xl">Проверка заказа</CardTitle>
                  <CardDescription className="leading-6">
                    Загрузите PDF из StartОкна. Нужная форма отчета находится в меню{" "}
                    <span className="inline-flex rounded-full border border-primary/20 bg-primary/10 px-2.5 py-0.5 font-medium text-primary">
                      Печать/Резерв/3.4 Заполнения
                    </span>
                    .
                  </CardDescription>
                </div>
                <div className="hidden rounded-3xl border border-white/80 bg-white/70 p-3 text-primary shadow-sm sm:block">
                  <ScanSearch className="size-6" />
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex h-full flex-col justify-between gap-4 pt-5">
              <div
                onDragOver={(event) => {
                  event.preventDefault()
                  setIsDragging(true)
                }}
                onDragLeave={(event) => {
                  event.preventDefault()
                  setIsDragging(false)
                }}
                onDrop={(event) => {
                  event.preventDefault()
                  setIsDragging(false)
                  selectFile(event.dataTransfer.files[0] ?? null)
                }}
                className={cn(
                  "rounded-[24px] border border-dashed p-5 text-center transition-colors",
                  isDragging
                    ? "border-primary bg-primary/5"
                    : "border-border bg-secondary/30",
                )}
              >
                <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <FileUp className="size-6" />
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium">Нажмите или перетащите PDF сюда</p>
                  <p className="text-sm text-muted-foreground">Максимальный размер: 10 МБ</p>
                  {selectedFile ? (
                    <Badge className="rounded-full px-3 py-1">{selectedFile.name}</Badge>
                  ) : null}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
                />
                <Button
                  variant="outline"
                  className="mt-4 rounded-xl"
                  onClick={() => fileInputRef.current?.click()}
                >
                  Выбрать PDF
                </Button>
              </div>

              <Button
                onClick={() => void submitPdf()}
                disabled={!selectedFile || pdfLoading}
                className="h-11 w-full rounded-xl text-sm font-semibold"
              >
                {pdfLoading ? (
                  <>
                    <LoaderCircle className="size-4 animate-spin" />
                    Проверяем файл
                  </>
                ) : (
                  "Проверить файл"
                )}
              </Button>
            </CardContent>
          </Card>
        </section>
      </div>

      <Dialog open={resultDialogOpen} onOpenChange={setResultDialogOpen}>
        <DialogContent className="max-w-4xl rounded-[28px] border-border/70 bg-background/98 p-0 shadow-2xl">
          <DialogHeader className="border-b border-border/70 bg-[linear-gradient(135deg,rgba(39,174,96,0.12),rgba(255,255,255,0.92))] px-6 py-5 text-left">
            <div className="space-y-3">
              <DialogTitle className="text-3xl font-semibold tracking-tight">
                Результат проверок
              </DialogTitle>
              <div className="flex items-center justify-between gap-4">
                <div className="flex min-h-11 items-center gap-3">
                  {activeResult === "search" ? (
                    <Badge
                      variant={searchError || searchResult?.status === "not_found" ? "secondary" : "default"}
                      className="h-11 rounded-xl px-4 text-base"
                    >
                      Подбор формулы
                    </Badge>
                  ) : null}
                  {activeResult === "pdf" ? (
                    <Badge
                      variant={
                        pdfError || pdfResult?.status === "issues_found" || pdfResult?.status === "warning"
                          ? "secondary"
                          : "default"
                      }
                      className="h-11 rounded-xl px-4 text-base"
                    >
                      Проверка PDF
                    </Badge>
                  ) : null}
                </div>
                <Button
                  variant="outline"
                  className="h-11 rounded-xl px-5 text-base"
                  onClick={() => void copyCombinedResult()}
                  disabled={!resultText}
                >
                  <Copy className="size-4" />
                  {copyState === "copied"
                    ? "Скопировано"
                    : copyState === "error"
                      ? "Ошибка копирования"
                      : "Скопировать"}
                </Button>
              </div>
            </div>
            <DialogDescription className="sr-only">
              Подробный результат последней проверки.
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[75vh] overflow-auto p-4">
            {resultText ? (
              <div className="rounded-[24px] border border-border/70 bg-secondary/25 p-2.5">
                <div className="rounded-[18px] border border-border/70 bg-white/90 p-3.5">
                  {activeResult === "search" ? (
                    <SearchResultView result={searchResult} error={searchError} />
                  ) : (
                    <PdfResultView result={pdfResult} error={pdfError} />
                  )}
                </div>
              </div>
            ) : (
              <Alert className="rounded-2xl border-border/70 bg-secondary/30">
                <AlertCircle className="size-4" />
                <AlertTitle>Пока нет результата</AlertTitle>
                <AlertDescription>
                  Выполните подбор формулы или проверку PDF, и результат появится в модальном окне.
                </AlertDescription>
              </Alert>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </main>
  )
}
