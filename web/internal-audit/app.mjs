export function validateReplay(bundle) {
  if (!bundle || bundle.manifest?.schema_version !== 0) {
    throw new Error("This audit page requires replay schema version 0.");
  }
  if (!Array.isArray(bundle.timeline) || bundle.timeline.length === 0) {
    throw new Error("Replay timeline is missing.");
  }
  if (!Array.isArray(bundle.representative_agents) || bundle.representative_agents.length === 0) {
    throw new Error("Replay has no representative households.");
  }
  return bundle;
}

export function formatISK(value) {
  return `${new Intl.NumberFormat("en-IS").format(value)} ISK`;
}

export function viewAt(bundle, monthIndex, householdId) {
  const month = bundle.timeline[monthIndex]?.month;
  const agent = bundle.representative_agents.find((item) => item.household_id === householdId);
  if (!month || !agent) throw new Error("Unknown replay selection.");
  const point = agent.track.find((item) => item.month === month);
  const household = bundle.snapshots.find(
    (item) => item.month === month && item.sector === "households",
  );
  const bank = bundle.snapshots.find((item) => item.month === month && item.sector === "banks");
  const event = point?.revaluation_event_id
    ? bundle.events.find((item) => item.id === point.revaluation_event_id)
    : null;
  if (!point || !household || !bank) throw new Error("Replay tables are not aligned.");
  return { month, agent, point, household, bank, event };
}

function metric(label, value) {
  return `<article><span>${label}</span><strong>${formatISK(value)}</strong></article>`;
}

export function renderEvent(event) {
  if (!event) return "<p>No CPI revaluation in this month.</p>";
  const sides = event.ledger_sides
    .map(
      (side) => `<li><span>${side.role.replaceAll("_", " ")}</span><strong>${formatISK(
        side.amount,
      )}</strong><code>${side.account_id}</code></li>`,
    )
    .join("");
  return `<p><span class="event-type">${event.event_type}</span> from <code>${
    event.ledger_entry_id
  }</code></p><ul>${sides}</ul>`;
}

export function mountAudit(document, bundle) {
  validateReplay(bundle);
  const slider = document.querySelector("#month");
  const select = document.querySelector("#representative");
  slider.max = String(bundle.timeline.length - 1);
  select.innerHTML = bundle.representative_agents
    .map(
      (agent) =>
        `<option value="${agent.household_id}">${agent.cohort.replaceAll("_", " ")} · ${
          agent.stable_label
        }</option>`,
    )
    .join("");
  document.querySelector("#run-summary").textContent = `${bundle.manifest.scenario_id} · run ${
    bundle.manifest.run_id
  } · seed ${bundle.manifest.seed}`;

  const render = () => {
    const view = viewAt(bundle, Number(slider.value), select.value);
    document.querySelector("#month-label").textContent = view.month;
    document.querySelector("#metrics").innerHTML = [
      metric("Household mortgage stock", view.household.mortgage_principal),
      metric("Household net worth", view.household.net_worth),
      metric("Bank mortgage assets", view.bank.mortgage_principal),
      metric("Bank equity", view.bank.equity),
    ].join("");
    document.querySelector("#household-title").textContent = `${view.agent.stable_label} · ${
      view.agent.cohort.replaceAll("_", " ")
    }`;
    document.querySelector("#household-values").innerHTML = `
      <div><dt>Closing principal</dt><dd>${formatISK(view.point.mortgage_principal)}</dd></div>
      <div><dt>Payment</dt><dd>${formatISK(view.point.payment)}</dd></div>
      <div><dt>CPI revaluation</dt><dd>${formatISK(view.point.revaluation)} <button id="inspect-change" type="button" ${view.event ? "" : "disabled"}>Inspect ledger entry</button></dd></div>
      <div><dt>Deposits</dt><dd>${formatISK(view.point.deposits)}</dd></div>
      <div><dt>Net worth</dt><dd>${formatISK(view.point.net_worth)}</dd></div>`;
    document.querySelector("#event-detail").innerHTML = view.event
      ? "<p>Select the visible CPI change to inspect its mirrored claim postings.</p>"
      : renderEvent(null);
    document.querySelector("#inspect-change").addEventListener("click", () => {
      document.querySelector("#event-detail").innerHTML = renderEvent(view.event);
    });
    document.querySelector("#previous").disabled = Number(slider.value) === 0;
    document.querySelector("#next").disabled = Number(slider.value) === bundle.timeline.length - 1;
  };
  slider.addEventListener("input", render);
  select.addEventListener("change", render);
  document.querySelector("#previous").addEventListener("click", () => {
    slider.value = String(Math.max(0, Number(slider.value) - 1));
    render();
  });
  document.querySelector("#next").addEventListener("click", () => {
    slider.value = String(Math.min(bundle.timeline.length - 1, Number(slider.value) + 1));
    render();
  });
  render();
}

if (typeof document !== "undefined") {
  fetch("replay-v0.json")
    .then((response) => {
      if (!response.ok) throw new Error(`Replay load failed (${response.status}).`);
      return response.json();
    })
    .then((bundle) => mountAudit(document, bundle))
    .catch((error) => {
      const target = document.querySelector("#error");
      target.hidden = false;
      target.textContent = error.message;
    });
}
