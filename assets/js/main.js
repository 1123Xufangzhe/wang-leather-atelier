/* 王氏手工皮艺 — site interactions */
(function () {
  'use strict';

  var doc = document;
  var header = doc.querySelector('.header');
  var burger = doc.querySelector('.burger');
  var drawer = doc.querySelector('.drawer');
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (location.search.indexOf('shot') > -1) document.documentElement.classList.add('shot');

  /* ----- header state ----- */
  var lastY = 0;
  function onScroll() {
    var y = window.scrollY || window.pageYOffset;
    if (header) header.classList.toggle('is-scrolled', y > 40);
    lastY = y;
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ----- mobile drawer ----- */
  function setDrawer(open) {
    if (!drawer || !burger) return;
    drawer.classList.toggle('is-open', open);
    burger.classList.toggle('is-open', open);
    burger.setAttribute('aria-expanded', String(open));
    doc.body.style.overflow = open ? 'hidden' : '';
    if (header) header.classList.toggle('is-scrolled', open || (window.scrollY || 0) > 40);
  }
  if (burger) {
    burger.addEventListener('click', function () {
      setDrawer(!drawer.classList.contains('is-open'));
    });
  }
  if (drawer) {
    drawer.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () { setDrawer(false); });
    });
    doc.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') setDrawer(false);
    });
  }

  /* ----- active nav ----- */
  var page = doc.body.getAttribute('data-page');
  if (page) {
    doc.querySelectorAll('[data-nav]').forEach(function (a) {
      if (a.getAttribute('data-nav') === page) { a.classList.add('is-active'); a.setAttribute('aria-current', 'page'); }
    });
  }

  /* ----- reveal on scroll ----- */
  var revealEls = doc.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add('is-in');
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add('is-in'); });
  }

  /* ----- hero parallax ----- */
  var heroBg = doc.querySelector('.hero__bg');
  if (heroBg && !reduceMotion) {
    var raf = false;
    window.addEventListener('scroll', function () {
      if (raf) return;
      raf = true;
      window.requestAnimationFrame(function () {
        var y = window.scrollY || 0;
        if (y < window.innerHeight * 1.2) {
          heroBg.style.transform = 'translate3d(0,' + (y * 0.18).toFixed(1) + 'px,0)';
        }
        raf = false;
      });
    }, { passive: true });
  }

  /* ----- ticker duplicate for seamless loop ----- */
  var track = doc.querySelector('.ticker__track');
  if (track) {
    track.innerHTML = track.innerHTML + track.innerHTML;
  }

  /* ----- works filter ----- */
  var filters = doc.querySelectorAll('.filter');
  var workItems = doc.querySelectorAll('[data-cat]');
  filters.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var cat = btn.getAttribute('data-filter');
      filters.forEach(function (b) { b.classList.toggle('is-active', b === btn); });
      workItems.forEach(function (item) {
        var match = cat === 'all' || item.getAttribute('data-cat').split(' ').indexOf(cat) > -1;
        item.style.display = match ? '' : 'none';
        if (match) {
          item.classList.remove('is-in');
          void item.offsetWidth;
          item.classList.add('is-in');
        }
      });
    });
  });

  /* ----- booking form (static demo) ----- */
  var form = doc.querySelector('[data-form]');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var name = form.querySelector('[name="name"]');
      var phone = form.querySelector('[name="phone"]');
      var want = form.querySelector('[name="want"]');
      var ok = true;
      [name, phone].forEach(function (f) {
        if (!f || !f.value.trim()) {
          ok = false;
          if (f) f.style.borderColor = '#a5452f';
        } else if (f) {
          f.style.borderColor = '';
        }
      });
      if (phone && phone.value && !/^1[3-9]\d{9}$/.test(phone.value.trim())) {
        ok = false;
        phone.style.borderColor = '#a5452f';
        phone.setAttribute('placeholder', '请填写 11 位手机号');
      }
      if (!ok) return;

      var done = doc.querySelector('.form-done');
      var summary = doc.querySelector('[data-summary]');
      if (summary) {
        summary.textContent = name.value.trim() + '，' + phone.value.trim() +
          '，' + (want && want.value.trim() ? want.value.trim() : '想聊聊定制');
      }
      if (done) {
        done.classList.add('is-on');
        done.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      var copyBtn = doc.querySelector('[data-copy]');
      if (copyBtn) {
        copyBtn.addEventListener('click', function () {
          var text = '预约到店｜王氏手工皮艺\n姓名：' + name.value.trim() +
            '\n电话：' + phone.value.trim() +
            '\n需求：' + (want && want.value.trim() ? want.value.trim() : '到店了解');
          if (navigator.clipboard) navigator.clipboard.writeText(text);
          copyBtn.textContent = '已复制 ✓';
          setTimeout(function () { copyBtn.textContent = '复制预约信息'; }, 2000);
        });
      }
      form.reset();
    });
  }

  /* ----- copy address ----- */
  doc.querySelectorAll('[data-copy-text]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var t = btn.getAttribute('data-copy-text');
      if (navigator.clipboard) navigator.clipboard.writeText(t);
      var old = btn.textContent;
      btn.textContent = '地址已复制 ✓';
      setTimeout(function () { btn.textContent = old; }, 1800);
    });
  });


  /* ----- footer year ----- */
  doc.querySelectorAll('[data-year]').forEach(function (el) {
    el.textContent = new Date().getFullYear();
  });
})();





