# Markets and Matching

## V0.1 markets

The minimum economy needs four interaction layers:

1. labor market;
2. consumer-goods market;
3. mortgage/credit market;
4. foreign/import input channel.

Housing transactions can be deferred until a later version if initial homes and mortgages are assigned at initialization.

## Labor market

### Minimal rule

Firms have desired employment based on expected demand and productivity.

\[
L^d_{j,t}=\frac{Q^{desired}_{j,t}}{productivity_j}
\]

Firms with vacancies sample unemployed households. Households accept offers subject to a simple reservation-wage rule or accept any offer in V0.1.

### Wage setting

V0.1 can use:

\[
W_{j,t}=W_{j,t-1}\left(1+\gamma_w f(labor\ tightness,\ past\ inflation,\ productivity)\right)
\]

Do **not** mechanically index wages in the baseline. Wage indexation becomes a separate experiment in V0.2.

## Consumer-goods market

Households allocate planned consumption across firms.

Simple matching options:

- random sample weighted toward cheaper firms;
- logit choice based on relative price;
- fixed preferred suppliers with occasional switching.

A transparent price-sensitive rule is preferable to full perfect competition.

If demand exceeds inventory, rationing occurs and actual household consumption can be below desired consumption.

## Credit/mortgage market

In V0.1, mortgages may be assigned initially rather than originated every month. If new origination is included:

1. household requests loan;
2. bank checks LTV, DSTI, and affordability rules;
3. bank offers indexed and/or nominal product;
4. contract is created;
5. transaction changes deposits and balance sheets consistently.

## Foreign/import channel

Firms use imported inputs with share \(m_j\).

Import cost index:

\[
P^{imp}_t = E_t P^*_t
\]

where:

- \(E_t\) is domestic currency per unit of foreign currency;
- \(P^*_t\) is the foreign price index.

Firm unit costs therefore respond to exchange-rate or foreign-price shocks.

## Housing market — later version

When introduced, housing should include:

- fixed or slowly changing housing stock;
- sellers and buyers;
- bid/ask or search-and-matching process;
- mortgage approval;
- house-price index;
- LTV dynamics;
- collateral/default recovery.

Do not introduce this until mortgage indexation works correctly without it.

## Market design principle

Avoid Walrasian clearing by construction. Shortages, inventories, unemployment, rationing, and unsuccessful credit applications are useful ABM outcomes.
