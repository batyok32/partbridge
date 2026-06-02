/** Inline script to apply stored theme before paint (avoids flash). */
export function themeBootstrapScript() {
  return `(function(){try{var t=localStorage.getItem("partbridge-theme");if(t==="dark")document.documentElement.classList.add("dark");else document.documentElement.classList.remove("dark");}catch(e){}})();`;
}
