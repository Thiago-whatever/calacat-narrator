export type Lang = 'en' | 'es'

export interface Team {
  id: string
  name: string
  short: string
  /** Shield/silhouette fill, ink on top of it, and the soft background behind a silhouette. */
  color: string
  ink: string
  soft: string
}

export interface Player {
  id: string
  name: string
  num: number
  team: string
}

export interface Match {
  id: string
  home: string
  away: string
}

/** A transmission (TV 1, Stream…): carries one match and holds its own on-air card. */
export interface Output {
  id: string
  name: string
  match: string
}

export interface CardText {
  h: string
  b: string
}

export interface FeedCard {
  id: string
  match: string
  team: string
  player?: Player
  /** Match clock in seconds. */
  clock: number
  topic: string
  critical: boolean
  salience: number
  specialist?: Record<Lang, string>
  text: Record<Lang, CardText>
}

export type Phase = 'pre' | 'h1' | 'h2' | 'ft'

/** Everything the console renders that comes from a card source (demo simulation or live feed). */
export interface Source {
  teams: Record<string, Team>
  players: Player[]
  matches: Record<string, Match>
  outputs: Output[]
  cards: FeedCard[]
  clock: number
  phase: Phase
}
