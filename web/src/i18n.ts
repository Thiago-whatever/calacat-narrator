import type { Lang } from './types'

const en = {
  sub: 'Reporter console', start: 'Start match', pause: 'Pause', resume: 'Resume', restart: 'Restart',
  lang: 'Language', a11y: 'Accessibility', hc: 'High contrast', lg: 'Larger text', rm: 'Reduce motion',
  output: 'Transmission', outLive: 'card on air', outOff: 'nothing on air', program: 'Program feed',
  preMatch: 'Pre-match', kickoff: 'Kick-off soon', preHint: 'Press Start match to begin the demo feed.',
  liveHint: 'Waiting for the first insight from the match.',
  h1: '1st half', h2: '2nd half', ft: 'Full time', onAir: 'On air',
  feed: 'Insight feed',
  feedTip: 'Click a card to preview it on screen, or drag it to the spot you want. J / K moves between cards.',
  waiting: 'Waiting', empty: 'Cards appear here as the matches unfold.',
  emptyFilter: 'No cards for this game yet.', emptyFocus: 'No cards for this focus yet.', cards: 'cards',
  games: 'Filter by game', allGames: 'All games', focus: 'Focus', focusNone: 'No focus', teams: 'Teams', players: 'Players',
  dragTo: 'Drag onto the screen', release: 'Release to place',
  editCard: 'Card editor', headline: 'Headline', body: 'Body', size: 'Size', small: 'Small', medium: 'Medium', large: 'Large',
  removePrev: 'Remove card from preview', removed: 'Card removed from preview',
  move: 'Move card', arrowsMove: 'Drag it anywhere on screen, or use the arrow keys. Hold Shift for bigger steps.',
  bPreview: 'Preview', bLive: 'Live', liveIn: 'Live in',
  jersey: 'jersey number', player: 'Player', team: 'Team',
  resizeW: 'Resize width', resizeH: 'Resize height', resizeXY: 'Resize width and height',
  arrowsW: 'Use left and right arrow keys.', arrowsH: 'Use up and down arrow keys.', arrowsXY: 'Use arrow keys.',
  control: 'On-air control', offAir: 'Off air', selectHint: 'Click or drag a card from the feed onto the screen.',
  ready: 'Preview · not live', editHint: 'Drag to place it · click its text to edit · × to remove',
  nextReady: 'Next card ready in preview',
  goLive: 'Go live on', replace: 'Replace on', pull: 'Pull from air', cancel: 'Cancel', goNow: 'Go live now',
  goingLive: 'Going live on', secs: 's', sendMsg: 'Going live in 5 seconds. Press Escape to cancel.',
  cancelMsg: 'Cancelled. The card is back on screen for editing.', pulled: 'Card pulled from air',
  placed: 'Card placed on screen',
  live: 'Live', salience: 'Salience', new: 'New', toastTitle: 'Card is live on',
  shortcuts: 'J / K move · Enter go live · Esc cancel or pull',
  feedConnecting: 'Connecting to the live feed…', feedError: 'Live feed unavailable. Retrying…',
  topics: { goal: 'Goal', passing: 'Build-up', duels: 'Duels', discipline: 'Discipline', setpiece: 'Set piece', keeper: 'Goalkeeping' } as Record<string, string>,
}

export type Strings = typeof en

const es: Strings = {
  sub: 'Consola del reportero', start: 'Iniciar partido', pause: 'Pausar', resume: 'Reanudar', restart: 'Reiniciar',
  lang: 'Idioma', a11y: 'Accesibilidad', hc: 'Alto contraste', lg: 'Texto más grande', rm: 'Reducir movimiento',
  output: 'Transmisión', outLive: 'tarjeta al aire', outOff: 'nada al aire', program: 'Señal de programa',
  preMatch: 'Previa', kickoff: 'Ya casi empieza', preHint: 'Pulsa Iniciar partido para arrancar el feed de demo.',
  liveHint: 'Esperando el primer insight del partido.',
  h1: '1.er tiempo', h2: '2.º tiempo', ft: 'Final', onAir: 'Al aire',
  feed: 'Feed de insights',
  feedTip: 'Haz clic en una tarjeta para previsualizarla, o arrástrala al lugar que quieras. J / K para moverte entre tarjetas.',
  waiting: 'En espera', empty: 'Las tarjetas aparecerán aquí a medida que avancen los partidos.',
  emptyFilter: 'Aún no hay tarjetas de este partido.', emptyFocus: 'Aún no hay tarjetas para este enfoque.', cards: 'tarjetas',
  games: 'Filtrar por partido', allGames: 'Todos', focus: 'Enfoque', focusNone: 'Sin enfoque', teams: 'Equipos', players: 'Jugadores',
  dragTo: 'Arrastra a la pantalla', release: 'Suelta para colocar',
  editCard: 'Editor de tarjeta', headline: 'Titular', body: 'Texto', size: 'Tamaño', small: 'Pequeño', medium: 'Mediano', large: 'Grande',
  removePrev: 'Quitar tarjeta de la vista previa', removed: 'Tarjeta quitada de la vista previa',
  move: 'Mover tarjeta', arrowsMove: 'Arrástrala a cualquier lugar de la pantalla o usa las flechas. Mantén Shift para pasos más grandes.',
  bPreview: 'Vista previa', bLive: 'En vivo', liveIn: 'En vivo en',
  jersey: 'número de camiseta', player: 'Jugador', team: 'Equipo',
  resizeW: 'Cambiar ancho', resizeH: 'Cambiar alto', resizeXY: 'Cambiar ancho y alto',
  arrowsW: 'Usa las flechas izquierda y derecha.', arrowsH: 'Usa las flechas arriba y abajo.', arrowsXY: 'Usa las flechas.',
  control: 'Control de emisión', offAir: 'Fuera del aire', selectHint: 'Haz clic o arrastra una tarjeta del feed a la pantalla.',
  ready: 'Vista previa · no en vivo', editHint: 'Arrastra para ubicarla · clic en el texto para editar · × para quitarla',
  nextReady: 'Siguiente tarjeta lista en vista previa',
  goLive: 'Enviar a', replace: 'Reemplazar en', pull: 'Retirar del aire', cancel: 'Cancelar', goNow: 'Enviar ya',
  goingLive: 'Sale al aire en', secs: 's', sendMsg: 'Sale al aire en 5 segundos. Pulsa Escape para cancelar.',
  cancelMsg: 'Cancelado. La tarjeta volvió a la pantalla para editarla.', pulled: 'Tarjeta retirada del aire',
  placed: 'Tarjeta colocada en pantalla',
  live: 'En vivo', salience: 'Relevancia', new: 'Nueva', toastTitle: 'La tarjeta está al aire en',
  shortcuts: 'J / K mover · Enter al aire · Esc cancelar o retirar',
  feedConnecting: 'Conectando con el feed en vivo…', feedError: 'Feed en vivo no disponible. Reintentando…',
  topics: { goal: 'Gol', passing: 'Construcción', duels: 'Duelos', discipline: 'Disciplina', setpiece: 'Balón parado', keeper: 'Portería' },
}

export const STRINGS: Record<Lang, Strings> = { en, es }

/** Live cards use signal kinds as topics; unknown ones are shown humanized ("pass_streak" → "Pass streak"). */
export function topicLabel(t: Strings, topic: string): string {
  const known = t.topics[topic]
  if (known) return known
  const words = topic.replace(/[_-]+/g, ' ').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export const minutes = (seconds: number) => `${Math.floor(seconds / 60)}’`
