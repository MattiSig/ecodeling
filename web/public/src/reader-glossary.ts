import { html } from "lit";

// Browser authority, adapted from specs/21_glossary.md. Keep expansions in one place.
export const GLOSSARY = {
  ABM: [
    "Agent-based model",
    "A simulation of different households, firms, and institutions following rules and interacting; their actions produce aggregate outcomes.",
  ],
  CPI: [
    "Consumer Price Index",
    "A measure of consumer prices. Here it is computed from simulated purchases, not observed Icelandic prices.",
  ],
  FX: [
    "Foreign exchange",
    "The exchange rate is krónur per foreign-currency unit. A rise makes imported inputs more expensive in this model.",
  ],
  ISK: [
    "Icelandic króna",
    "The currency unit. Monetary results are nominal whole krónur, not inflation-adjusted purchasing power.",
  ],
  LTV: [
    "Loan-to-value",
    "Mortgage balance divided by property value. A higher ratio means more debt relative to collateral.",
  ],
  DSTI: [
    "Debt-service-to-income",
    "Debt payments divided by income. A higher ratio means more current income is needed for debt service.",
  ],
  SFC: [
    "Stock-flow consistency",
    "Assets, liabilities, and flows reconcile across agents. Each financial asset has a matching liability.",
  ],
  IRF: [
    "Impulse response function",
    "A path after a shock relative to a no-shock counterfactual. The displayed indexed-minus-nominal comparison is not an impulse response.",
  ],
  principal: [
    "Principal",
    "The outstanding loan balance before future interest. Indexation can increase it even while payments are made.",
  ],
  revaluation: [
    "Revaluation",
    "A change in the value of an asset and its matching liability without a cash transfer. Indexation rewrites the mortgage balance.",
  ],
  indexation: [
    "Price indexation",
    "A contract rule that changes a nominal amount with a price index after a specified lag.",
  ],
} as const;
export type GlossaryTerm = keyof typeof GLOSSARY;

export function glossary() {
  return html`<details class="reader-glossary">
    <summary>Glossary — words used in this model</summary>
    <p>
      Focus, hover, or tap a term to read its definition. Tap again to close it.
    </p>
    <div>
      ${Object.entries(GLOSSARY).map(
        ([key, [expanded, definition]]) =>
          html` <div class="glossary-entry">
            <div>
              <details
                @pointerenter=${(e: PointerEvent) => {
                  if (e.pointerType === "mouse")
                    (e.currentTarget as HTMLDetailsElement).open = true;
                }}
                @focusin=${(e: FocusEvent) => {
                  if ((e.target as HTMLElement).matches(":focus-visible"))
                    (e.currentTarget as HTMLDetailsElement).open = true;
                }}
              >
                <summary aria-describedby=${`definition-${key}`}>
                  <abbr>${key}</abbr> — ${expanded}
                </summary>
                <p id=${`definition-${key}`}>${definition}</p>
              </details>
            </div>
          </div>`,
      )}
    </div>
  </details>`;
}

export const METRIC_GUIDES: Record<string, string> = {
  cpi_level:
    "Consumer Price Index (CPI): simulated transaction prices, shown on an index with a base of 100. A rise means the same goods cost more; it is a price level, not an inflation rate.",
  policy_rate:
    "Annual policy rate, shown as a percentage. A higher rate can raise later loan coupons under the declared reset rule; it is separate from principal revaluation.",
  mortgage_principal:
    "Outstanding mortgage stock in nominal whole Icelandic krónur (ISK). A larger balance means more debt remains; defaults and payments also change it.",
  debt_service:
    "Mortgage payments settled during this month, in nominal whole Icelandic krónur (ISK). Lower payments need not mean lower lifetime debt or better welfare.",
  consumption:
    "Household expenditure during this month, in nominal whole Icelandic krónur (ISK). A rise may reflect prices or quantities; it is not a direct measure of welfare.",
  defaults:
    "Households defaulting during this month. A larger count signals more recorded credit distress under the model's default rule.",
  bank_equity:
    "Bank assets minus liabilities at month end, in nominal whole Icelandic krónur (ISK). Revaluations, defaults, and distributed interest all affect this stock.",
};

/** Inline disclosure shares the glossary definitions; no native-title dependency. */
export function term(key: GlossaryTerm, instance: string) {
  const id = `term-${instance}-${key}`;
  const show = (target: EventTarget | null, visible: boolean) => {
    const button = target as HTMLButtonElement;
    button.setAttribute("aria-expanded", String(visible));
    (button.nextElementSibling as HTMLElement).hidden = !visible;
  };
  return html`<span
    class="inline-term"
    @pointerleave=${(e: PointerEvent) => {
      const button = (e.currentTarget as HTMLElement).querySelector("button")!;
      if (
        e.pointerType === "mouse" &&
        !button.dataset.pinned &&
        !button.matches(":focus-visible")
      )
        show(button, false);
    }}
    ><button
      type="button"
      aria-describedby=${id}
      aria-expanded="false"
      @pointerenter=${(e: PointerEvent) => {
        if (e.pointerType === "mouse") show(e.currentTarget, true);
      }}
      @focus=${(e: FocusEvent) => {
        if ((e.currentTarget as HTMLElement).matches(":focus-visible"))
          show(e.currentTarget, true);
      }}
      @blur=${(e: FocusEvent) => {
        delete (e.currentTarget as HTMLElement).dataset.pinned;
        show(e.currentTarget, false);
      }}
      @click=${(e: MouseEvent) => {
        const target = e.currentTarget as HTMLElement;
        if (target.dataset.pinned) {
          delete target.dataset.pinned;
          show(target, false);
        } else {
          target.dataset.pinned = "true";
          show(target, true);
        }
      }}
      @keydown=${(e: KeyboardEvent) => {
        if (e.key === "Escape") {
          delete (e.currentTarget as HTMLElement).dataset.pinned;
          show(e.currentTarget, false);
          e.stopPropagation();
        }
      }}
    >
      <abbr>${key}</abbr></button
    ><span id=${id} class="term-definition" role="tooltip" hidden
      >${GLOSSARY[key][0]}: ${GLOSSARY[key][1]}</span
    ></span
  >`;
}
