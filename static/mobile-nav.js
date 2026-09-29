/* ReStone — 手機版導覽
   前台：header 放不下時收合成漢堡選單（手機一律收合；平板或英日文較長時自動偵測）
   後台：窄螢幕時左側選單改為抽屜，從上方按鈕開啟 */
(function () {
  var NAV = 'a.hbtn, a.btn-link, a.header-admin';
  var PHONE = window.matchMedia('(max-width: 640px)');
  var MENU_SVG = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" ' +
                 'stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>';

  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  ready(function () {
    var header = document.querySelector('header');
    var toggle = header && header.querySelector('.mnav-toggle');
    if (header && toggle) initHeader(header, toggle);

    var sidebar = document.querySelector('.sidebar');
    var topbar = document.querySelector('.topbar');
    if (sidebar && topbar) initAdmin(topbar);
  });

  // ── 前台：漢堡選單 ──
  function initHeader(header, toggle) {
    var inner = header.querySelector('.header-inner') || header;
    var links = [].slice.call(header.querySelectorAll(NAV));
    if (!links.length) { toggle.parentNode.removeChild(toggle); return; }

    // 面板內放一份導覽連結（保留原本的主要按鈕樣式）
    var panel = document.createElement('nav');
    panel.className = 'mnav-panel';
    panel.id = 'mnav-panel';
    links.forEach(function (a) {
      var item = document.createElement('a');
      item.href = a.getAttribute('href');
      item.textContent = a.textContent.trim();
      item.className = 'mnav-item';
      var style = a.getAttribute('style') || '';
      if (/primary/.test(a.className) || /background\s*:\s*var\(--blue\)/.test(style)) item.classList.add('primary');
      panel.appendChild(item);
    });
    header.appendChild(panel);
    toggle.setAttribute('aria-controls', 'mnav-panel');
    if (getComputedStyle(header).position === 'static') header.style.position = 'relative';

    function setOpen(open) {
      header.classList.toggle('mnav-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    toggle.addEventListener('click', function (e) {
      e.stopPropagation();
      setOpen(!header.classList.contains('mnav-open'));
    });
    document.addEventListener('click', function (e) { if (!header.contains(e.target)) setOpen(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setOpen(false); });

    // 手機寬度由 CSS 直接收合；更寬的螢幕若導覽放不下，也改為收合
    function update() {
      header.classList.remove('mnav-collapsed');
      if (!PHONE.matches && inner.scrollWidth > inner.clientWidth + 1) header.classList.add('mnav-collapsed');
      if (!PHONE.matches && !header.classList.contains('mnav-collapsed')) setOpen(false);
    }
    update();
    var timer;
    window.addEventListener('resize', function () { clearTimeout(timer); timer = setTimeout(update, 120); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(update);   // 字型載入後寬度會變
  }

  // ── 後台：側欄抽屜 ──
  function initAdmin(topbar) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'sb-toggle';
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-label', ({ 'zh-TW': '選單', en: 'Menu', ja: 'メニュー' })[document.documentElement.lang] || 'Menu');
    btn.innerHTML = MENU_SVG;
    topbar.insertBefore(btn, topbar.firstChild);

    var backdrop = document.createElement('div');
    backdrop.className = 'sb-backdrop';
    document.body.appendChild(backdrop);

    function setOpen(open) {
      document.body.classList.toggle('sb-open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    btn.addEventListener('click', function () { setOpen(!document.body.classList.contains('sb-open')); });
    backdrop.addEventListener('click', function () { setOpen(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setOpen(false); });
  }
})();
