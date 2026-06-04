"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/context/auth-context";

const CartContext = createContext(null);

export function CartProvider({ children }) {
  const { user, loading: authLoading } = useAuth();
  const [cartData, setCartData] = useState({ items: [], bundles: [] });

  const refresh = useCallback(async () => {
    if (!user) {
      setCartData({ items: [], bundles: [] });
      return;
    }
    try {
      const data = await apiFetch("/cart/");
      setCartData({
        items: Array.isArray(data?.items) ? data.items : [],
        bundles: Array.isArray(data?.bundles) ? data.bundles : [],
      });
    } catch {
      // silent — cart not critical to page load
    }
  }, [user]);

  useEffect(() => {
    if (!authLoading) void refresh();
  }, [authLoading, refresh]);

  const itemIds = new Set(cartData.items.map((ci) => ci.item));
  const bundleIds = new Set(cartData.bundles.map((cb) => cb.bundle));

  // cartItemId(itemId) → the CartItem.id needed to call DELETE /cart/<id>/
  function getCartItemId(itemId) {
    return cartData.items.find((ci) => ci.item === itemId)?.id ?? null;
  }

  return (
    <CartContext.Provider value={{ cartData, itemIds, bundleIds, getCartItemId, refresh }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
}
