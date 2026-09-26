/**
 * Estimated share of each country's publicly listed procurement opportunities that Signal's
 * enabled sources reach, with the main listings it does not collect. Reviewed by hand from
 * source volumes; the basis for every figure is in docs/market-coverage-2026-09-23.md.
 */
export const coverageReview: {
  reviewed: string
  countries: Record<string, { estimate: number; missing: string[] }>
} = {
  reviewed: '2026-09-23',
  countries: {
    AT: { estimate: 53, missing: ['ANKÖ', 'auftrag.at'] },
    BE: { estimate: 41, missing: ['e-Procurement (BDA)'] },
    BG: { estimate: 36, missing: ['CAIS EOP'] },
    CA: { estimate: 7, missing: ['Ontario portals', 'SEAO'] },
    CH: { estimate: 48, missing: ['simap.ch', 'Cantonal gazettes'] },
    CY: { estimate: 32, missing: ['eprocurement.gov.cy'] },
    CZ: { estimate: 28, missing: ['Buyer profiles (E-ZAK, NEN)'] },
    DE: { estimate: 93, missing: ['Local portals'] },
    DK: { estimate: 71, missing: ['Byggefakta / Udbudsvagten', 'udbud.dk'] },
    EE: { estimate: 24, missing: ['Riigihangete register'] },
    ES: { estimate: 80, missing: ['PLACSP regional feed'] },
    FI: { estimate: 47, missing: ['Hilma', 'Tarjouspalvelu'] },
    FR: { estimate: 39, missing: ['BOAMP', 'Buyer profiles'] },
    GB: { estimate: 85, missing: ['Buyer portals', 'eTendersNI'] },
    GR: { estimate: 12, missing: ['KIMDIS / ESIDIS', 'Diavgeia'] },
    HR: { estimate: 18, missing: ['EOJN RH'] },
    HU: { estimate: 45, missing: ['EKR'] },
    IE: { estimate: 55, missing: ['eTenders', 'Semi-state portals'] },
    IS: { estimate: 43, missing: ['Útboðsvefur', 'Buyer websites'] },
    IT: { estimate: 31, missing: ['ANAC PVL', 'MePA'] },
    LT: { estimate: 16, missing: ['CVP IS'] },
    LU: { estimate: 70, missing: ['Portail des marchés publics'] },
    LV: { estimate: 33, missing: ['IUB / EIS'] },
    MT: { estimate: 13, missing: ['ePPS'] },
    NL: { estimate: 86, missing: ['TenderNed', 'Negometrix / CTM'] },
    NO: { estimate: 57, missing: ['Doffin', 'Mercell / TendSign'] },
    PL: { estimate: 15, missing: ['BZP e-Zamówienia', 'Buyer platforms'] },
    PT: { estimate: 38, missing: ['Portal BASE', 'Diário da República'] },
    RO: { estimate: 37, missing: ['SICAP'] },
    SE: { estimate: 58, missing: ['Mercell', 'e-Avrop'] },
    SI: { estimate: 41, missing: ['e-JN portal'] },
    SK: { estimate: 18, missing: ['eks.sk', 'ÚVO Vestník'] },
    US: { estimate: 10, missing: ['State and local portals', 'DLA DIBBS'] },
  },
}
