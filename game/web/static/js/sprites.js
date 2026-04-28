/**
 * Pixel-art sprite system.
 * Each sprite row is a 16-char string; each char maps to a hex colour via CM.
 * '.' = transparent. Scale factor applied at draw time.
 */

// ─── Colour map (single-char → hex) ─────────────────────────────────────────
const CM = {
  '.': null,
  // skin
  's': '#f5c5a3', 'S': '#c8825a',
  // warrior blues
  'h': '#7a9fb5', 'a': '#3a6e9b', 'A': '#2a5278', 'l': '#2c4a68',
  // ranger greens
  'g': '#6aaa50', 'G': '#3d7833', 'L': '#2e5227',
  // mage purples
  'm': '#8840b0', 'M': '#5a2e78', 'H': '#aa60d8',
  // ironman darks
  'i': '#5a5a6a', 'I': '#383848', 'J': '#202028',
  // weapons
  'w': '#d8dde8', 'W': '#9aa4b8', 'b': '#8b5e2a', 'f': '#a060d0', 'F': '#44ddaa',
  // hair
  'r': '#3a2010', 'R': '#c8a020',
  // goblin
  'o': '#52aa44', 'O': '#338833', 'e': '#ffee00', 'c': '#7a4422',
  // boar
  'B': '#9a7050', 'D': '#5c3820', 'N': '#f08060',
  // skeleton
  'k': '#e8e4cc', 'K': '#b0a888', 'E': '#ff4400', 'q': '#888880',
  // dark mage
  'd': '#281440', 'p': '#b030e8', 'P': '#601870',
  // boss gold
  'C': '#fce068', 'Q': '#d8a830',
  // spider
  'x': '#303030', 'X': '#181818', 'y': '#ff2020',
  // tiles — use chars not shared with sprites above
  'T': '#d4a96a', 't': '#b08040',          // sand light / dark
  'n': '#7a7264', '2': '#4a4638', '3': '#9a928a',  // stone med / dark / light
  'v': '#3a8c3a', 'V': '#2a6c2a',          // grass light / dark
  'Z': '#1a5a1a', 'z': '#7a5030',          // tree / dirt
};

