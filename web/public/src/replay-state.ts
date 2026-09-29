export interface ReplaySelection {
  kind: "run" | "sector" | "agent" | "event";
  id: string;
}

export class ReplayState extends EventTarget {
  #months: readonly string[] = [];
  #monthIndex = 0;
  #selection: ReplaySelection | null = null;

  get months(): readonly string[] {
    return this.#months;
  }

  get monthIndex(): number {
    return this.#monthIndex;
  }

  get month(): string | null {
    return this.#months[this.#monthIndex] ?? null;
  }

  get selection(): ReplaySelection | null {
    return this.#selection;
  }

  configure(months: readonly string[], initialMonth?: string): void {
    this.#months = [...months];
    const requested =
      initialMonth === undefined ? -1 : this.#months.indexOf(initialMonth);
    this.#monthIndex = requested >= 0 ? requested : 0;
    this.#selection = null;
    this.#announce("configure");
  }

  setMonthIndex(index: number): void {
    if (this.#months.length === 0) return;
    const next = Math.max(
      0,
      Math.min(Math.trunc(index), this.#months.length - 1),
    );
    if (next === this.#monthIndex) return;
    this.#monthIndex = next;
    this.#announce("month");
  }

  select(selection: ReplaySelection | null): void {
    if (
      this.#selection?.kind === selection?.kind &&
      this.#selection?.id === selection?.id
    ) {
      return;
    }
    this.#selection = selection;
    this.#announce("selection");
  }

  #announce(reason: "configure" | "month" | "selection"): void {
    this.dispatchEvent(new CustomEvent("change", { detail: { reason } }));
  }
}
