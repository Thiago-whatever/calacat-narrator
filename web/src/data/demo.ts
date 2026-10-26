// Fictional demo fixtures from the design prototype (DOCS/design.md). Not real clubs or players.
import type { FeedCard, Match, Output, Player, Team } from '../types'

export const DEMO_FULL_TIME = 5400

export const demoTeams: Record<string, Team> = {
  rio: { id: 'rio', name: 'Ríos FC', short: 'RÍO', color: '#1e5bb8', ink: '#ffffff', soft: '#dbe7fb' },
  nor: { id: 'nor', name: 'Atlético Norte', short: 'NOR', color: '#c2540a', ink: '#ffffff', soft: '#fbe3d2' },
  sol: { id: 'sol', name: 'Puerto Sol', short: 'SOL', color: '#f2c230', ink: '#1a1a1a', soft: '#fdf1c6' },
  val: { id: 'val', name: 'Valle Real', short: 'VAL', color: '#6b3fa0', ink: '#ffffff', soft: '#e8dff4' },
}

export const demoMatches: Record<string, Match> = {
  m1: { id: 'm1', home: 'rio', away: 'nor' },
  m2: { id: 'm2', home: 'sol', away: 'val' },
}

export const demoOutputs: Output[] = [
  { id: 'o1', name: 'TV 1', match: 'm1' },
  { id: 'o2', name: 'TV 2', match: 'm2' },
  { id: 'o3', name: 'Stream', match: 'm1' },
]

const P = (id: string, name: string, num: number, team: string): Player => ({ id, name, num, team })
const martin = P('martin', 'Martín', 1, 'rio')
const rivas = P('rivas', 'Rivas', 9, 'rio')
const duarte = P('duarte', 'Duarte', 11, 'rio')
const ortega = P('ortega', 'Ortega', 6, 'nor')
const ibarra = P('ibarra', 'Ibarra', 10, 'sol')
const camacho = P('camacho', 'Camacho', 7, 'val')
const soto = P('soto', 'Soto', 13, 'val')

export const demoPlayers: Player[] = [martin, rivas, duarte, ortega, ibarra, camacho, soto]

const spec = {
  passing: { en: 'Build-up & Passing', es: 'Construcción y pase' },
  goal: { en: 'Goal & Shot', es: 'Gol y remate' },
  duels: { en: 'Duels & Pressing', es: 'Duelos y presión' },
  setpiece: { en: 'Set Pieces', es: 'Balón parado' },
}

