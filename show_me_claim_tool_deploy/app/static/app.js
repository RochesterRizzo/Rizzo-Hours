(() => {
  const search = document.querySelector('#topic-search');
  const category = document.querySelector('#category-filter');
  const availableBtn = document.querySelector('#available-only');
  const cards = [...document.querySelectorAll('.topic-card')];
  const empty = document.querySelector('#no-results');
  let availableOnly = false;

  function filterCards() {
    if (!cards.length) return;
    const q = (search?.value || '').trim().toLowerCase();
    const cat = category?.value || '';
    let shown = 0;
    cards.forEach(card => {
      const matchesQ = !q || card.dataset.title.includes(q);
      const matchesCat = !cat || card.dataset.category === cat;
      const matchesStatus = !availableOnly || card.dataset.status === 'available';
      const show = matchesQ && matchesCat && matchesStatus;
      card.hidden = !show;
      if (show) shown += 1;
    });
    if (empty) empty.hidden = shown !== 0;
  }

  search?.addEventListener('input', filterCards);
  category?.addEventListener('change', filterCards);
  availableBtn?.addEventListener('click', () => {
    availableOnly = !availableOnly;
    availableBtn.setAttribute('aria-pressed', String(availableOnly));
    availableBtn.textContent = availableOnly ? 'Showing available' : 'Available only';
    filterCards();
  });

  document.querySelectorAll('[data-copy]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const input = document.querySelector(btn.dataset.copy);
      if (!input) return;
      try {
        await navigator.clipboard.writeText(input.value);
        const old = btn.textContent;
        btn.textContent = 'Copied';
        setTimeout(() => btn.textContent = old, 1300);
      } catch (_) {
        input.select();
        document.execCommand('copy');
      }
    });
  });
})();
