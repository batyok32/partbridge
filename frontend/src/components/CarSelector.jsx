"use client";

import { useEffect, useState } from "react";

import { getGenerations, getMakes, getModels, getModifications } from "@/lib/api";

const selectStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  color: "var(--text-primary)",
  padding: "10px 12px",
  fontSize: 13,
  outline: "none",
  fontFamily: "var(--ff-body)",
  width: "100%",
};

function Field({ label, children }) {
  return (
    <div style={{ flex: "1 1 140px", minWidth: 120 }}>
      {label && (
        <label style={{ display: "block", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 4 }}>
          {label}
        </label>
      )}
      {children}
    </div>
  );
}

export function buildCarPayload({ makeId, modelId, generationId, modificationId, year, makes, models, generations, modifications }) {
  const make = makes.find((m) => String(m.id) === String(makeId));
  const model = models.find((m) => String(m.id) === String(modelId));
  const gen = generations.find((g) => String(g.id) === String(generationId));
  const mod = modifications.find((m) => String(m.id) === String(modificationId));
  const codes = gen?.chassis_codes || [];
  const code = codes[0] || gen?.name || "";
  const displayParts = [String(year), make?.name, model?.name].filter(Boolean);
  if (code) displayParts.push(code);
  return {
    generationId: parseInt(generationId, 10),
    modificationId: modificationId ? parseInt(modificationId, 10) : null,
    year: parseInt(year, 10),
    makeId: make?.id,
    modelId: model?.id,
    makeName: make?.name || "",
    modelName: model?.name || "",
    generationName: gen?.name || "",
    generationLabel: gen?.display_label || "",
    displayLabel: displayParts.join(" "),
  };
}

export default function CarSelector({ compact = false, onSubmit, submitLabel = "Find parts for my car", initialValues = null }) {
  const [makes, setMakes] = useState([]);
  const [models, setModels] = useState([]);
  const [generations, setGenerations] = useState([]);
  const [modifications, setModifications] = useState([]);

  const [makeId, setMakeId] = useState(initialValues?.makeId ? String(initialValues.makeId) : "");
  const [modelId, setModelId] = useState(initialValues?.modelId ? String(initialValues.modelId) : "");
  const [generationId, setGenerationId] = useState(initialValues?.generationId ? String(initialValues.generationId) : "");
  const [modificationId, setModificationId] = useState(initialValues?.modificationId ? String(initialValues.modificationId) : "");
  const [year, setYear] = useState(initialValues?.year ? String(initialValues.year) : "");

  useEffect(() => {
    getMakes().then((d) => setMakes(Array.isArray(d) ? d : d?.results || [])).catch(() => {});
  }, []);

  useEffect(() => {
    setModelId("");
    setGenerationId("");
    setModificationId("");
    setModels([]);
    setGenerations([]);
    setModifications([]);
    if (!makeId) return;
    getModels(makeId).then((d) => setModels(Array.isArray(d) ? d : d?.results || [])).catch(() => {});
  }, [makeId]);

  useEffect(() => {
    setGenerationId("");
    setModificationId("");
    setGenerations([]);
    setModifications([]);
    if (!modelId) return;
    getGenerations(modelId).then((d) => setGenerations(Array.isArray(d) ? d : d?.results || [])).catch(() => {});
  }, [modelId]);

  useEffect(() => {
    setModificationId("");
    setModifications([]);
    if (!generationId) return;
    getModifications(generationId).then((d) => setModifications(Array.isArray(d) ? d : d?.results || [])).catch(() => {});
  }, [generationId]);

  const selectedGen = generations.find((g) => String(g.id) === generationId);
  const yearMin = selectedGen?.production_start ? new Date(selectedGen.production_start).getFullYear() : 1970;
  const yearMax = selectedGen?.production_end ? new Date(selectedGen.production_end).getFullYear() : new Date().getFullYear();
  const years = [];
  for (let y = yearMax; y >= yearMin; y--) years.push(y);

  function handleSubmit(e) {
    e.preventDefault();
    if (!makeId || !modelId || !generationId || !year) return;
    onSubmit?.(
      buildCarPayload({ makeId, modelId, generationId, modificationId, year, makes, models, generations, modifications }),
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: compact ? 8 : 10 }}>
        <Field label={compact ? null : "Make"}>
          <select value={makeId} onChange={(e) => setMakeId(e.target.value)} style={selectStyle} required>
            <option value="">Make</option>
            {makes.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </Field>
        <Field label={compact ? null : "Model"}>
          <select value={modelId} onChange={(e) => setModelId(e.target.value)} style={selectStyle} disabled={!makeId} required>
            <option value="">Model</option>
            {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </Field>
        <Field label={compact ? null : "Generation"}>
          <select value={generationId} onChange={(e) => setGenerationId(e.target.value)} style={selectStyle} disabled={!modelId} required>
            <option value="">Generation</option>
            {generations.map((g) => (
              <option key={g.id} value={g.id}>{g.display_label || g.name}</option>
            ))}
          </select>
        </Field>
        <Field label={compact ? null : "Year"}>
          <select value={year} onChange={(e) => setYear(e.target.value)} style={selectStyle} disabled={!generationId} required>
            <option value="">Year</option>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </Field>
        {modifications.length > 0 && (
          <Field label={compact ? null : "Modification (optional)"}>
            <select value={modificationId} onChange={(e) => setModificationId(e.target.value)} style={selectStyle}>
              <option value="">Any trim / engine</option>
              {modifications.map((m) => <option key={m.id} value={m.id}>{m.display_label || m.code}</option>)}
            </select>
          </Field>
        )}
        <div style={{ flex: compact ? "1 1 100%" : "0 0 auto", alignSelf: compact ? "stretch" : "flex-end", minWidth: compact ? undefined : 200 }}>
          <button
            type="submit"
            className="btn-forge"
            style={{ width: "100%", height: 42, fontSize: 14, borderRadius: 8 }}
            disabled={!makeId || !modelId || !generationId || !year}
          >
            {submitLabel}
          </button>
        </div>
      </div>
    </form>
  );
}
