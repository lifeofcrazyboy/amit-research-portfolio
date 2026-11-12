(() => {
  'use strict';
  const menu = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#main-nav');
  const dockMenu = document.querySelector('.dock-menu');
  let menuTrigger = menu;
  function closeMenu() { nav.classList.remove('open'); [menu, dockMenu].forEach(button => button.setAttribute('aria-expanded', 'false')); }
  function toggleMenu(event) {
    const open = !nav.classList.contains('open');
    menuTrigger = event.currentTarget;
    [menu, dockMenu].forEach(button => button.setAttribute('aria-expanded', String(open)));
    nav.classList.toggle('open', open);
    if (open && menuTrigger === dockMenu) nav.querySelector('a').focus({ preventScroll: true });
  }
  menu.addEventListener('click', toggleMenu);
  dockMenu.addEventListener('click', toggleMenu);
  nav.addEventListener('click', event => { if (event.target.closest('a')) closeMenu(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && nav.classList.contains('open')) { closeMenu(); menuTrigger.focus(); } });
  document.addEventListener('click', event => { if (!event.target.closest('.site-header, .mobile-dock')) closeMenu(); });
  document.getElementById('copyright-year').textContent = new Date().getFullYear();

  // Real links and hashes keep each section bookmarkable, including without JavaScript.
  const sectionOrder = ['home', 'research', 'publications', 'fieldwork', 'journey', 'community', 'contact'];
  const sectionNames = {home:'Overview', research:'Research', publications:'Publications', fieldwork:'Fieldwork', journey:'Experience', community:'Skills & awards', contact:'Contact'};
  const sections = sectionOrder.map(id => document.getElementById(id));
  const sectionLinks = [...document.querySelectorAll('#main-nav a, .mobile-dock a, .wordmark')];
  const viewBar = document.querySelector('.view-bar');
  const previous = document.querySelector('#previous-section');
  const next = document.querySelector('#next-section');
  const baseTitle = document.title;
  let currentSection;
  function showSection(id, focusHeading = false) {
    if (!sectionOrder.includes(id)) id = 'home';
    const index = sectionOrder.indexOf(id);
    sections.forEach(section => { section.hidden = section.id !== id; });
    document.querySelector('.research-strip').hidden = id !== 'home';
    document.body.dataset.section = id;
    viewBar.hidden = id === 'home';
    document.querySelector('#view-number').textContent = `${String(index + 1).padStart(2, '0')} / 07`;
    document.querySelector('#view-title').textContent = sectionNames[id];
    const prevId = sectionOrder[Math.max(0, index - 1)];
    const nextId = sectionOrder[(index + 1) % sectionOrder.length];
    previous.href = '#' + prevId;
    previous.querySelector('.pager-label').textContent = sectionNames[prevId];
    next.href = '#' + nextId;
    next.querySelector('.pager-label').textContent = sectionNames[nextId];
    sectionLinks.forEach(link => {
      if (link.hash === '#' + id) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    dockMenu.classList.toggle('current-group', !['home','research','publications'].includes(id));
    document.title = id === 'home' ? baseTitle : `${sectionNames[id]} · Amit Singh Chandel`;
    closeMenu();
    if (currentSection !== id || focusHeading) {
      window.scrollTo({ top: 0, behavior: 'instant' });
      if (focusHeading) {
        const heading = document.getElementById(id).querySelector('h1, h2');
        heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
      }
    }
    currentSection = id;
  }
  document.documentElement.classList.add('interactive');
  document.querySelector('.mobile-dock').hidden = false;
  showSection(location.hash.slice(1));
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const id = link.hash.slice(1);
    if (!sectionOrder.includes(id)) return;
    event.preventDefault();
    if (location.hash !== '#' + id) history.pushState(null, '', '#' + id);
    showSection(id, true);
  });
  window.addEventListener('hashchange', () => showSection(location.hash.slice(1), true));

  const publications = [...document.querySelectorAll('.publication')];
  const search = document.querySelector('#publication-search');
  const years = document.querySelector('#publication-year');
  const tabs = [...document.querySelectorAll('[data-filter]')];
  const more = document.querySelector('#show-more');
  const results = document.querySelector('#publication-results');
  const empty = document.querySelector('.empty-state');
  let activeType = 'all';
  let limit = 5;
  const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
  publications.forEach(publication => { publication.searchText = normalize(publication.textContent); });
  [...new Set(publications.map(publication => publication.dataset.year).filter(Boolean))].sort().reverse().forEach(year => {
    const option = document.createElement('option'); option.value = year; option.textContent = year; years.append(option);
  });
  function update() {
    const query = normalize(search.value.trim());
    const matches = publications.filter(publication => {
      const type = publication.dataset.type;
      return (activeType === 'all' || type === activeType || (activeType === 'other' && type !== 'journal-article')) &&
        (years.value === 'all' || publication.dataset.year === years.value) &&
        (!query || publication.searchText.includes(query));
    });
    publications.forEach(publication => { publication.hidden = true; });
    matches.slice(0, limit).forEach(publication => { publication.hidden = false; });
    results.textContent = matches.length ? `Showing ${Math.min(limit, matches.length)} of ${matches.length} research outputs` : '0 research outputs';
    empty.hidden = matches.length > 0;
    more.hidden = matches.length <= limit;
    more.firstChild.textContent = `Show ${Math.min(5, matches.length - limit)} more publications `;
  }
  tabs.forEach(tab => tab.addEventListener('click', () => {
    activeType = tab.dataset.filter;
    tabs.forEach(button => { button.classList.toggle('active', button === tab); button.setAttribute('aria-pressed', String(button === tab)); });
    limit = 5; update();
  }));
  search.addEventListener('input', () => { limit = 5; update(); });
  years.addEventListener('change', () => { limit = 5; update(); });
  more.addEventListener('click', () => {
    const before = publications.filter(publication => !publication.hidden).length;
    limit += 5; update();
    const firstNew = publications.filter(publication => !publication.hidden)[before]?.querySelector('h3 a');
    firstNew?.focus({ preventScroll: true });
  });
  document.querySelector('#reset-filters').addEventListener('click', () => {
    search.value = ''; years.value = 'all'; tabs[0].click(); search.focus();
  });
  document.querySelector('.publication-toolbar').hidden = false;
  update();

  let toastTimer;
  const toast = document.querySelector('#toast');
  function notify(message) { clearTimeout(toastTimer); toast.textContent = message; toast.hidden = false; toastTimer = setTimeout(() => { toast.hidden = true; }, 4000); }
  document.querySelector('#publication-list').addEventListener('click', async event => {
    const button = event.target.closest('.copy-citation');
    if (!button) return;
    const text = button.dataset.citation;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const input = document.createElement('textarea'); input.value = text; input.setAttribute('readonly', '');
        input.style.cssText = 'position:fixed;left:-9999px;top:0'; document.body.append(input); input.select();
        const success = document.execCommand('copy'); input.remove(); button.focus();
        if (!success) throw new Error('Clipboard unavailable');
      }
      notify('Citation copied to clipboard.');
    } catch {
      window.prompt('Copy this citation:', text);
    }
  });
})();
