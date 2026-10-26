import type { Lang } from './types'

// Translations live in locales/*.json so they can be edited (or handed to a translation tool) without touching code.
import en from './locales/en.json'
import esJson from './locales/es.json'

/** Shape of a string table; `en.json` is the reference. `topics` is open-ended (signal kinds). */
export type Strings = Omit<typeof en, 'topics'> & { topics: Record<string, string> }

// Typed against en.json, so a key missing from es.json fails the build.
const es: Strings = esJson

export const STRINGS: Record<Lang, Strings> = { en, es }

/** Live cards use signal kinds as topics; unknown ones are shown humanized ("pass_streak" → "Pass streak"). */
export function topicLabel(t: Strings, topic: string): string {
  const known = t.topics[topic]
  if (known) return known
  const words = topic.replace(/[_-]+/g, ' ').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export const minutes = (seconds: number) => `${Math.floor(seconds / 60)}’`