// ─── Sprite data (16 cols × 16 rows each) ────────────────────────────────────
const SD = {
  warrior: [
    '......hhhhhh....',
    '.....hhhhhhhh...',
    '.....hssssshh...',
    '.....hSsssSh....',
    '......ssrss.....',
    '...waaaaaaaaA...',
    '...waaAaAaaAA...',
    '...waaaaaaaaA...',
    '....AaAAAaAA....',
    '.....lllllll....',
    '.....llllWll....',
    '.....lllllll....',
    '.....ll...ll....',
    '.....ll...ll....',
    '.....AA...AA....',
    '................',
  ],
  ranger: [
    '......gggggg....',
    '.....gggggggg...',
    '.....gsssssgg...',
    '.....GsssSSg....',
    '......ssrss.....',
    '...bGGGGGGGGG...',
    '...bbGGgGGGGG...',
    '...bGGGGGGGGG...',
    '.....GGGGGgGG...',
    '.....LLLLLLL....',
    '.....LLLlLLL....',
    '.....LLLLLLL....',
    '.....LL...LL....',
    '.....LL...LL....',
    '.....GG...GG....',
    '................',
  ],
  mage: [
    '......HHHmm.....',
    '.....HHHHmmm....',
    '.....HssssHm....',
    '.....mssSSm.....',
    '....fmsrssm.....',
    '...FFmmmmmmmm...',
    '...F.mMmMmmmm...',
    '...FFmmmmmmmm...',
    '.....MmMMmMmm...',
    '.....mmmmmmmm...',
    '.....MMmmMmmm...',
    '.....mmmmmm.....',
    '.....mm...mm....',
    '.....mm...mm....',
    '.....MM...MM....',
    '................',
  ],
  ironman: [
    '....iiiiiiii....',
    '...iiiiiiiiI....',
    '...iiIIIIiii....',
    '...iiIIIIiIi....',
    '....iIiIIii.....',
    '...iIIIIIIIi....',
    '...iIIIiIIIi....',
    '...iIIIIIIIi....',
    '....IIIiIIII....',
    '....JJJJJJJJ....',
    '....JJJjJJJJ....',
    '....JJJJJJJJ....',
    '....JJ...JJ.....',
    '....JJ...JJ.....',
    '....II...II.....',
    '................',
  ],
  goblin: [
    '......oooooo....',
    '.....ooOooooo...',
    '.....ooeeoooo...',
    '....OooooooOo...',
    '.....oooooo.....',
    '.....occccoo....',
    '....occcccoo....',
    '.....occcoo.....',
    '.....cccccc.....',
    '.....oooooo.....',
    '.....oOoooO.....',
    '.....oooooo.....',
    '.....oo...oo....',
    '.....oo...oo....',
    '.....oO...Oo....',
    '................',
  ],
  stone_goblin: [
    '......OOOOOO....',
    '.....OOOOOOO....',
    '.....OOssOOO....',
    '....OOOooOOO....',
    '.....OOOOOO.....',
    '.....OccOOOO....',
    '....OccccOOO....',
    '.....OccOOO.....',
    '.....ccOccc.....',
    '.....OOOOOO.....',
    '.....OOOoOO.....',
    '.....OOOOOO.....',
    '.....OO...OO....',
    '.....OO...OO....',
    '.....OO...OO....',
    '................',
  ],
  forest_boar: [
    '................',
    '..BBBBBBB.......',
    '.BBBBBBBBDD.....',
    '.NBBBBBBDDD.....',
    '.NBBBBBBBBBB....',
    '..BBBBBBBBBBB...',
    '..BBBBBBBBBBB...',
    '..BBBBBBBBBB....',
    '...BBBBBBBBB....',
    '...BBDBBBBB.....',
    '....BBBBBB......',
    '....BB...BB.....',
    '....BB...BB.....',
    '....DB...DB.....',
    '................',
    '................',
  ],
  skeleton_archer: [
    '......kkkkkk....',
    '.....kkkkkkk....',
    '.....kEkkkEk....',
    '....kkkkkkkkk...',
    '.....kkkkkk.....',
    '...b.kkKkkkk....',
    '...bbkkkKkkkk...',
    '...b.kkkkKkkk...',
    '.....KkKkKkKk...',
    '.....qqqqqq.....',
    '.....qqKqqqq....',
    '.....qqqqqq.....',
    '.....kk...kk....',
    '.....kk...kk....',
    '.....KK...KK....',
    '................',
  ],
  dark_mage: [
    '......ppppp.....',
    '.....ppppppp....',
    '.....psssspP....',
    '.....dssssd.....',
    '....ddrsssd.....',
    '....dddPdddd....',
    '....dddddddd....',
    '....dPdddddd....',
    '.....PPddPPd....',
    '.....ddddddd....',
    '.....dPddPdd....',
    '......dddd......',
    '......dd..dd....',
    '......dd..dd....',
    '......dd..dd....',
    '................',
  ],
  goblin_king: [
    '....CCCCCCCCC...',
    '...CQQQQQQQQCo..',
    '...CQooooooQC...',
    '...CooooeooC....',
    '....oooooooo....',
    '...ocCQQQCcoo...',
    '..ocCQQQQQCco...',
    '..oCCCQQQCCCo...',
    '...CoCQQQCoC....',
    '...oQQQoQQQo....',
    '...oQQoQQQQo....',
    '....QQQoQQQ.....',
    '....QQ...QQ.....',
    '....QQ...QQ.....',
    '....QO...QO.....',
    '....oo...oo.....',
  ],
  rare_spider: [
    '....xx....xx....',
    '...xxx....xxx...',
    '....xx....xx....',
    '...xxx....xxx...',
    '....xxxxxxxx....',
    '...xxyExxEyxx...',
    '..xxxxxyyyyxxx..',
    '..xxxxxyyyyxxx..',
    '...xxxxXXXxxx...',
    '....xxxxxxxx....',
    '...xxx....xxx...',
    '....xx....xx....',
    '...xxx....xxx...',
    '....xx....xx....',
    '................',
    '................',
  ],
  elite_goblin: [
    '...QQOOOoQQQ....',
    '...QOOooooQQ....',
    '...QOoeeooQ.....',
    '..QOOooooOQ.....',
    '...QoooooQ......',
    '..QQccQQQQQ.....',
    '.QQccccQccQQ....',
    '.QQQcccccQQQ....',
    '..QQccccQQ......',
    '..QooooooQ......',
    '..QoooooQ.......',
    '..QQooQQ........',
    '..QQ..QQ........',
    '..QQ..QQ........',
    '..Qo..oQ........',
    '................',
  ],
};

