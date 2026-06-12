/* ReStone — Motion Layer（進場動畫 + 數字滾動）
   配合 theme-gallery.css 的 .rv/.in 樣式；尊重 prefers-reduced-motion。 */
(function () {
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  function init() {
    // ── 進場動畫：常見卡片/面板自動套用,進入視窗時交錯浮現 ──
    var SELECTOR = '.stone-card, .tool, .card, .design-card, .shot, .rec, ' +
                   '.inquiry-card, .stat, .spec-card, .panel, .profile-card';
    var els = Array.prototype.slice.call(document.querySelectorAll(SELECTOR));
    if ('IntersectionObserver' in window && els.length) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (!e.isIntersecting) return;
          var el = e.target;
          var delay = (parseInt(el.dataset.rvIdx || '0', 10) % 6) * 70;
          setTimeout(function () { el.classList.add('in'); }, delay);
          io.unobserve(el);
        });
      }, { threshold: 0.08, rootMargin: '0px 0px -4% 0px' });
      els.forEach(function (el, i) {
        el.dataset.rvIdx = String(i);
        el.classList.add('rv');
        io.observe(el);
      });
    }

    // ── 數字滾動：.stat-num 內的數字從 0 跳到實際值 ──
    var nums = Array.prototype.slice.call(document.querySelectorAll('.stat-num'));
    nums.forEach(function (el) {
      var text = el.textContent;
      var m = text.match(/([\d,]+(?:\.\d+)?)/);
      if (!m) return;
      var target = parseFloat(m[1].replace(/,/g, ''));
      if (!isFinite(target) || target <= 0) return;
      var decimals = (m[1].split('.')[1] || '').length;
      var started = false;
      function run() {
        if (started) return; started = true;
        var t0 = null, DUR = 1300;
        function frame(ts) {
          if (!t0) t0 = ts;
          var p = Math.min(1, (ts - t0) / DUR);
          var eased = 1 - Math.pow(1 - p, 3);
          var val = (target * eased).toFixed(decimals);
          if (decimals === 0) val = Math.round(target * eased).toLocaleString();
          el.textContent = text.replace(m[1], val);
          if (p < 1) requestAnimationFrame(frame);
          else el.textContent = text;
        }
        requestAnimationFrame(frame);
      }
      if ('IntersectionObserver' in window) {
        var io2 = new IntersectionObserver(function (entries) {
          entries.forEach(function (e) { if (e.isIntersecting) { run(); io2.disconnect(); } });
        }, { threshold: 0.4 });
        io2.observe(el);
      } else { run(); }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