export const demoCards: FeedCard[] = [
  { id: 'c1', match: 'm1', team: 'rio', clock: 740, topic: 'passing', critical: false, salience: 0.62, specialist: spec.passing,
    text: { en: { h: '14 passes, no way through', b: 'Ríos strung together 14 completed passes, their longest move of the half, and pulled Norte’s midfield apart.' },
      es: { h: '14 pases sin respiro', b: 'Ríos encadenó 14 pases completados, su jugada más larga del primer tiempo, y abrió el mediocampo de Norte.' } } },
  { id: 'b1', match: 'm2', team: 'sol', player: ibarra, clock: 900, topic: 'goal', critical: true, salience: 0.9, specialist: spec.goal,
    text: { en: { h: 'Ibarra curls in a free kick', b: 'From 24 metres over the wall: his third direct free-kick goal this season.' },
      es: { h: 'Ibarra la clava de tiro libre', b: 'Desde 24 metros por encima de la barrera: su tercer gol de tiro libre directo en la temporada.' } } },
  { id: 'c2', match: 'm1', team: 'rio', player: rivas, clock: 1385, topic: 'goal', critical: true, salience: 0.96, specialist: spec.goal,
    text: { en: { h: 'Rivas opens the scoring', b: 'A 104 km/h finish from a 0.74 xG chance, the clearest opening of the match so far.' },
      es: { h: 'Rivas abre el marcador', b: 'Remate a 104 km/h desde una ocasión de 0,74 xG, la más clara del partido hasta ahora.' } } },
  { id: 'c3', match: 'm1', team: 'nor', clock: 1870, topic: 'duels', critical: false, salience: 0.55, specialist: spec.duels,
    text: { en: { h: 'Norte own the middle', b: 'Away have won 9 of the last 12 duels in central areas, forcing Ríos wide.' },
      es: { h: 'Norte manda en el medio', b: 'El visitante ganó 9 de los últimos 12 duelos en zona central y obliga a Ríos a ir por fuera.' } } },
  { id: 'b2', match: 'm2', team: 'val', player: soto, clock: 2050, topic: 'keeper', critical: false, salience: 0.6, specialist: spec.goal,
    text: { en: { h: 'Soto stands tall', b: 'Three saves inside the box already, two of them from point-blank range.' },
      es: { h: 'Soto se agiganta', b: 'Ya suma tres atajadas dentro del área, dos de ellas a quemarropa.' } } },
  { id: 'c4', match: 'm1', team: 'nor', player: ortega, clock: 2300, topic: 'discipline', critical: false, salience: 0.71, specialist: spec.duels,
    text: { en: { h: 'Ortega on thin ice', b: 'Booked for his third foul in ten minutes. One more mistimed challenge and he risks a second yellow.' },
      es: { h: 'Ortega, al límite', b: 'Amonestado por su tercera falta en diez minutos. Una entrada más a destiempo y se arriesga a la segunda amarilla.' } } },
  { id: 'c5', match: 'm1', team: 'nor', clock: 2690, topic: 'setpiece', critical: false, salience: 0.58, specialist: spec.setpiece,
    text: { en: { h: 'Corners are Norte’s best weapon', b: 'Six corners so far, and four found a first contact inside the six-yard box.' },
      es: { h: 'Los córners, el arma de Norte', b: 'Seis córners hasta ahora, y cuatro encontraron un primer contacto dentro del área chica.' } } },
  { id: 'c6', match: 'm1', team: 'rio', player: martin, clock: 3135, topic: 'keeper', critical: false, salience: 0.78, specialist: spec.goal,
    text: { en: { h: 'Martín keeps Ríos ahead', b: 'His fifth save of the night, this one from a 0.41 xG header at the near post.' },
      es: { h: 'Martín sostiene a Ríos', b: 'Su quinta atajada de la noche, esta vez ante un cabezazo de 0,41 xG en el primer palo.' } } },
  { id: 'b3', match: 'm2', team: 'val', clock: 3300, topic: 'duels', critical: false, salience: 0.57, specialist: spec.duels,
    text: { en: { h: 'Valle Real win it back high', b: 'Seven recoveries in the final third since the break, the most of any team tonight.' },
      es: { h: 'Valle Real recupera arriba', b: 'Siete recuperaciones en el último tercio desde el descanso, la mayor cifra de la noche.' } } },
  { id: 'c7', match: 'm1', team: 'nor', clock: 4050, topic: 'passing', critical: false, salience: 0.66, specialist: spec.passing,
    text: { en: { h: 'All the ball, little danger', b: 'Norte have had 71% of possession in the last ten minutes but only 0.12 xG to show for it.' },
      es: { h: 'Mucho balón, poco peligro', b: 'Norte tuvo el 71% de la posesión en los últimos diez minutos, pero apenas 0,12 xG.' } } },
  { id: 'b4', match: 'm2', team: 'val', player: camacho, clock: 4600, topic: 'goal', critical: true, salience: 0.93, specialist: spec.goal,
    text: { en: { h: 'Camacho levels it', b: 'A first-time finish from a 0.52 xG cutback. Valle Real are back on terms.' },
      es: { h: 'Camacho empata', b: 'Definición de primera tras un pase atrás de 0,52 xG. Valle Real vuelve a igualar.' } } },
  { id: 'b5', match: 'm2', team: 'sol', player: ibarra, clock: 5000, topic: 'passing', critical: false, salience: 0.64, specialist: spec.passing,
    text: { en: { h: 'Ibarra pulls the strings', b: 'Involved in 38% of Puerto Sol’s passes since the hour mark.' },
      es: { h: 'Ibarra mueve los hilos', b: 'Participa en el 38% de los pases de Puerto Sol desde el minuto 60.' } } },
  { id: 'c8', match: 'm1', team: 'rio', player: duarte, clock: 5280, topic: 'goal', critical: true, salience: 0.97, specialist: spec.goal,
    text: { en: { h: 'Ríos seal it on the break', b: 'Nine seconds from their own box: four passes, 78 metres, and a calm finish from Duarte.' },
      es: { h: 'Ríos lo sentencia a la contra', b: 'Nueve segundos desde su propia área: cuatro pases, 78 metros y una definición tranquila de Duarte.' } } },
]