// ─── Tile data (16 cols × 16 rows each) ──────────────────────────────────────
const TD = {
  grass: [
    'vvvvvvvvvvvvvvvv',
    'vvVvvvvVvvvvVvvv',
    'vvvvvvvvvvvvvvvv',
    'VvvvVvvvvVvvvvVv',
    'vvvvvvvvvvvvvvvv',
    'vvvVvvvvvvvVvvvv',
    'vvvvvvvvvvvvvvvv',
    'vVvvvvvVvvvvvVvv',
    'vvvvvvvvvvvvvvvv',
    'vvvVvvvvVvvvvvvv',
    'VvvvvvvvvvvvVvvv',
    'vvvvvvVvvvvvvvvv',
    'vvvVvvvvvvVvvvvv',
    'vvvvvvvvvvvvvvvv',
    'vVvvvvvvVvvvvVvv',
    'vvvvvvvvvvvvvvvv',
  ],
  stone_floor: [
    'nnnnnnnnnnnnnnnn',
    'n3nnnnnnnn3nnnnn',
    'n3nnnnnnnn3nnnnn',
    'n3nnnnnnnn3nnnnn',
    'n3nnnnnnnn3nnnnn',
    '2222222222222222',
    'nnnnnnnnnnnnnnnn',
    'nnnnnnnnnnnnnnnn',
    '2222222222222222',
    'n3nnnnnnnn3nnnnn',
    'n3nnnnnnnn3nnnnn',
    'n3nnnnnnnn3nnnnn',
    'n3nnnnnnnn3nnnnn',
    '2222222222222222',
    'nnnnnnnnnnnnnnnn',
    'nnnnnnnnnnnnnnnn',
  ],
  sand: [
    'TTTTTTTTTTTTTTTT',
    'TTtTTTTTTTtTTTTT',
    'TTTTTTTTTTTTtTTT',
    'TtTTTTTtTTTTTTTT',
    'TTTTTtTTTTTTtTTT',
    'TTTTTTTTtTTTTTTT',
    'TtTTTTTTTTtTTTTT',
    'TTTTTtTTTTTTTTTT',
    'TTTTTTTTTtTTtTTT',
    'TtTTTTTTTTTTTTTT',
    'TTTTTtTTTTTtTTTT',
    'TTTTTTTTtTTTTTTT',
    'TTTTTTTTTTTTTTtT',
    'TtTTTTtTTTTTTTTT',
    'TTTTTTTTTTtTTTTT',
    'TTTTTtTTTTTTTTTT',
  ],
  tree_bg: [
    'vZZvvZZZvvZZvvvv',
    'vZZZZZZZZZZZvvvv',
    'ZZZZZZzZZZZZZvvv',
    'ZZZZZZZZZZZZZvvv',
    'vZZZZZzZZZZZvvvv',
    'vvZZZZZZZZvvvvvv',
    'vvvZZZZZZvvvvvvv',
    'vvvvzzzvvvvvvvvv',
    'vvvvvvvvvvvvvvvv',
    'vvvZZZvvvZZZvvvv',
    'vvZZZZZvZZZZZvvv',
    'vZZZzZZZZZzZZvvv',
    'vZZZZZZZZZZZZvvv',
    'vvZZZZZZZZZZvvvv',
    'vvvvzzzvvvzzvvvv',
    'vvvvvvvvvvvvvvvv',
  ],
  dungeon_wall: [
    'nnnnnnnnnnnnnnnn',
    'n3nnnnnnn3nnnnnn',
    'nnnnnnnnnnnnnnnn',
    'nnnnn3nnnnnn3nnn',
    '2222222222222222',
    'n3nnnnnnnn3nnnnn',
    'nnnnnnnnnnnnnnnn',
    '22n22n22n22n22nn',
    '22n22n22n22n22nn',
    'nnnnnnnnnnnnnnnn',
    'n3nnnnnnnn3nnnnn',
    '2222222222222222',
    'nnnnnnnnnnnnnnnn',
    'nnn3nnnnnn3nnnnn',
    'nnnnnnnnnnnnnnnn',
    '2222222222222222',
  ],
};

