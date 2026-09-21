import { createContext, useContext, useMemo } from 'react'
import type { ReactNode } from 'react'
import type { Dataset, DisplayLanguage, HistoryRecord, Signal } from './types'
import { displayBuyer } from './lib'

const TranslationContext = createContext<{
  language: DisplayLanguage
  translations: Dataset['translations']
}>({ language: 'en', translations: {} })
export const useTranslations = () => useContext(TranslationContext)

export function TranslationProvider({
  language,
  translations,
  children,
}: {
  language: DisplayLanguage
  translations: Dataset['translations']
  children: ReactNode
}) {
  const value = useMemo(() => ({ language, translations }), [language, translations])
  return <TranslationContext.Provider value={value}>{children}</TranslationContext.Provider>
}

export function useSignalText(signal: Signal) {
  const { language, translations } = useContext(TranslationContext)
  const english = language === 'en' ? translations?.[signal.id] : undefined
  return {
    title: english?.title || signal.title,
    description: english?.description || signal.description,
    buyerName: displayBuyer(signal, english),
    original: language === 'en' && !english,
  }
}
export function useHistoryText(record: HistoryRecord) {
  const { language, translations } = useContext(TranslationContext)
  return language === 'en'
    ? record.title_en || translations?.[record.signal_id]?.title || record.title
    : record.title
}
