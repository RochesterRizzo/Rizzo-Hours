# Professor Rizzo's Office Hours Site

This is a static GitHub Pages site. The main Office Hours page remains the
root `index.html`. Course Updates and their archives are stored under
`weekly/`.

## Main locations

- Office Hours homepage: `index.html`
- All Course Updates: `weekly/index.html`
- ECON 108 / EWOT: `weekly/ewot/index.html`
- Current EWOT semester: `weekly/ewot/fall-2026/index.html`
- Fall 2025 EWOT archive: `weekly/ewot/fall-2025/index.html`
- Price Theory: `weekly/price-theory/index.html`
- Money, Banking & Modern Financial Institutions: `weekly/money-banking/index.html`
- Sports Economics: `weekly/sports-economics/index.html`
- Environmental Economics: `weekly/environmental-economics/index.html`
- Shared Course Update styles: `weekly/assets/weekly.css`
- EWOT update template: `weekly/_templates/ewot-update.html`

The full weekly workflow is in `WEEKLY-UPDATES-GUIDE.md`.

## What's on Tap? editorial rules

The discussion page is `whats-on-tap.html`. It is a **running conversation**, not a static syllabus.

- Put each new discussion **first** in the `#main-questions` section, with a unique `id` and `data-added="YYYY-MM-DD"`; write a sharp title, short argument, and the source link.
- **What are we talking about this week?** automatically displays the four newest questions, with links to the originals.
- **Hot Discussion** automatically features the newest question. Write its headline to be worth arguing about, not as a bland topic label.
- **The Big Theme** is separate: a substantive, recurring line of inquiry across the semester. **None is selected yet**; do not silently revive AI Sludge or manufacture one.
- Keep earlier ideas and links; don't let old feature boxes, repeated boilerplate, or unchanged dates masquerade as this week's conversation.

## GitHub Pages

The repository is published from the `main` branch and the repository root.
In GitHub, open **Settings → Pages** and use:

- Source: **Deploy from a branch**
- Branch: **main**
- Folder: **/ (root)**

Merging an approved branch into `main` updates the public site.