// ─── Renderer ─────────────────────────────────────────────────────────────────
/**
 * Draw sprite rows at (x, y) with pixel scale.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string[]} rows
 * @param {number} x
 * @param {number} y
 * @param {number} scale   pixels per art-pixel (default 3)
 * @param {boolean} flipH  mirror horizontally
 */
function drawSprite(ctx, rows, x, y, scale = 3, flipH = false) {
  const h = rows.length;
  const w = rows[0].length;
  for (let row = 0; row < h; row++) {
    for (let col = 0; col < w; col++) {
      const color = CM[rows[row][col]];
      if (!color) continue;
      ctx.fillStyle = color;
      const px = flipH ? (w - 1 - col) : col;
      ctx.fillRect(x + px * scale, y + row * scale, scale, scale);
    }
  }
}

// Tiled background fill
function drawTiled(ctx, tileRows, canvasW, canvasH, scale = 2) {
  const tw = tileRows[0].length * scale;
  const th = tileRows.length * scale;
  for (let ty = 0; ty < canvasH; ty += th) {
    for (let tx = 0; tx < canvasW; tx += tw) {
      drawSprite(ctx, tileRows, tx, ty, scale);
    }
  }
}

// ─── Lookup tables ────────────────────────────────────────────────────────────
const MONSTER_SPRITE = {
  goblin:          'goblin',
  stone_goblin:    'stone_goblin',
  forest_boar:     'forest_boar',
  skeleton_archer: 'skeleton_archer',
  dark_mage:       'dark_mage',
  elite_goblin:    'elite_goblin',
  rare_spider:     'rare_spider',
  goblin_king:     'goblin_king',
  grondar:         'goblin_king',
  sylvara:         'dark_mage',
  zythera:         'skeleton_archer',
};

const ZONE_BG = {
  forest:    { floor: 'grass',       wall: 'tree_bg',      sky: '#1a3a1a', ground: '#2a5a2a' },
  dungeon_1: { floor: 'stone_floor', wall: 'dungeon_wall', sky: '#0a0a18', ground: '#1a1828' },
  dungeon_2: { floor: 'stone_floor', wall: 'dungeon_wall', sky: '#08081a', ground: '#181020' },
  swamp:     { floor: 'grass',       wall: 'tree_bg',      sky: '#0a1a08', ground: '#1a2a10' },
  desert:    { floor: 'sand',        wall: 'sand',         sky: '#3a2808', ground: '#c8a060' },
  mountain:  { floor: 'stone_floor', wall: 'dungeon_wall', sky: '#0c1020', ground: '#1a2030' },
  void:      { floor: 'stone_floor', wall: 'dungeon_wall', sky: '#04020c', ground: '#100818' },
  raid:      { floor: 'sand',        wall: 'dungeon_wall', sky: '#1e0c04', ground: '#a85020' },
};

const STYLE_SPRITE = { melee: 'warrior', range: 'ranger', magic: 'mage' };
