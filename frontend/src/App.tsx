import { useRef, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  FileSearch,
  FileUp,
  LoaderCircle,
  Search,
  ShieldAlert,
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
import { Separator } from "@/components/ui/separator"
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

  const normalizeIntegerInput = (value: string) => value.replace(/\D/g, "")

  const submitSearch = async () => {
    const width = widthValue.trim()
    const height = heightValue.trim()
    if (!width || !height) {
      setSearchError("Укажите ширину и высоту стеклопакета")
      setSearchResult(null)
      return
    }

    setSearchLoading(true)
    setSearchError(null)

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

    setPdfLoading(true)
    setPdfError(null)
    setPdfResult(null)

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

  return (
    <main className="min-h-screen px-4 py-6 text-foreground sm:px-6 lg:px-10">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="overflow-hidden rounded-[28px] border border-border/60 bg-card/90 shadow-sm backdrop-blur">
          <div className="flex flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
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

        <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <Card className="overflow-hidden border-border/70 bg-card/95 shadow-sm">
            <CardHeader className="gap-4 border-b border-border/70 bg-[linear-gradient(135deg,rgba(39,174,96,0.12),rgba(255,255,255,0.9))]">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <Badge className="rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em]">
                    Быстрый поиск
                  </Badge>
                  <CardTitle className="text-2xl">Подбор формулы из таблицы слипания</CardTitle>
                  <CardDescription className="max-w-2xl text-sm leading-6">
                    Введите размер стеклопакета в формате <span className="font-medium text-foreground">1520*2730</span>.
                    Система покажет все доступные формулы, которые есть в таблице.
                  </CardDescription>
                </div>
                <div className="hidden rounded-3xl border border-white/80 bg-white/70 p-3 text-primary shadow-sm sm:block">
                  <Search className="size-6" />
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6 pt-6">
              <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Ширина, мм</label>
                    <Input
                      value={widthValue}
                      onChange={(event) => setWidthValue(normalizeIntegerInput(event.target.value))}
                      inputMode="numeric"
                      pattern="[0-9]*"
                      placeholder="Например, 1520"
                      className="h-12 rounded-xl border-border/80 bg-white text-base shadow-none"
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
                      className="h-12 rounded-xl border-border/80 bg-white text-base shadow-none"
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault()
                          void submitSearch()
                        }
                      }}
                    />
                  </div>
                </div>
                <Button
                  onClick={() => void submitSearch()}
                  disabled={searchLoading}
                  className="h-12 rounded-xl px-6 text-sm font-semibold"
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
              </div>

              {searchError ? (
                <Alert variant="destructive" className="rounded-2xl border-destructive/30 bg-destructive/5">
                  <AlertCircle className="size-4" />
                  <AlertTitle>Ошибка поиска</AlertTitle>
                  <AlertDescription>{searchError}</AlertDescription>
                </Alert>
              ) : null}

              {searchResult ? (
                <div className="space-y-4">
                  <Alert
                    className={cn(
                      "rounded-2xl border",
                      searchResult.status === "not_found"
                        ? "border-amber-200 bg-amber-50 text-amber-950"
                        : "border-emerald-200 bg-emerald-50 text-emerald-950",
                    )}
                  >
                    {searchResult.status === "not_found" ? (
                      <ShieldAlert className="size-4" />
                    ) : (
                      <CheckCircle2 className="size-4" />
                    )}
                    <AlertTitle>
                      {searchResult.status === "not_found"
                        ? "Правило не найдено"
                        : "Формулы найдены"}
                    </AlertTitle>
                    <AlertDescription>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">Размер: {searchResult.width}x{searchResult.height}</Badge>
                        <Badge variant="outline">
                          Округление: {searchResult.width_round}x{searchResult.height_round}
                        </Badge>
                        {searchResult.marking ? (
                          <Badge variant="outline">Маркировка: {searchResult.marking}</Badge>
                        ) : null}
                      </div>
                      {searchResult.status === "not_found" ? (
                        <p className="pt-2">
                          Для этого размера в таблице слипания нет подходящей строки.
                        </p>
                      ) : null}
                    </AlertDescription>
                  </Alert>

                  {searchResult.status === "success" ? (
                    <div className="grid gap-4 md:grid-cols-3">
                      {formulaGroups
                        .filter(({ key }) => (searchResult.formulas[key] || []).length > 0)
                        .map(({ key, title }) => (
                          <Card key={key} className="gap-4 rounded-2xl border-border/70 bg-white/90 py-5 shadow-none">
                            <CardHeader className="gap-3 px-5">
                              <CardTitle className="text-lg">{title}</CardTitle>
                            </CardHeader>
                            <CardContent className="px-5">
                              <ul className="space-y-3 text-sm leading-6 text-muted-foreground">
                                {searchResult.formulas[key].map((formula) => (
                                  <li
                                    key={formula}
                                    className="rounded-xl border border-border/70 bg-secondary/40 px-3 py-2 text-foreground"
                                  >
                                    {formula}
                                  </li>
                                ))}
                              </ul>
                            </CardContent>
                          </Card>
                        ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/95 shadow-sm">
            <CardHeader className="border-b border-border/70">
              <Badge variant="secondary" className="w-fit rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em]">
                Анализ PDF
              </Badge>
              <CardTitle className="text-2xl">Проверка заказа</CardTitle>
              <CardDescription className="leading-6">
                Загрузите PDF из StartОкна. Нужная форма отчета находится в меню{" "}
                <span className="inline-flex rounded-full border border-primary/20 bg-primary/10 px-3 py-1 font-medium text-primary">
                  Печать/Резерв/3.4 Заполнения
                </span>
                . Проверка использует те же серверные правила, что и бот.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-6">
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
                  "rounded-[24px] border border-dashed p-6 text-center transition-colors",
                  isDragging
                    ? "border-primary bg-primary/5"
                    : "border-border bg-secondary/30",
                )}
              >
                <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <FileUp className="size-7" />
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
                  className="mt-5 rounded-xl"
                  onClick={() => fileInputRef.current?.click()}
                >
                  Выбрать PDF
                </Button>
              </div>

              <Button
                onClick={() => void submitPdf()}
                disabled={!selectedFile || pdfLoading}
                className="h-12 w-full rounded-xl text-sm font-semibold"
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

              {pdfError ? (
                <Alert variant="destructive" className="rounded-2xl border-destructive/30 bg-destructive/5">
                  <AlertCircle className="size-4" />
                  <AlertTitle>Ошибка проверки</AlertTitle>
                  <AlertDescription>{pdfError}</AlertDescription>
                </Alert>
              ) : null}
            </CardContent>
          </Card>
        </section>

        {pdfResult ? (
          <Card className="border-border/70 bg-card/95 shadow-sm">
            <CardHeader className="gap-4 border-b border-border/70">
              <div className="flex flex-wrap items-center gap-3">
                <Badge
                  variant={pdfResult.status === "success" ? "default" : "secondary"}
                  className="rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em]"
                >
                  {pdfResult.status === "success"
                    ? "Ошибок нет"
                    : pdfResult.status === "warning"
                      ? "Предупреждение"
                      : "Есть замечания"}
                </Badge>
                <div className="text-sm text-muted-foreground">{pdfResult.file_name}</div>
              </div>
              <CardTitle className="text-2xl">Результат проверки PDF</CardTitle>
              <CardDescription className="leading-6">
                Всего позиций: {pdfResult.total_items}. Проблемных позиций: {pdfResult.issues_count}.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-6">
              {pdfResult.status === "success" ? (
                <Alert className="rounded-2xl border-emerald-200 bg-emerald-50 text-emerald-950">
                  <CheckCircle2 className="size-4" />
                  <AlertTitle>Файл успешно проверен</AlertTitle>
                  <AlertDescription>Отклонений по таблице слипания не обнаружено.</AlertDescription>
                </Alert>
              ) : null}

              {pdfResult.status === "warning" && pdfResult.message ? (
                <Alert className="rounded-2xl border-amber-200 bg-amber-50 text-amber-950">
                  <AlertCircle className="size-4" />
                  <AlertTitle>Нужна корректная выгрузка</AlertTitle>
                  <AlertDescription>{pdfResult.message}</AlertDescription>
                </Alert>
              ) : null}

              {pdfResult.report_data.length > 0 ? (
                <div className="grid gap-4">
                  {pdfResult.report_data.map((item) => (
                    <Card key={`${item.pos_num}-${item.size}`} className="gap-4 rounded-2xl border-border/70 bg-white/90 py-5 shadow-none">
                      <CardHeader className="gap-3 px-5">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <CardTitle className="text-lg">Позиция №{item.pos_num}</CardTitle>
                          <Badge variant="outline">{item.size}</Badge>
                        </div>
                        <CardDescription className="space-y-1 text-sm leading-6">
                          <div>
                            <span className="font-medium text-foreground">Формула:</span> {item.formula}
                          </div>
                          <div>
                            <span className="font-medium text-foreground">Открывание:</span>{" "}
                            {item.is_outside ? "Наружу (формула перевернута)" : "Внутрь"}
                          </div>
                          <div>
                            <span className="font-medium text-foreground">Раскладка:</span> {item.raskl || "Нет"}
                          </div>
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="px-5">
                        <Separator className="mb-4" />
                        <div className="space-y-2">
                          {item.errors.map((error) => (
                            <Alert
                              key={error}
                              variant="destructive"
                              className="rounded-2xl border-destructive/25 bg-destructive/5"
                            >
                              <ShieldAlert className="size-4" />
                              <AlertTitle>Несоответствие</AlertTitle>
                              <AlertDescription>{error}</AlertDescription>
                            </Alert>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        ) : null}
      </div>
    </main>
  )
}
