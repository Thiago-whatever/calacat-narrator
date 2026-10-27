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

const HALF_TIME_S = 45 * 60

/** On-air minute, matching the backend's `broadcast_minute`: 0:00-0:59 is 1', capped at 45' and 90'. */
export const minutes = (seconds: number) => {
  const minute = Math.floor(seconds / 60) + 1
  return `${Math.min(minute, seconds < HALF_TIME_S ? 45 : 90)}’`
}