/* ---------- floating UI: mobile action bar + back to top ---------- */
(function () {
  var bar = document.createElement('div');
  bar.className = 'mobile-bar';
  bar.innerHTML = '<a href="works.html">看作品</a><a class="primary" href="visit.html">预约到店</a>';
  document.body.appendChild(bar);

  var top = document.createElement('button');
  top.className = 'to-top';
  top.type = 'button';
  top.setAttribute('aria-label', '回到顶部');
  top.textContent = '↑';
  document.body.appendChild(top);

  top.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  var tick = false;
  window.addEventListener('scroll', function () {
    if (tick) return;
    tick = true;
    window.requestAnimationFrame(function () {
      top.classList.toggle('is-on', window.scrollY > 640);
      tick = false;
    });
  }, { passive: true });
})();

/* ---------- footer wordmark ---------- */
(function () {
  var top = document.querySelector('.footer__top');
  if (!top) return;
  var w = document.createElement('div');
  w.className = 'footer__wordmark';
  w.setAttribute('aria-hidden', 'true');
  w.textContent = 'WANG LEATHER ATELIER';
  top.insertBefore(w, top.firstChild);
})();


/* ---------- editorial details: folio numbers / colophon ---------- */
(function () {
  document.querySelectorAll('.sec-head .idx').forEach(function (el) {
    var m = el.textContent.match(/(\d+)\s*\/\s*(.+)/);
    if (!m) return;
    el.innerHTML = '<b>' + m[1] + '</b><span>' + m[2].trim() + '</span>';
  });

  var foot = document.querySelector('.footer .container');
  if (foot) {
    var c = document.createElement('div');
    c.className = 'footer__colophon';
    c.innerHTML = '<span>No.01 — Changchun 2026</span><span>Typography · Noto Serif SC / Noto Sans SC</span><span>Images · Rendered</span>';
    foot.insertBefore(c, foot.querySelector('.footer__bottom'));
  }
})();

/* ---------- interactive icons + magnetic buttons + cursor ---------- */
(function () {
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || !window.matchMedia('(hover:hover)').matches) return;

  /* hero 跟随鼠标微位移 */
  var hero = document.querySelector('.hero');
  var heroInner = hero ? hero.querySelector('.hero__inner') : null;
  if (hero && heroInner) {
    hero.addEventListener('pointermove', function (e) {
      var r = hero.getBoundingClientRect();
      var dx = (e.clientX - r.left) / r.width - .5;
      var dy = (e.clientY - r.top) / r.height - .5;
      heroInner.style.transform = 'translate(' + (dx * 12).toFixed(1) + 'px,' + (dy * 7).toFixed(1) + 'px)';
      heroInner.style.transition = 'transform .12s linear';
    });
    hero.addEventListener('pointerleave', function () {
      heroInner.style.transition = 'transform .8s cubic-bezier(.22,.61,.36,1)';
      heroInner.style.transform = '';
    });
  }
  /* icon tilt inside cards */
  document.querySelectorAll('.principle, .service').forEach(function (card) {
    var icon = card.querySelector('.icon');
    if (!icon) return;
    card.addEventListener('pointermove', function (e) {
      var r = card.getBoundingClientRect();
      var dx = (e.clientX - r.left) / r.width - .5;
      var dy = (e.clientY - r.top) / r.height - .5;
      icon.style.transform = 'translate(' + (dx * 8).toFixed(1) + 'px,' + (dy * 8).toFixed(1) + 'px) rotate(' + (dx * 9).toFixed(1) + 'deg)';
    });
    card.addEventListener('pointerleave', function () { icon.style.transform = ''; });
  });

  /* magnetic buttons */
  document.querySelectorAll('.btn, .header__cta').forEach(function (b) {
    b.addEventListener('pointermove', function (e) {
      var r = b.getBoundingClientRect();
      var dx = (e.clientX - r.left) / r.width - .5;
      var dy = (e.clientY - r.top) / r.height - .5;
      b.style.transform = 'translate(' + (dx * 6).toFixed(1) + 'px,' + (dy * 4).toFixed(1) + 'px)';
    });
    b.addEventListener('pointerleave', function () { b.style.transform = ''; });
  });

  /* custom cursor */
  var ring = document.createElement('div'); ring.className = 'cursor-ring';
  var dot = document.createElement('div'); dot.className = 'cursor-dot';
  document.body.appendChild(ring); document.body.appendChild(dot);
  var tx = 0, ty = 0, rx = 0, ry = 0, shown = false;
  window.addEventListener('pointermove', function (e) {
    tx = e.clientX; ty = e.clientY;
    if (!shown) { shown = true; ring.style.opacity = 1; dot.style.opacity = 1; }
    dot.style.transform = 'translate(' + tx + 'px,' + ty + 'px) translate(-50%,-50%)';
    var hot = e.target.closest('a, button, .work-card, .principle, .service, summary');
    ring.classList.toggle('is-hot', !!hot);
  }, { passive: true });
  (function loop() {
    rx += (tx - rx) * .16; ry += (ty - ry) * .16;
    ring.style.transform = 'translate(' + rx + 'px,' + ry + 'px) translate(-50%,-50%)';
    window.requestAnimationFrame(loop);
  })();
  document.addEventListener('mouseleave', function () { ring.style.opacity = 0; dot.style.opacity = 0; });
  document.addEventListener('mouseenter', function () { ring.style.opacity = 1; dot.style.opacity = 1; });
})();

