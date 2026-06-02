/**
 * cars-data.js — v4
 *
 * Vehicle catalog data is now served by the catalog API (/api/catalog/).
 * Use the functions from api.js instead of static data where possible:
 *
 *   getMakes()                     → GET /api/catalog/makes/
 *   getModels(makeId)              → GET /api/catalog/models/?make_id=
 *   getGenerations(modelId)        → GET /api/catalog/generations/?model_id=
 *   getModifications(generationId) → GET /api/catalog/modifications/?generation_id=
 *
 * The static MODELS_BY_MAKE export below is kept for backwards compatibility
 * with any existing components that use it directly. New code should call the
 * API functions from api.js.
 */

export { getMakes, getModels, getGenerations, getModifications } from "./api.js";

// Legacy static fallback — use catalog API for production data
export const MODELS_BY_MAKE = {
  "Acura": ["ILX", "Integra", "MDX", "NSX", "RDX", "TL", "TLX", "TSX"],
  "BMW": ["128i", "228i", "318i", "320i", "325i", "328i", "330i", "335i", "340i", "428i", "430i", "435i", "440i", "528i", "530i", "535i", "540i", "M3", "M4", "M5", "X1", "X2", "X3", "X4", "X5", "X6", "X7"],
  "Chevy": ["Camaro", "Colorado", "Corvette", "Equinox", "Malibu", "Silverado 1500", "Silverado 2500", "Suburban", "Tahoe", "Traverse"],
  "Dodge": ["Challenger", "Charger", "Dart", "Durango", "Ram 1500"],
  "Ford": ["Bronco", "Edge", "Escape", "Expedition", "Explorer", "F-150", "F-250", "Fusion", "Mustang", "Ranger"],
  "GMC": ["Acadia", "Canyon", "Sierra 1500", "Sierra 2500", "Terrain", "Yukon"],
  "Honda": ["Accord", "CRV", "Civic", "HR-V", "Odyssey", "Passport", "Pilot", "Ridgeline"],
  "Hyundai": ["Elantra", "Ioniq 5", "Kona", "Palisade", "Santa Fe", "Sonata", "Tucson"],
  "Jeep": ["Cherokee", "Compass", "Gladiator", "Grand Cherokee", "Renegade", "Wrangler"],
  "Kia": ["Carnival", "EV6", "Forte", "K5", "Niro", "Seltos", "Sorento", "Soul", "Sportage", "Telluride"],
  "Lexus": ["ES350", "GX460", "IS250", "IS350", "NX300", "RX350", "UX 200"],
  "Mazda": ["CX-3", "CX-30", "CX-5", "CX-9", "Mazda3", "Mazda6", "MX-5 Miata"],
  "Mercedes": ["C Class", "E Class", "GLC Class", "GLE Class", "GLS Class", "S Class"],
  "Nissan": ["Altima", "Frontier", "Kicks", "Leaf", "Murano", "Pathfinder", "Rogue", "Sentra", "Titan", "Xterra"],
  "Subaru": ["Ascent", "BRZ", "Crosstrek", "Forester", "Impreza", "Legacy", "Outback", "WRX"],
  "Tesla": ["Cybertruck", "Model 3", "Model S", "Model X", "Model Y"],
  "Toyota": ["4Runner", "Camry", "Corolla", "Highlander", "Land Cruiser", "Prius", "RAV4", "Sequoia", "Sienna", "Tacoma", "Tundra"],
  "Volkswagen": ["Atlas", "Golf", "ID.4", "Jetta", "Passat", "Taos", "Tiguan"],
  "Volvo": ["S60", "V60", "XC40", "XC60", "XC90"],
};

export const MAKES = Object.keys(MODELS_BY_MAKE);
