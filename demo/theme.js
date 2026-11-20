/* Incident Skeleton skins: Day (white) · Night edition (purple) · Auto (follows the system).
   Loaded in <head> so the skin is set before the page paints. The choice is shared by every page
   (localStorage "theme"); ?theme=day|night|auto overrides it for one visit.
   A page shows the switch by having an element with id="themeSeg", and calls Theme.relabel()
   after it changes language. */
(function () {
  var KEY = 'theme', ICON = {day: '☀︎', night: '☾', auto: '◐'};
  var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function pref() {
    try {
      var q = new URLSearchParams(location.search).get('theme');
      if (q === 'day' || q === 'night' || q === 'auto') return q;
      var s = localStorage.getItem(KEY);
      if (s === 'day' || s === 'night' || s === 'auto') return s;
    } catch (e) {}
    return 'auto';
  }
  var cur = pref();
  function resolved(p) { return p === 'auto' ? ((mq && mq.matches) ? 'night' : 'day') : p; }
  function labels() {
    var zh = (document.documentElement.lang || '').toLowerCase().indexOf('zh') === 0;
    return zh ? {day: '白天', night: '夜晚限定', auto: '跟随系统'} : {day: 'Day', night: 'Night edition', auto: 'Auto'};
  }
  function render() {
    var slot = document.getElementById('themeSeg');
    if (!slot) return;
    var L = labels(), h = '';
    ['day', 'night', 'auto'].forEach(function (k) {
      h += '<button type="button" data-t="' + k + '" aria-pressed="' + (k === cur) + '" title="' + L[k] + '">' + ICON[k] + ' ' + L[k] + '</button>';
    });
    slot.innerHTML = h;
    slot.setAttribute('role', 'group');
    slot.setAttribute('aria-label', labels().auto === 'Auto' ? 'Skin' : '皮肤');
  }
  function apply(p) {
    var r = document.documentElement;
    r.setAttribute('data-theme-pref', p);
    r.setAttribute('data-theme', resolved(p));
    render();
    try { window.dispatchEvent(new CustomEvent('themechange', {detail: r.getAttribute('data-theme')})); } catch (e) {}
  }
  document.addEventListener('click', function (e) {
    var b = e.target && e.target.closest ? e.target.closest('#themeSeg button') : null;
    if (!b) return;
    cur = b.getAttribute('data-t');
    try { localStorage.setItem(KEY, cur); } catch (err) {}
    apply(cur);
  });
  if (mq) {
    var onChange = function () { if (cur === 'auto') apply('auto'); };
    if (mq.addEventListener) mq.addEventListener('change', onChange); else if (mq.addListener) mq.addListener(onChange);
  }
  window.Theme = {relabel: render, get: function () { return document.documentElement.getAttribute('data-theme'); }};
  apply(cur);
  document.addEventListener('DOMContentLoaded', render);
})();
