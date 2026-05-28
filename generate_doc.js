#!/usr/bin/env node
/**
 * Okolica.ai - Generator Word dokumenta (tablice 2.1 - 2.11)
 * Poziva se: node generate_doc.js <input.json> <output.docx>
 */

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, BorderStyle, WidthType, ShadingType, HeadingLevel,
  VerticalAlign
} = require('docx');

const inputPath  = process.argv[2];
const outputPath = process.argv[3];

if (!inputPath || !outputPath) {
  console.error('Uporaba: node generate_doc.js input.json output.docx');
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(inputPath, 'utf8'));

// ── Helpers ───────────────────────────────────────────────────────
const HEADER_COLOR = 'D9E1F2';
const BORDER = { style: BorderStyle.SINGLE, size: 1, color: '999999' };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };
const TW = 9360; // table width DXA (A4 with 1.5cm margins each side)
const C1 = 2200; // label column
const C2 = TW - C1; // content column

function txt(text, opts = {}) {
  return new TextRun({ text: String(text || ''), font: 'Arial', size: 22, ...opts });
}

function bold(text) { return txt(text, { bold: true }); }

function para(children, opts = {}) {
  if (typeof children === 'string') children = [txt(children)];
  return new Paragraph({ children, spacing: { after: 60 }, ...opts });
}

function headerPara(text) {
  return new Paragraph({
    children: [bold(text)],
    spacing: { before: 200, after: 100 },
    heading: HeadingLevel.HEADING_2,
  });
}

function titlePara(text) {
  return new Paragraph({
    children: [new TextRun({ text, font: 'Arial', size: 28, bold: true })],
    spacing: { before: 240, after: 120 },
    heading: HeadingLevel.HEADING_1,
  });
}

