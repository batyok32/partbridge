"use client";

const STEPS = [
  { n: "01", title: "Seller uploads their car", desc: "A donor vehicle is listed with photos — every part on that car becomes discoverable." },
  { n: "02", title: "AI researches all parts", desc: "We map OEM data and market listings so each part has fitment and pricing context." },
  { n: "03", title: "You find what fits your car", desc: "Set your year, make, and generation once — compatible parts show a green fitment badge." },
  { n: "04", title: "We handle shipping", desc: "Shipping tiers and estimates are shown upfront based on part size and your state." },
];

export default function HowItWorksBuyer() {
  return (
    <section id="how-it-works" className="py-24">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-14">
          <span className="section-label justify-center mb-4">How it works</span>
          <h2 className="heading-display text-3xl sm:text-4xl mt-2">From donor car to your driveway</h2>
        </div>
        <div className="space-y-4">
          {STEPS.map((s) => (
            <div
              key={s.n}
              className="flex gap-4 rounded-[12px] p-5"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
            >
              <span style={{ fontFamily: "var(--ff-mono)", fontSize: 12, fontWeight: 700, color: "var(--primary)" }}>{s.n}</span>
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>{s.title}</h3>
                <p style={{ fontSize: 13, color: "var(--text-muted)", lineHeight: 1.5 }}>{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
