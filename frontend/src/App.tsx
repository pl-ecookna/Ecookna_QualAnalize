import { useRef, useState } from "react"
import {
  AlertCircle,
  Copy,
  FileSearch,
  FileUp,
  LoaderCircle,
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
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

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

  if (result.marking) {
    lines.push(`Маркировка: ${result.marking}`)
  }

  if (result.status === "not_found") {
    lines.push("Результат: правило в таблице слипания не найдено")
    return lines.join("\n")
  }

  lines.push("Результат: формулы найдены")

  formulaGroups.forEach(({ key, title }) => {
    const values = result.formulas[key] || []
    if (values.length > 0) {
      lines.push(`${title}:`)
      values.forEach((formula) => lines.push(`- ${formula}`))
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
    } catch (error) {
      setSearchResult(null)
      setSearchError(error instanceof Error ? error.message : "Ошибка поиска")
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
    } catch (error) {
      setPdfError(error instanceof Error ? error.message : "Ошибка сервера")
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
          <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-3">
                <div className="rounded-2xl bg-primary px-3 py-2 text-sm font-semibold tracking-[0.18em] text-primary-foreground">
                  ЭКООКНА
                </div>
                <Badge variant="outline" className="rounded-full px-3 py-1 text-xs uppercase tracking-[0.16em]">
                  Контроль качества
                </Badge>
              </div>
              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                Подбор формул и проверка заказов
              </h1>
            </div>
          </div>
        </header>

        <section className="grid gap-4 xl:grid-cols-[0.9fr_1.05fr_1.2fr] xl:items-stretch">
          <Card className="overflow-hidden border-border/70 bg-card/95 shadow-sm">
            <CardHeader className="min-h-40 gap-3 border-b border-border/70 bg-[linear-gradient(135deg,rgba(39,174,96,0.12),rgba(255,255,255,0.9))]">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <Badge className="rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em]">
                    Быстрый поиск
                  </Badge>
                  <CardTitle className="text-2xl">Подбор формулы из таблицы слипания</CardTitle>
                  <CardDescription className="max-w-2xl text-sm leading-6">
                    Введите ширину и высоту, чтобы получить допустимые формулы из таблицы.
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

          <Card className="overflow-hidden border-border/70 bg-card/95 shadow-sm">
            <CardHeader className="min-h-40 gap-3 border-b border-border/70 bg-[linear-gradient(135deg,rgba(39,174,96,0.12),rgba(255,255,255,0.9))]">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
              <Badge variant="secondary" className="w-fit rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em]">
                Анализ PDF
              </Badge>
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
        
          <Card className="border-border/70 bg-card/95 shadow-sm">
            <CardHeader className="gap-4 border-b border-border/70">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <Badge
                    variant="outline"
                    className="rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em]"
                  >
                    Общий результат
                  </Badge>
                  {activeResult === "search" ? (
                    <Badge
                      variant={searchError || searchResult?.status === "not_found" ? "secondary" : "default"}
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
                    >
                      Проверка PDF
                    </Badge>
                  ) : null}
                </div>
                <Button
                  variant="outline"
                  className="rounded-xl"
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
              <CardTitle className="text-2xl">Результат проверок</CardTitle>
              <CardDescription className="leading-6">
                Все результаты выводятся в одном текстовом блоке. Его удобно целиком выделить и скопировать.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-6">
              {resultText ? (
                <div className="rounded-[24px] border border-border/70 bg-secondary/25 p-3">
                  <textarea
                    readOnly
                    value={resultText}
                    className="h-[28rem] w-full resize-none rounded-[18px] border border-border/70 bg-white/90 p-4 font-mono text-sm leading-6 text-foreground outline-none xl:h-[31rem]"
                  />
                </div>
              ) : (
                <Alert className="rounded-2xl border-border/70 bg-secondary/30">
                  <AlertCircle className="size-4" />
                  <AlertTitle>Пока нет результата</AlertTitle>
                  <AlertDescription>
                    Выполните подбор формулы или проверку PDF, и результат появится здесь в едином блоке.
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  )
}