function cell(content, isHeader = false, colWidth = C2) {
  const children = typeof content === 'string'
    ? content.split('\n').map(line => para(line || ' '))
    : (Array.isArray(content) ? content : [para(String(content))]);
  return new TableCell({
    borders: BORDERS,
    width: { size: colWidth, type: WidthType.DXA },
    shading: isHeader
      ? { fill: HEADER_COLOR, type: ShadingType.CLEAR }
      : { fill: 'FFFFFF', type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: VerticalAlign.TOP,
    children,
  });
}

function twoColTable(tableNum, tableTitle, rows) {
  const headerRow = new TableRow({
    children: [
      new TableCell({
        columnSpan: 2,
        borders: BORDERS,
        width: { size: TW, type: WidthType.DXA },
        shading: { fill: '2E5EA8', type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({
          children: [new TextRun({ text: `Tablica ${tableNum}. ${tableTitle}`, font: 'Arial', size: 22, bold: true, color: 'FFFFFF' })],
          spacing: { after: 0 },
        })],
      }),
    ],
  });

  const dataRows = rows.map(([label, content]) =>
    new TableRow({
      children: [
        cell(label, true, C1),
        cell(content, false, C2),
      ],
    })
  );

  return new Table({
    width: { size: TW, type: WidthType.DXA },
    columnWidths: [C1, C2],
    rows: [headerRow, ...dataRows],
  });
}

// ── Podaci iz JSON-a ──────────────────────────────────────────────
const d = data;
const addr = d.address || '';
const lat  = d.lat ? parseFloat(d.lat).toFixed(5) : '';
const lon  = d.lon ? parseFloat(d.lon).toFixed(5) : '';
const radius = d.radius || 500;

// Tablice s Claude sadržajem
const t21 = d.tables?.t21 || {};
const t22 = d.tables?.t22 || {};
const t25 = d.tables?.t25 || {};
const t27 = d.tables?.t27 || {};
const t210 = d.tables?.t210 || {};
const t211 = d.tables?.t211 || {};

// ── Statični tekstovi ────────────────────────────────────────────
const st = data.static || {};

const T23_MATERIJAL = st.t23_mat || 'Hodne i tranzitne površine: betonski opločnici i asfaltni slojevi.\nUrbana oprema: čelik i drvo (klupe, koševi za otpad).';
const T23_NAGIB     = st.t23_nagib || 'Nagib terena utvrđuje se terenskim pregledom lokacije.';
const T23_ELEMENTI  = st.t23_elementi || 'Postojeći elementi utvrđuju se terenskim pregledom.';
const T24_ELEKTRIKA = st.t24_el || 'Električne instalacije lokacije uključuju sustav javne rasvjete s pripadajućom infrastrukturom.';
const T24_OSTALO    = st.t24_ost || 'Ostale instalacije utvrđuju se uvidom u projektnu dokumentaciju.';
const T26_PROCESI   = st.t26 || 'Posebnih procesa i postupaka bitnih za sigurnost lokacije nema.';
const T28_TJELESNA  = st.t28_tjelesna || 'U lokaciji se trenutno ne provodi tjelesna zaštita.';
const T28_TEHNICKA  = st.t28_tehnicka || 'U lokaciji se trenutno ne provodi tehnička zaštita.';
const T28_ORG       = st.t28_org || 'Za lokaciju nisu definirane posebne organizacijske mjere zaštite.';
const T29_POSTOJECI = st.t29_postojeci || 'U lokaciji se ne provodi tehnička zaštita.';
const T29_DOK       = st.t29_dok || 'Ne postoji dokumentacija postojećih sustava tehničke zaštite.';

// ── Zakoni ────────────────────────────────────────────────────────

const ZAKONI = [
  'Zakon o privatnoj zaštiti (NN 16/20, 114/22)',
  'Zakon o prekršajima protiv javnog reda i mira (NN 41/77, 52/87, 47/89, 55/89, 05/90, 30/90, 47/90, 29/94, 114/22, 47/23)',
  'Zakon o sigurnosti prometa na cestama (NN 67/08, 48/10, 74/11, 80/13, 158/13, 92/14, 64/15, 108/17, 70/19, 42/20, 85/22, 114/22, 133/23, 145/24)',
  'Kazneni zakon (NN 125/11, 144/12, 56/15, 61/15, 101/17, 118/18, 126/19, 84/21, 114/22, 114/23, 36/24, 136/25)',
  'Zakon o cestama (NN 84/11, 22/13, 54/13, 148/13, 92/14, 110/19, 144/21, 114/22, 04/23, 133/23, 156/25)',
  'Pravilnik o uvjetima i načinu provedbe tehničke zaštite (NN 198/03)',
  'Pravilnik o načinu i uvjetima obavljanja poslova privatne zaštite na javnim površinama (NN 36/12)',
];

// ── Izgradnja dokumenta ───────────────────────────────────────────
function buildDoc() {
  const children = [];

  // Naslov
  children.push(titlePara('Procjena ugroženosti — Opis lokacije i okolice'));
  children.push(para([
    bold('Adresa/lokacija: '), txt(addr),
  ]));
  children.push(para([
    bold('Koordinate: '), txt(`${lat}, ${lon}`),
  ]));
  children.push(para([
    bold('Radijus analize: '), txt(`${radius}m`),
  ]));
  children.push(para(' '));

  // Popis zakona
  children.push(headerPara('Popis primijenjenih zakona, pravilnika, propisa i normi'));
  ZAKONI.forEach(z => children.push(para(z)));
  children.push(para(' '));

  // Opis lokacije naslov
  children.push(headerPara('Opis lokacije'));
  children.push(para(' '));

  // 2.1
  children.push(twoColTable('2.1', 'Opis lokacije', [
    ['Opis lokacije:', t21.opis_lokacije || ''],
    ['Opis okolnih građevina, površina i okoliša:', t21.opis_okolnih || ''],
    ['Načini pristupa:', t21.nacini_pristupa || ''],
    ['Frekvencija prometa radnim danom, vikendom, noću:', t21.frekvencija || ''],
    ['Stanje kriminaliteta u okolnom prostoru:', t21.kriminalitet || ''],
  ]));
  children.push(para(' '));

  // 2.2
  children.push(twoColTable('2.2', 'Osnovne karakteristike', [
    ['Prostorna organiziranost:', t22.prostorna || ''],
    ['Veličina i namjena:', t22.velicina || ''],
  ]));
  children.push(para(' '));

  // 2.3
  children.push(twoColTable('2.3', 'Građevinske karakteristike', [
    ['Vrsta materijala:', T23_MATERIJAL],
    ['Nagib terena:', T23_NAGIB],
    ['Postojeći elementi javne površine (stepenice, podvožnjaci, objekti) i dr.:', T23_ELEMENTI],
  ]));
  children.push(para(' '));

  // 2.4
  children.push(twoColTable('2.4', 'Instalacije', [
    ['Električne instalacije:', T24_ELEKTRIKA],
    ['Ostale instalacije (plin, voda, kanalizacija):', T24_OSTALO],
  ]));
  children.push(para(' '));

  // 2.5
  children.push(twoColTable('2.5', 'Namjena', [
    ['Opća namjena:', t25.opca_namjena || ''],
    ['Namjena pojedinih prostora:', t25.namjena_prostora || ''],
    ['Radno vrijeme:', t25.radno_vrijeme || ''],
    ['Put kretanja osoba i vozila:', t25.put_kretanja || ''],
    ['Način zaključavanja prostora:', t25.zakljucavanje || ''],
  ]));
  children.push(para(' '));

  // 2.6
  children.push(twoColTable('2.6', 'Radni procesi', [
    ['Popis i opis procesa i postupaka bitnih za sigurnost:', T26_PROCESI],
  ]));
  children.push(para(' '));

  // 2.7
  children.push(twoColTable('2.7', 'Vrsta i visina vrijednosti', [
    ['Vrste vrijednosti:', t27.vrste || ''],
    ['Visina vrijednosti:', t27.visina || ''],
    ['Način čuvanja vrijednosti:', t27.cuvanje || ''],
  ]));
  children.push(para(' '));

  // 2.8
  children.push(twoColTable('2.8', 'Organizacija sigurnosti', [
    ['Tjelesna zaštita:', T28_TJELESNA],
    ['Tehnička zaštita:', T28_TEHNICKA],
    ['Organizacijske mjere:', T28_ORG],
  ]));
  children.push(para(' '));

  // 2.9
  children.push(twoColTable('2.9', 'Stanje dokumentiranosti', [
    ['Postojeći sustavi zaštite:', T29_POSTOJECI],
    ['Dokumentiranost postojećih sustava tehničke zaštite:', T29_DOK],
  ]));
  children.push(para(' '));

  // 2.10
  children.push(twoColTable('2.10', 'Uočeni nedostaci', [
    ['Uočeni nedostaci:', t210.nedostaci || ''],
  ]));
  children.push(para(' '));

  // 2.11
  children.push(twoColTable('2.11', 'Kritične točke i ugroženi prostori', [
    ['Kritične točke:', t211.kriticne || ''],
    ['Ugroženi prostori:', t211.ugrozeni || ''],
  ]));

  const doc = new Document({
    styles: {
      default: {
        document: { run: { font: 'Arial', size: 22 } },
      },
      paragraphStyles: [
        {
          id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
          run: { size: 28, bold: true, font: 'Arial', color: '1F3864' },
          paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 },
        },
        {
          id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
          run: { size: 24, bold: true, font: 'Arial', color: '2E5EA8' },
          paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 },
        },
      ],
    },
    sections: [{
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1134, right: 850, bottom: 1134, left: 850 },
        },
      },
      children,
    }],
  });

  return doc;
}

const doc = buildDoc();
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outputPath, buf);
  console.log('OK:' + outputPath);
}).catch(err => {
  console.error('ERROR:' + err.message);
  process.exit(1);
});
