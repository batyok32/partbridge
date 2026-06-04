"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/context/auth-context";
import { addUserCar, getUserCars } from "@/lib/api";

const STORAGE_KEY = "partbridge_buyer_car";

const CarContext = createContext(null);

function readStoredCar() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeStoredCar(car) {
  if (typeof window === "undefined") return;
  if (car) localStorage.setItem(STORAGE_KEY, JSON.stringify(car));
  else localStorage.removeItem(STORAGE_KEY);
}

export function CarProvider({ children }) {
  const { user } = useAuth();
  const [car, setCarState] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (user) {
        try {
          const cars = await getUserCars();
          const list = Array.isArray(cars) ? cars : cars?.results || [];
          const defaultCar = list.find((c) => c.is_default) || list[0];
          if (!cancelled && defaultCar) {
            setCarState({
              generationId: defaultCar.generation,
              modificationId: defaultCar.modification || null,
              year: defaultCar.year,
              makeId: defaultCar.make_id,
              modelId: defaultCar.model_id,
              makeName: defaultCar.make_name,
              modelName: defaultCar.model_name,
              generationName: defaultCar.generation_name,
              generationLabel: defaultCar.generation_label,
              displayLabel: defaultCar.display_label,
              userCarId: defaultCar.id,
            });
            writeStoredCar(null);
            setLoaded(true);
            return;
          }
        } catch {
          /* fall through to local */
        }
      }
      if (!cancelled) {
        setCarState(readStoredCar());
        setLoaded(true);
      }
    })();
    return () => { cancelled = true; };
  }, [user]);

  const setCar = useCallback(
    async (next) => {
      setCarState(next);
      if (!next) {
        writeStoredCar(null);
        return;
      }
      if (user) {
        try {
          const saved = await addUserCar({
            generation: next.generationId,
            modification: next.modificationId || undefined,
            year: next.year,
            is_default: true,
          });
          setCarState((prev) => ({
            ...next,
            userCarId: saved.id,
            displayLabel: saved.display_label || next.displayLabel,
          }));
          writeStoredCar(null);
          return;
        } catch {
          /* save locally if API fails */
        }
      }
      writeStoredCar(next);
    },
    [user],
  );

  const clearCar = useCallback(() => {
    setCarState(null);
    writeStoredCar(null);
  }, []);

  const value = useMemo(
    () => ({ car, setCar, clearCar, loaded, hasCar: Boolean(car?.generationId) }),
    [car, setCar, clearCar, loaded],
  );

  return <CarContext.Provider value={value}>{children}</CarContext.Provider>;
}

export function useBuyerCar() {
  const ctx = useContext(CarContext);
  if (!ctx) throw new Error("useBuyerCar must be used within CarProvider");
  return ctx;
}
